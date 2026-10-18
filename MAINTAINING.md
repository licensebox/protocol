# Keeping the SDKs aligned

## A client change

1. Add a regression scenario here for changed licensing behavior. Update SPEC.md
   and deterministic vectors when wire bytes or native binding rules change.
2. Implement the change in every affected SDK. Run the shared suite locally.
   Keep administration in the Go CLI; do not duplicate admin functionality merely
   because an application SDK is added.
3. Increment contract.json's revision and record compatible SDK releases. A wire
   breaking change also changes the protocol/signature domains and requires a
   coordinated server/consumer rollout. A protocol revision is not a server
   deployment instruction.
4. Merge only after Linux checks pass for all affected clients. The Go reference
   check runs here, and each SDK runs the same fixture/server harness.
5. Each SDK's hourly sync workflow finds the new contract commit, tests it, and
   opens a PR updating protocol-lock.json and the applicable native/host dependency
   pins. Run the sync workflow manually when immediate propagation is needed.
6. Review implementation changes and compatibility PRs; publish language packages
   only after checks pass. Registry publishing is deliberately separate from
   compatibility sync. This avoids releasing a broken translation automatically.

## Automation permissions

The workflow uses only the repository's own GITHUB_TOKEN. Test jobs have read-only
permissions and checkout does not persist credentials. The separate PR job has
contents, pull-request and actions write access in that repository only. Actions
write permission dispatches the test workflow explicitly after the bot creates
a PR; GitHub-token-created PR workflows can otherwise require manual approval.
No workflow auto-approves or auto-merges a PR.

Invoke the metadata publisher as `python3 -B .github/scripts/open_sync_pr.py`.
The registry import must not create Python bytecode in the fresh checkout: the
publisher deliberately rejects every unexpected untracked file. Keep this guard
strict rather than ignoring artifacts created by the publisher itself. The
isolated `scripts/test_publisher.py` regression exercises the real entry point,
no-op startup and rejection of unexpected files/source edits without GitHub
access.

Enable the repository setting allowing Actions to create PRs. GitHub exposes this
as the combined “Allow GitHub Actions to create and approve pull requests” setting;
the bot never invokes review approval. Keep the default token permission read.
An organization policy may prevent enabling this; surface that failure rather
than introducing an unreviewed PAT.

The protocol repository's scheduled release watcher opens a compatibility PR
when an SDK publishes a new stable release. Updating a compatibility map cannot
prove an untested implementation correct. Add the shared regression scenario
before the release, and use the same scenarios to verify each port.

References: [GitHub token event behavior](https://docs.github.com/en/actions/concepts/security/github_token)
and [repository workflow permissions](https://docs.github.com/en/rest/actions/permissions).

## Local development

Use a source checkout for the adapter you are testing. The Python/Node adapters
live in their tests folders; the C/C++ adapters are CMake build targets. Native
tests read the current host identity but never print it. Adapter clock/binding
overrides are synthetic test seams, not command-line bypasses in SDK products.

To compare an unpublished Go change, replace the Go adapter's licensebox.dev
dependency with a local SDK checkout before building; never commit the local
path. A go.work file is ignored for this purpose. Production apps resolve a
published SDK release.

## Language families and shared implementations

`contract.json` is the authoritative list of released clients and approved source
previews. Java/Kotlin/Scala/Clojure share the Java library; C#/F#/VB.NET share the
managed .NET assembly; Erlang/Elixir share the BEAM native resource. JavaScript
and TypeScript share the Node package. Validate each language consumer, not just
the underlying library. Their CI runs separate executable adapters.

Most additional native bindings depend on the pinned C JSON ABI. When licensing
behavior changes, port the Go, Python, Node and C implementations, then rebuild
and run **every registered consumer**. C++ and native language bindings inherit
C behavior; wrappers still need review for argument conversion, ownership,
callback lifetimes and errors. Update the C release in the compatibility map
only after core checks pass. Scheduled SDK PRs update `native-version.txt` (or
C++'s `c-version.cmake`) after each consumer's actual tests succeed.

The Wasmtime/WASI profile keeps identity, storage and licensing in a native
Python host. Its tested metadata update also changes `host-dependencies.txt`.
Do not add browser fingerprints or guest-controlled identity/clock overrides.
A host-assisted profile is not a claim of standalone browser support.

A source preview has a separate `previews` entry and explicitly labeled bridge
checks. Those checks do not prove the target language runtime works. Its lock
and update PR retain `bridge-only-unvalidated`; the full runtime test scripts
remain mandatory before promotion. Never publish a stable SDK tag based only
on bridge compilation.

## Reproduce a consumer check

For native profiles, install the C release specified in `native-version.txt`,
set `LICENSEBOX_LIB_DIR`, `LICENSEBOX_LIBRARY` and `LD_LIBRARY_PATH`, then run
`bash ci/test.sh`. `ci/setup.sh` is for disposable Ubuntu GitHub runners, not an
automatic workstation installer. Run the shared suite from the protocol checkout:

```sh
python3 conformance/run.py --adapter bash ../SDK/ci/adapter.sh
```

Keep compiler versions, package consumers and lifecycle/callback checks in the
SDK's own `ci/test.sh`. MATLAB's official public-runner job uses one licensed
session and a test-only file transport, with fresh clients and persistent
credential files. Its local batch adapter also tests separate MATLAB processes.
MATLAB and Octave additionally run `conformance/mex_strings.py`; TLS-capable
native adapters can run `conformance/tls_transport.py` with synthetic roots.
All fixtures are synthetic. Never use an administrator token, production signing
key, customer account or private consuming application to make tests pass.
