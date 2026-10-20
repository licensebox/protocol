#!/usr/bin/env python3
"""Shared SDK contract tests. All keys, emails and identifiers are synthetic.

Run: python3 conformance/run.py --adapter python3 ../python/tests/adapter.py
The adapter receives one JSON request on stdin and returns one JSON answer.
No production endpoint, credential folder or email service is used.
"""
import argparse
import base64
import hashlib
import hmac
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import os
import re
from pathlib import Path
import shutil
import subprocess
import tempfile
import threading
import time
from datetime import datetime, timezone

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey, Ed25519PublicKey
from cryptography.hazmat.primitives.asymmetric.mldsa import MLDSA65PrivateKey, MLDSA65PublicKey

ROOT = Path(__file__).resolve().parent.parent
START = 1_700_000_000


def enc(value):
    return base64.urlsafe_b64encode(value).decode().rstrip("=")


def dec(value):
    return base64.urlsafe_b64decode(value + "=" * (-len(value) % 4))


def stamp(value):
    return datetime.fromtimestamp(value, timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def binding(raw_id, product="demo", source="linux-machine-id"):
    canonical = raw_id.strip("\0").strip().lower().replace("-", "")
    key = hashlib.sha256(("licensebox machine binding v1\n" + product).encode()).digest()
    return "m1:" + source + ":" + hmac.new(key, (source + "\n" + canonical).encode(), hashlib.sha256).hexdigest()


ALG = "ed25519-mldsa65"
ED_PUBLIC, ED_SIGNATURE = 32, 64
SIGNATURE_SIZE = ED_SIGNATURE + 3309


class Key:
    """A hybrid Ed25519 + ML-DSA-65 private key, from its 64-byte seed."""

    def __init__(self, seed):
        assert len(seed) == 64
        self.seed = seed
        self.ed = Ed25519PrivateKey.from_private_bytes(seed[:32])
        self.ml = MLDSA65PrivateKey.from_seed_bytes(seed[32:])

    def public_bytes(self):
        return self.ed.public_key().public_bytes_raw() + self.ml.public_key().public_bytes_raw()

    def public(self):
        return ALG + ":" + enc(self.public_bytes())

    def private(self):
        return ALG + ":" + enc(self.seed)

    def sign(self, message):
        # Pure Ed25519, and hedged ML-DSA-65 with an empty context.
        return self.ed.sign(message) + self.ml.sign(message)


def verify(public, signature, message):
    """Raises unless signature is public's signature of message. The
    algorithm comes from the trusted key, never from the signed data."""
    alg, _, data = public.partition(":")
    assert alg == ALG, "unknown key algorithm"
    raw = dec(data)
    assert len(raw) == ED_PUBLIC + 1952 and len(signature) == SIGNATURE_SIZE
    Ed25519PublicKey.from_public_bytes(raw[:ED_PUBLIC]).verify(signature[:ED_SIGNATURE], message)
    MLDSA65PublicKey.from_public_bytes(raw[ED_PUBLIC:]).verify(signature[ED_SIGNATURE:], message)


def lease_message(payload, alg=ALG, domain="v3"):
    return f"licensebox lease {domain}\n{alg}\n".encode() + payload


HOST_A = binding("12345678123456789abc1234567890ab")
HOST_B = binding("22345678123456789abc1234567890ab")
SIGNING = Key(bytes(range(64)))
PUBLIC = SIGNING.public()


def lease_payload(machine, host, now, *, product="demo", terms=1, version=3):
    value = {"v": version, "kid": "test-key", "product": product, "user": "synthetic-user", "email": "sdk@example.invalid",
             "machine": machine, "binding": host, "modules": ["core"], "issued": stamp(now), "expires": stamp(now+86400), "terms": terms}
    return json.dumps(value, separators=(",", ":"), ensure_ascii=False).encode()


def token(machine, host, now, *, product="demo", terms=1):
    payload = lease_payload(machine, host, now, product=product, terms=terms)
    return enc(payload) + "." + enc(SIGNING.sign(lease_message(payload)))


def lease_cases(install):
    """Leases and trusted keys that a verifier must refuse, and why."""
    payload = lease_payload(install.public(), HOST_A, START)
    good = SIGNING.sign(lease_message(payload))
    ed_only = Ed25519PrivateKey.from_private_bytes(bytes(range(32)))
    ed_public = enc(ed_only.public_key().public_bytes_raw())
    other = Key(bytes(range(64, 128)))
    mixed = ALG + ":" + enc(SIGNING.public_bytes()[:ED_PUBLIC] + other.public_bytes()[ED_PUBLIC:])
    v2 = lease_payload(enc(install.public_bytes()[:ED_PUBLIC]), HOST_A, START, version=2)

    def flip(i):
        bad = bytearray(good)
        bad[i] ^= 1
        return bytes(bad)

    def case(name, signature, error, keys=None, body=payload):
        return {"name": name, "token": enc(body) + "." + enc(signature), "keys": keys or {"test-key": PUBLIC}, "error": error}

    return [
        case("valid hybrid signature", good, None),
        case("Ed25519 half corrupted", flip(0), "bad_signature"),
        case("ML-DSA-65 half corrupted", flip(len(good) - 1), "bad_signature"),
        case("Ed25519 half only", good[:ED_SIGNATURE], "bad_signature"),
        case("ML-DSA-65 half only", good[ED_SIGNATURE:], "bad_signature"),
        case("truncated signature", good[:-1], "bad_signature"),
        case("signed under the v2 lease domain", SIGNING.sign(b"licensebox lease v2\n" + payload), "bad_signature"),
        case("signed under another algorithm name", SIGNING.sign(lease_message(payload, alg="ed25519")), "bad_signature"),
        case("ML-DSA-65 half of another key", good, "bad_signature", {"test-key": mixed}),
        case("v2 Ed25519 lease", ed_only.sign(b"licensebox lease v2\n" + v2), ["version", "bad_signature"], {"test-key": PUBLIC}, v2),
        case("trusted key is bare Ed25519", good, "malformed", {"test-key": ed_public}),
        case("trusted key is prefixed Ed25519", good, "malformed", {"test-key": "ed25519:" + ed_public}),
        case("trusted key has another algorithm", good, "malformed", {"test-key": "ed25519-mldsa44:" + PUBLIC.partition(":")[2]}),
        case("trusted key has no algorithm", good, "malformed", {"test-key": PUBLIC.partition(":")[2]}),
    ]


def build_vectors():
    install = Key(bytes(range(64, 128)))
    public = install.public()
    valid = token(public, HOST_A, START)
    message = f"licensebox device v3\n{ALG}\ndemo\n{HOST_A}\n{stamp(START)}"
    poll = f"licensebox token v3\n{ALG}\nsynthetic-device-1\n{HOST_A}\n{stamp(START)}"
    payload = '{"modules":["export"],"note":"café – test"}'
    call = f"licensebox request v3\n{ALG}\n{valid}\n{HOST_A}\n{stamp(START)}\n{hashlib.sha256(payload.encode()).hexdigest()}"
    vectors = {"protocol": 3, "revision": 2, "warning": "Public synthetic test keys only; never use these keys in production.",
               "note": "ML-DSA-65 signing is hedged, so regenerating changes every signature; all of them stay valid.",
               "algorithm": ALG, "keys": {"test-key": PUBLIC}, "now": START, "product": "demo",
               "installation_key": install.private(), "installation_public": public,
               "device_message": message, "device_signature": enc(install.sign(message.encode())),
               "poll_message": poll, "poll_signature": enc(install.sign(poll.encode())),
               "call_payload": payload, "call_message": call, "call_signature": enc(install.sign(call.encode())),
               "valid_lease": valid, "lease_cases": lease_cases(install),
               "bindings": [{"product": "demo", "source": source, "raw_id": raw,
                              "expected": binding(raw, source=source)}
                             for source, raw in [("linux-machine-id", "12345678123456789ABC1234567890AB\n"),
                                                 ("linux-dmi", "12345678-1234-5678-9abc-1234567890ab"),
                                                 ("macos-platform", "12345678-1234-5678-9abc-1234567890ab"),
                                                 ("windows-smbios", "12345678123456789abc1234567890ab"),
                                                 ("linux-device-tree", "0123456789abcdef\0")]]}
    return vectors


def unsigned(value):
    """value without its signatures, which hedged ML-DSA makes differ at
    every generation: signature fields, and the signature part of tokens."""
    if isinstance(value, dict):
        return {k: unsigned(v) for k, v in value.items() if not k.endswith("_signature")}
    if isinstance(value, list):
        return [unsigned(v) for v in value]
    if isinstance(value, str):
        return re.sub(r"([A-Za-z0-9_-]{20,})\.[A-Za-z0-9_-]{20,}", r"\1.", value)
    return value


def check_fixture(path, fresh, signed):
    """Checks that the committed fixture is what the generator makes, up to
    signatures, and that each signature in it, (key, signature, message) from
    signed, verifies."""
    committed = json.loads(path.read_text())
    assert unsigned(committed) == unsigned(fresh), f"{path.name} is stale: run --write-vectors"
    for public, signature, message in signed(committed):
        verify(public, signature, message)
    print(f"PASS: {path.name} matches its generator and its signatures verify", flush=True)


def lease_signature(public, token):
    payload, signature = token.split(".")
    return public, dec(signature), lease_message(dec(payload))


def vector_signatures(v):
    yield v["installation_public"], dec(v["device_signature"]), v["device_message"].encode()
    yield v["installation_public"], dec(v["poll_signature"]), v["poll_message"].encode()
    yield v["installation_public"], dec(v["call_signature"]), v["call_message"].encode()
    assert "\n" + v["valid_lease"] + "\n" in v["call_message"], "call_message names another lease"
    yield lease_signature(v["keys"]["test-key"], v["valid_lease"])
    for case in v["lease_cases"]:
        if case["error"] is None:
            yield lease_signature(case["keys"]["test-key"], case["token"])


class State:
    def __init__(self):
        self.now, self.mode, self.denial, self.limit, self.terms = START, "", "", 1, 1
        self.devices, self.machines, self.seats, self.revoked = {}, {}, [], set()
        self.device_count, self.renew_count, self.calls = 0, 0, 0
        self.requests, self.counts = [], {}


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *_):
        pass

    def answer(self, status, value):
        data = json.dumps(value, ensure_ascii=False, separators=(",", ":")).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def error(self, code, status=403):
        self.answer(status, {"error": code, "error_description": "Synthetic conformance refusal: " + code})

    def do_POST(self):
        state = self.server.state
        state.calls += 1
        if state.mode == "offline":
            self.error("unavailable", 503)
            return
        if state.mode == "nonjson403":
            self.send_response(403)
            self.end_headers()
            self.wfile.write(b"Forbidden")
            return
        try:
            size = int(self.headers.get("Content-Length", "0"))
            assert 0 < size <= 1 << 20
            request = json.loads(self.rfile.read(size))
            host, at = request["binding"], request["time"]
            when = datetime.fromisoformat(at.replace("Z", "+00:00")).timestamp()
            assert abs(state.now - when) <= 300
            assert host.startswith("m1:") and len(host.split(":")[2]) == 64
            if self.path == "/v1/device":
                machine = request["machine"]
                verify(machine, dec(request["signature"]), f"licensebox device v3\n{ALG}\n{request['product']}\n{host}\n{at}".encode())
                if host in state.revoked:
                    self.error("revoked")
                    return
                if machine in state.machines and state.machines[machine] != host:
                    self.error("machine_changed")
                    return
                state.device_count += 1
                code = "synthetic-device-" + str(state.device_count)
                state.devices[code] = request
                self.answer(200, {"device_code": code, "user_code": "TEST-CODE", "verification_uri": "https://example.invalid/activate",
                    "verification_uri_complete": "https://example.invalid/activate?code=TEST-CODE", "expires_in": 10, "interval_ms": 1, "interval": 1})
                return
            if self.path == "/v1/token":
                device = state.devices[request["device_code"]]
                assert device["binding"] == host
                machine = device["machine"]
                verify(machine, dec(request["signature"]), f"licensebox token v3\n{ALG}\n{request['device_code']}\n{host}\n{at}".encode())
                state.machines[machine] = host
                state.seats = [(key, b) for key, b in state.seats if b != host]
                state.seats.append((machine, host))
                if state.limit:
                    state.seats = state.seats[-state.limit:]
                self.answer(200, {"lease": token(machine, host, state.now, terms=state.terms), "usage": True})
                return
            kind = self.path.removeprefix("/v1/")
            lease_token, payload = request["lease"], request["payload"]
            lease_bytes, signature = lease_token.split(".")
            lease_value = json.loads(dec(lease_bytes))
            verify(PUBLIC, dec(signature), lease_message(dec(lease_bytes)))
            machine = lease_value["machine"]
            assert host == lease_value["binding"] == state.machines[machine]
            message = f"licensebox {kind} v3\n{ALG}\n{lease_token}\n{host}\n{at}\n{hashlib.sha256(payload.encode()).hexdigest()}"
            verify(machine, dec(request["signature"]), message.encode())
            if host in state.revoked:
                self.error("revoked")
                return
            if state.denial:
                self.error(state.denial)
                return
            if state.limit and (machine, host) not in state.seats:
                self.error("seat_transferred")
                return
            if lease_value["terms"] < state.terms:
                self.error("terms_changed")
                return
            body = json.loads(payload)
            if kind == "renew":
                state.renew_count += 1
                for count in body["usage"]:
                    old = state.counts.get(count["id"], {"ok": 0, "failed": 0, "ms": 0})
                    state.counts[count["id"]] = {k: max(old[k], count[k]) for k in old}
                if state.mode == "lost_ack":
                    self.error("unavailable", 503)
                    return
                result = token(machine, host, state.now, terms=state.terms)
                if state.mode == "bad_lease":
                    result = result[:-3] + "AAA"
                self.answer(200, {"lease": result, "usage": True})
            elif kind == "modules":
                self.answer(200, [{"name": "core", "free": True, "have": True}, {"name": "export", "description": "Export files", "have": False}])
            elif kind == "request":
                result = {"id": "synthetic-request", "modules": body["modules"], "note": body["note"], "status": "pending"}
                state.requests.append(result)
                self.answer(200, result)
            elif kind == "requests":
                self.answer(200, state.requests)
            elif kind == "access-link":
                self.answer(200, {"url": "https://example.invalid/access?token=synthetic"})
            else:
                self.error("invalid_request", 400)
        except Exception:
            self.error("invalid_signature", 401)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--write-vectors", action="store_true")
    parser.add_argument("--check-vectors", action="store_true")
    parser.add_argument("--adapter", nargs=argparse.REMAINDER)
    args = parser.parse_args()
    if args.write_vectors:
        (ROOT / "vectors.json").write_text(json.dumps(build_vectors(), ensure_ascii=False, indent=2) + "\n")
        return
    if args.check_vectors:
        check_fixture(ROOT / "vectors.json", build_vectors(), vector_signatures)
        return
    if not args.adapter:
        parser.error("--adapter COMMAND is required")
    vectors = json.loads((ROOT / "vectors.json").read_text())
    count = 0

    def run(request):
        process = subprocess.run(args.adapter, input=json.dumps(request), text=True, stdout=subprocess.PIPE,
                                 stderr=subprocess.PIPE, timeout=15)
        if process.returncode:
            # All values used by these adapters are synthetic. Do not include
            # requests or native bindings in failure diagnostics.
            raise RuntimeError(f"adapter operation {request['op']} exited {process.returncode}: {process.stderr}")
        return json.loads(process.stdout)

    def expect(request, error=None):
        nonlocal count
        result = run(request)
        if error:
            allowed = [error] if isinstance(error, str) else error
            assert not result["ok"] and result["error"] in allowed, f"{request['op']}: expected {error}, got {result.get('error', 'success')}"
        else:
            assert result["ok"], f"{request['op']}: {result.get('error')}"
        count += 1
        return result.get("value")

    for item in vectors["bindings"]:
        request = dict(item, op="derive")
        expected = request.pop("expected")
        assert expect(request) == expected, "native binding format mismatch"
    for raw in ["", "hostname", "0" * 32, "f" * 32]:
        expect({"op": "derive", "product": "demo", "source": "linux-machine-id", "raw_id": raw}, "identity_unavailable")
    verification = {"op": "verify", "token": vectors["valid_lease"], "product": "demo", "keys": vectors["keys"], "now": START}
    expect(verification)
    expect(dict(verification, now=START+86400), "expired")
    expect(dict(verification, product="another-product"), "malformed")
    expect(dict(verification, keys={"unknown": PUBLIC}), "unknown_key")
    damaged = vectors["valid_lease"][:-3] + "AAA"
    expect(dict(verification, token=damaged), "bad_signature")
    expect(dict(verification, token="bad"), "malformed")
    for case in vectors["lease_cases"]:
        try:
            expect(dict(verification, token=case["token"], keys=case["keys"]), case["error"])
        except AssertionError as error:
            raise AssertionError(f"lease case {case['name']!r}: {error}") from None
    native_a = expect({"op": "native", "product": "licensebox-conformance-a"})
    assert native_a == expect({"op": "native", "product": "licensebox-conformance-a"}), "native identity unstable across processes"
    assert native_a != expect({"op": "native", "product": "licensebox-conformance-b"}), "native identity is not product-scoped"
    print("PASS: wire vectors, hybrid lease verification and native identity (identifiers omitted)", flush=True)

    state = State()
    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    server.state = state
    worker = threading.Thread(target=server.serve_forever, daemon=True)
    worker.start()
    try:
        with tempfile.TemporaryDirectory(prefix="licensebox-conformance-") as temporary:
            directory = Path(temporary)
            base = {"product": "demo", "keys": {"test-key": PUBLIC}, "server": f"http://127.0.0.1:{server.server_port}", "now": START, "binding": HOST_A}

            def app(op, folder="a", **overrides):
                return expect(dict(base, op=op, directory=str(directory/folder), **overrides))

            def denied(op, code, folder="a", **overrides):
                return expect(dict(base, op=op, directory=str(directory/folder), **overrides), code)

            app("repeat")
            assert state.device_count == 1 and state.renew_count == 0, "sign-in did not cache its fresh lease"
            app("require")
            assert state.device_count == 1 and state.renew_count == 1, "fresh process did not silently renew"
            modules = app("modules")
            assert len(modules) == 2 and modules[1]["name"] == "export", "module discovery lost its response"
            request = app("request")
            assert request["note"] == "café – test", "Unicode signed payload mismatch"
            assert len(app("requests")) == 1, "request listing lost its response"
            assert app("access-link") == "https://example.invalid/access?token=synthetic", "access link lost its response"
            denied("require", "module_denied", module="export")
            app("record")
            state.mode = "lost_ack"
            app("require")
            state.mode = ""
            app("require")
            assert list(state.counts.values()) == [{"ok": 1, "failed": 1, "ms": 150}], "usage counts or retry identity changed"
            print("PASS: signed activation, renewal, modules, requests, access links and retry-safe usage", flush=True)

            state.mode = "offline"
            app("require")
            calls = state.calls
            app("status")
            assert state.calls == calls, "status contacted the server"
            denied("require", "offline", now=START+86401)
            denied("require", "offline")  # the saved clock must resist rollback
            state.mode = ""
            state.now = START + 45*86400
            base["now"] = state.now
            app("require")
            assert state.device_count == 1, "long idle period forced email sign-in"
            state.terms += 1
            app("require")
            assert state.device_count == 2, "changed terms did not require activation"
            print("PASS: offline expiry, clock rollback, long-idle renewal and changed terms", flush=True)

            for code in ("location_denied", "location_unknown", "seat_transferred", "machine_changed"):
                state.denial = code
                denied("require", code)
                state.denial, state.mode = "", "offline"
                denied("require", code)
                denied("status", code)
                state.mode = ""
                app("sign_in")
            state.mode = "nonjson403"
            denied("require", "http_error")
            state.mode = ""
            print("PASS: policy refusals persist across restart and offline use; non-JSON refusal fails closed", flush=True)

            for damaged in ("", "not-json"):
                (directory/"a"/"policy-denial").write_text(damaged)
                state.mode = "offline"
                for operation in ("require", "status"):
                    result = run(dict(base, op=operation, directory=str(directory/"a")))
                    assert not result["ok"], "damaged policy refusal restored offline access"
                    count += 1
                state.mode = ""
                app("sign_in")
            print("PASS: empty and damaged refusal state blocks offline access", flush=True)

            shutil.copytree(directory/"a", directory/"copied")
            calls = state.calls
            denied("require", "machine_changed", "copied", binding=HOST_B)
            assert state.calls == calls, "copied credentials contacted the server"
            state.mode = "offline"
            denied("require", "machine_changed", "copied", binding=HOST_B)
            state.mode = ""
            old_key = (directory/"copied"/"install.key").read_text()
            app("sign_in", "copied", binding=HOST_B)
            assert old_key != (directory/"copied"/"install.key").read_text(), "explicit activation reused the copied key"
            denied("require", "seat_transferred")
            app("sign_in")
            denied("require", "seat_transferred", "copied", binding=HOST_B)
            state.limit = 2
            app("sign_in", "copied", binding=HOST_B)
            app("sign_in", "reinstalled")
            assert len(state.seats) == 2 and {b for _, b in state.seats} == {HOST_A, HOST_B}, "reinstall displaced another native machine"
            state.revoked.add(HOST_A)
            denied("require", "revoked", "reinstalled")
            assert not (directory/"reinstalled"/"lease").exists(), "revocation retained the cached lease"
            denied("sign_in", "revoked", "reset-key")
            calls = state.calls
            denied("require", "identity_unavailable", "missing-identity", binding="")
            assert calls == state.calls, "missing identity started activation"
            app("logout", "copied", binding=HOST_B)
            assert not (directory/"copied"/"lease").exists() and (directory/"copied"/"install.key").exists(), "logout removed identity or kept a lease"
            print("PASS: credential-copy denial, explicit seat transfer, reinstall, native revocation and logout", flush=True)
    finally:
        server.shutdown()
        server.server_close()
    print(f"PASS: {count} shared conformance checks", flush=True)


if __name__ == "__main__":
    main()
