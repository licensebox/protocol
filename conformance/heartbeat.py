#!/usr/bin/env python3
"""Optional heartbeat contract; public synthetic keys, identities and records only."""
import argparse
from http.server import ThreadingHTTPServer
import json
from pathlib import Path
import subprocess
import tempfile
import threading
import run as wire

ORIGINAL_TOKEN = wire.token
POLICY = {"interval_seconds": 30, "grace_seconds": 90}


def signed(value):
    payload = json.dumps(value, separators=(",", ":"), ensure_ascii=False).encode()
    return wire.enc(payload) + "." + wire.enc(wire.SIGNING.sign(b"licensebox lease v2\n" + payload))


def value(machine, host, now=wire.START, *, heartbeat=POLICY, modules=None, terms=1):
    lease = json.loads(wire.dec(ORIGINAL_TOKEN(machine, host, now, terms=terms).split(".")[0]))
    if heartbeat is not None:
        lease["heartbeat"] = heartbeat
        lease["expires"] = wire.stamp(now + (heartbeat.get("grace_seconds", 90) if isinstance(heartbeat, dict) else 90))
    if modules is not None:
        lease["modules"] = modules
    return lease


class Handler(wire.Handler):
    def do_POST(self):
        state = self.server.state
        if self.path == "/heartbeat-redirect-target":
            state.redirect_leaks += 1
            self.send_error(403)
            return
        if self.path == "/v1/renew" and state.mode == "redirect307":
            state.calls += 1
            self.send_response(307)
            self.send_header("Location", "/heartbeat-redirect-target")
            self.end_headers()
            return
        if self.path == "/v1/renew" and state.renew_count:
            if state.mode == "seat-second":
                state.denial = "seat_transferred"
            elif state.mode == "terms-second":
                state.terms = 2
            elif state.mode == "module-second":
                state.modules = []
        super().do_POST()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--adapter", nargs=argparse.REMAINDER, required=True)
    args = parser.parse_args()
    total = 0

    def request(r, error=None):
        nonlocal total
        process = subprocess.run(args.adapter, input=json.dumps(r), text=True,
                                 capture_output=True, timeout=20)
        assert process.returncode == 0, f"adapter {r['op']} exited {process.returncode}: {process.stderr}"
        answer = json.loads(process.stdout)
        if error:
            assert answer.get("ok") is False and answer.get("error") == error, f"{r['op']}: expected {error}, got {answer.get('error', 'success')}"
        else:
            assert answer.get("ok") is True, f"{r['op']}: {answer.get('error')}"
        total += 1
        return answer.get("value")

    seed = bytes(range(32, 64))
    key = wire.Ed25519PrivateKey.from_private_bytes(seed)
    machine = wire.enc(key.public_key().public_bytes_raw())
    verify = {"op": "verify", "product": "demo", "keys": {"test-key": wire.PUBLIC}, "now": wire.START}
    valid = value(machine, wire.HOST_A)
    checked = request(dict(verify, token=signed(valid)))
    assert checked["heartbeat"] == POLICY, "signed heartbeat policy was lost"
    absent = value(machine, wire.HOST_A, heartbeat=None)
    request(dict(verify, token=signed(absent)))
    request(dict(verify, token=signed(dict(absent, heartbeat=None))))
    bad_policies = [False, [], "30", {}, {"interval_seconds": 0, "grace_seconds": 0},
                    {"interval_seconds": 29, "grace_seconds": 90},
                    {"interval_seconds": 86401, "grace_seconds": 90000},
                    {"interval_seconds": 30, "grace_seconds": 29},
                    {"interval_seconds": 30, "grace_seconds": 31536001},
                    {"interval_seconds": True, "grace_seconds": 90},
                    {"interval_seconds": 30.5, "grace_seconds": 90},
                    {"interval_seconds": "30", "grace_seconds": 90},
                    {"interval_seconds": 30, "grace_seconds": "90"}]
    for policy in bad_policies:
        request(dict(verify, token=signed(dict(valid, heartbeat=policy))), "malformed")
    request(dict(verify, token=signed(dict(valid, expires=wire.stamp(wire.START + 91)))), "malformed")
    print("PASS: optional signed heartbeat policy types, limits and contact deadline", flush=True)

    state = wire.State()
    state.modules = ["core"]
    state.heartbeat = dict(POLICY)
    state.machines[machine] = wire.HOST_A
    state.seats = [(machine, wire.HOST_A)]
    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    server.state = state
    base = {"product": "demo", "keys": {"test-key": wire.PUBLIC}, "binding": wire.HOST_A,
            "now": wire.START, "server": f"http://127.0.0.1:{server.server_port}", "module": "core"}
    def issue(machine_, host, now, *, product="demo", terms=1):
        return signed(value(machine_, host, now, heartbeat=state.heartbeat, modules=state.modules, terms=terms))
    wire.token = issue
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        with tempfile.TemporaryDirectory(prefix="licensebox-heartbeat-") as temp:
            root = Path(temp)
            def prepare(name, lease_value=valid):
                state.mode, state.denial, state.terms, state.modules = "", "", 1, ["core"]
                state.revoked.clear()
                state.renew_count = state.calls = state.device_count = 0
                state.now = wire.START
                state.redirect_leaks = 0
                directory = root/name
                directory.mkdir(mode=0o700)
                (directory/"install.key").write_text(wire.enc(seed)+"\n")
                if lease_value is not None:
                    (directory/"lease").write_text(signed(lease_value)+"\n")
                return dict(base, directory=str(directory))
            def call(r, op="heartbeat", error=None, **overrides):
                return request(dict(r, op=op, **overrides), error)

            r = prepare("missing", None)
            call(r, error="not_signed_in")
            assert state.calls == state.device_count == 0, "heartbeat started interactive sign-in"
            r = prepare("missing-key")
            key_path = Path(r["directory"])/"install.key"
            key_path.unlink()
            call(r, error="not_signed_in")
            assert not key_path.exists() and state.calls == state.device_count == 0, "heartbeat created a replacement identity"
            r = prepare("redirect")
            state.mode = "redirect307"
            call(r, error="http_error")
            assert state.redirect_leaks == 0, "heartbeat forwarded signed renewal credentials to a redirect"
            r = prepare("force")
            out = call(r, "heartbeat-repeat")
            assert state.renew_count == 2 and out["online"] is True and out["lease"]["heartbeat"] == POLICY, "heartbeat reused cached success"
            assert state.device_count == 0
            r = prepare("after-require")
            call(r, "heartbeat-after-require")
            assert state.renew_count == 2, "Require cache bypassed heartbeat contact"
            r = prepare("offline")
            state.mode = "offline"
            out = call(r)
            assert out["online"] is False and out["lease"]["expires"] == valid["expires"], "outage extended the contact deadline"
            state.now = wire.START + 90
            call(r, error="offline", now=state.now)
            assert state.device_count == 0, "expired offline heartbeat started sign-in"
            r = prepare("expired")
            state.now = wire.START + 100
            out = call(r, now=state.now)
            assert out["online"] is True, "expired trusted identity failed silent renewal"
            assert state.device_count == 0
            print("PASS: forced contact, no interactive activation, bounded offline fallback and silent renewal", flush=True)

            r = prepare("removed-module")
            state.mode = "module-second"
            call(r, "heartbeat-after-require", error="module_denied")
            out = call(r, "status")
            assert "core" not in out["modules"], "removed module survived in the cached authorization"
            r = prepare("seat")
            state.mode = "seat-second"
            call(r, "heartbeat-after-require", error="seat_transferred")
            assert state.device_count == 0
            state.mode, state.denial = "offline", ""
            call(r, error="seat_transferred")
            state.mode = ""
            call(r)
            state.mode = "offline"
            assert call(r)["online"] is False, "successful heartbeat failed to clear saved refusal"
            r = prepare("terms")
            state.mode = "terms-second"
            call(r, "heartbeat-after-require", error="terms_changed")
            assert state.device_count == 0, "heartbeat accepted changed terms through interactive sign-in"
            r = prepare("http-refusal")
            state.mode = "nonjson403"
            call(r, error="http_error")
            r = prepare("revoked")
            state.revoked.add(wire.HOST_A)
            call(r, error="revoked")
            assert not (Path(r["directory"])/"lease").exists(), "revocation retained the lease"
            r = prepare("copied")
            call(r, error="machine_changed", binding=wire.HOST_B)
            assert state.calls == 0, "copied credentials contacted the server"
            r = prepare("damaged-refusal")
            (Path(r["directory"])/"policy-denial").write_text("")
            state.mode = "offline"
            process = subprocess.run(args.adapter, input=json.dumps(dict(r, op="heartbeat")),text=True,capture_output=True,timeout=20)
            assert process.returncode == 0 and json.loads(process.stdout).get("ok") is False, "damaged refusal restored offline authorization"
            total += 1
            assert state.device_count == 0
            print("PASS: changed grants, persisted refusals, terms, revocation and machine binding remain fail closed", flush=True)
    finally:
        wire.token = ORIGINAL_TOKEN
        server.shutdown()
        server.server_close()
    print(f"PASS: {total} shared heartbeat checks", flush=True)


if __name__ == "__main__":
    main()
