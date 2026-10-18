# Initial SDK validation

The first batch targets Linux. Each SDK passes the same 69 behavioral checks,
using synthetic local records and public test keys. Runtime tests read the host's
native identity only to compare stability and product separation; no identifier
is printed, uploaded or used in a production licence.

Before publishing a client release:

- Run its Linux CI and the complete conformance suite against the intended
  contract commit. Go additionally runs `go test -race ./...`.
- For Python, build a wheel and install/import it outside the source checkout.
- For Node, `npm pack`, then install the tarball in a separate application and
  import its JavaScript exports. Ensure TypeScript declarations are included.
- For C/C++, run the suite with AddressSanitizer and UndefinedBehaviorSanitizer.
  Also install a release build into a separate prefix and compile/run a small
  downstream CMake consumer using `find_package` and exported library targets.
- Check package contents: only that SDK's public code, licence and intended
  metadata/docs belong in its package. Never include credentials, build caches,
  internal application documentation or consuming products' files.

The initial release completed those checks locally and ran the shared suite on
GitHub-hosted Linux runners. macOS/Windows runtime validation remains pending;
language READMEs distinguish implemented adapters from unsupported platforms.
Virtual machines, copied native IDs and modified host software remain limits of
software-based machine recognition. This is not hardware attestation.
