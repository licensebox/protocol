# SDK changes

This repository is the shared contract for every Licensebox application SDK.
Before changing a client, read SPEC.md, contract.json and MAINTAINING.md here.

- A wire, identity, persistence, authorization, offline, error, request or usage
  behavior change must add/update a shared conformance scenario and fixtures.
- Implement the corresponding change in every affected client. C++ inherits
  behavior from C; keep its C dependency pin current. Go-only admin CLI changes
  do not require language client ports.
- Run the complete shared suite against every implemented SDK listed in contract.json.
  A failing SDK is a release blocker. Do not weaken a test to make a port pass.
- Update contract.json's revision and compatibility map. The scheduled sync
  workflows propagate tested contract/dependency pins as PRs to each SDK repo.
  They do not translate arbitrary implementation changes or publish packages.
- Use pure Ed25519 from maintained crypto libraries. Preserve exact signed bytes.
  Never substitute random/hostname/network IDs for missing native identity.
- Keep client code public and server secrets private. Tests use synthetic keys,
  addresses and hosts only. Never copy Edgewise source, internal documents,
  references, product data, tokens or production keys into any SDK repository.
- Linux is the initial validated platform. Document untested/unsupported OS and
  runtime paths honestly. Browser/WASM needs a separately reviewed host identity
  profile; it must not claim desktop-native machine recognition.
- Before release, pass conformance, package/install checks and applicable native
  and memory/race checks. Use existing crypto; no homemade signing primitives.
