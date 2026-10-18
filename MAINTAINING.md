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
   opens a PR updating protocol-lock.json. For C++, it also updates the C release
   pin. Run the sync workflow manually when immediate propagation is needed.
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
