# Licensebox SDK contract

The shared protocol, deterministic test vectors and behavioral conformance suite
for [Licensebox](https://licensebox.dev) application clients. Administration stays
in the [Go admin CLI](https://github.com/licensebox/go).

| Language | Repository |
| --- | --- |
| Go | [licensebox/go](https://github.com/licensebox/go) |
| Python 3 | [licensebox/python](https://github.com/licensebox/python) |
| JavaScript and TypeScript (Node.js) | [licensebox/javascript](https://github.com/licensebox/javascript) |
| C | [licensebox/c](https://github.com/licensebox/c) |
| C++17 | [licensebox/cpp](https://github.com/licensebox/cpp) |

The first client batch is validated on Linux. C++ wraps the C implementation.
Java, Rust, Pascal, .NET and a host-assisted WASM profile are planned; repositories
are created when their implementations are ready. Browser WASM cannot obtain the
native identity used by these desktop clients. It must not silently fall back
to a browser-generated installation ID.

## Run the contract

Python 3.10+ and `cryptography>=43` run the mock server. An adapter is a small
program reading one JSON request on stdin and writing one JSON result on stdout.
The SDK directories contain their adapters. For example:

```sh
python3 -m pip install 'cryptography>=43'
PYTHONPATH=../python/src python3 conformance/run.py --adapter python3 ../python/tests/adapter.py
python3 conformance/run.py --adapter node ../javascript/test/adapter.mjs
python3 conformance/run.py --adapter ../c/build/licensebox-adapter
python3 conformance/run.py --adapter ../cpp/build/licensebox-cpp-adapter
```

The suite tests signed activation and token polling, exact UTF-8 payload proofs,
lease signatures, product and key selection, native binding format, native Linux
identity stability, process-level renewal, offline expiry, clock rollback, long
idle periods, changed terms, module access, requests, access links, cumulative
usage retry IDs, persistent policy refusals, credential copies, explicit seat
transfer, reinstall, revocation and logout.

All test keys, email addresses, user codes and identifiers are **public synthetic
fixtures**. Never use them in a real product. The suite listens only on loopback;
it does not connect to production, send mail, or use personal credentials. Native
test outputs are compared in memory without printing the host's binding.

## Updates across repositories

`contract.json` is the current protocol revision and release compatibility map.
Each SDK pins this repository by commit in `protocol-lock.json`. Its scheduled
sync workflow checks for a newer reviewed contract, runs the SDK's full
conformance suite against it, then opens an update PR. No cross-repository PAT is
needed: each repository uses its own scoped GitHub Actions token.

The protocol repository watches SDK releases and opens a compatibility update PR.
Go behavior changes must include shared scenarios here; changing a Go source file
cannot safely translate an implementation into every language. A mismatch blocks
the update. Implement the corresponding change in each affected SDK and rerun the
same test before release. See [AGENTS.md](AGENTS.md) and [MAINTAINING.md](MAINTAINING.md).

No SDK release publishes private server code or consuming applications' source,
documentation, credentials or signing keys.

MIT. Copyright © 2026 [Vijai Kumar](https://meshing.engineer).
