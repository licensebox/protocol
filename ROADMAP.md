# Application SDK catalog and maintenance roadmap

The first Linux rollout is released: 37 programming languages plus the shell CLI
and a host-assisted WebAssembly/WASI profile. Each full SDK passes the shared
69-scenario licensing suite and applicable build/install/lifecycle checks on
GitHub. JavaScript/TypeScript, JVM, .NET and BEAM languages share packages, with
separate language consumers validated. Source installation is available from
GitHub; do not assume language-registry publication.

| Family | Released languages/runtimes | Repositories |
| --- | --- | --- |
| Core | Go, Python 3, JavaScript, TypeScript, C, C++ | [go](https://github.com/licensebox/go), [python](https://github.com/licensebox/python), [javascript](https://github.com/licensebox/javascript), [c](https://github.com/licensebox/c), [cpp](https://github.com/licensebox/cpp) |
| Systems | Rust, Zig, Nim, D, Free Pascal / Object Pascal, COBOL | [rust](https://github.com/licensebox/rust), [zig](https://github.com/licensebox/zig), [nim](https://github.com/licensebox/nim), [d](https://github.com/licensebox/d), [pascal](https://github.com/licensebox/pascal), [cobol](https://github.com/licensebox/cobol) |
| JVM | Java, Kotlin, Scala, Clojure | [java](https://github.com/licensebox/java) |
| .NET | C#, F#, Visual Basic .NET | [dotnet](https://github.com/licensebox/dotnet) |
| Apple languages | Swift, Objective-C (Linux validation) | [swift](https://github.com/licensebox/swift), [objc](https://github.com/licensebox/objc) |
| Scientific | Fortran, R, Julia, GNU Octave, MATLAB R2025b | [fortran](https://github.com/licensebox/fortran), [r](https://github.com/licensebox/r), [julia](https://github.com/licensebox/julia), [octave](https://github.com/licensebox/octave), [matlab](https://github.com/licensebox/matlab) |
| Applications/scripting | Dart, Ruby, PHP, Lua/LuaJIT, Perl, Tcl, PowerShell | [dart](https://github.com/licensebox/dart), [ruby](https://github.com/licensebox/ruby), [php](https://github.com/licensebox/php), [lua](https://github.com/licensebox/lua), [perl](https://github.com/licensebox/perl), [tcl](https://github.com/licensebox/tcl), [powershell](https://github.com/licensebox/powershell) |
| Functional | Haskell, OCaml, Elixir, Erlang | [haskell](https://github.com/licensebox/haskell), [ocaml](https://github.com/licensebox/ocaml), [beam](https://github.com/licensebox/beam) |
| Shells | POSIX shell, Bash, Fish; PowerShell examples | [cli](https://github.com/licensebox/cli) |
| WASM/WASI | Native Python host using Wasmtime; browser-only unsupported | [wasm](https://github.com/licensebox/wasm) |

Exact compatible versions are in [contract.json](contract.json). Windows and
macOS runtime validation remain future work, including for Swift/Objective-C.
No release claims desktop-native identity for a standalone browser.

## Source preview

[Wolfram Language](https://github.com/licensebox/wolfram) is implemented but is a
clearly marked source preview. Its Java/native bridge compiles and passes
lifetime/callback tests; Wolfram evaluation and full runtime conformance remain
unvalidated. Do not publish a stable tag until those tests pass. Bridge-only CI
and automatic dependency PRs explicitly preserve that status.

## Keeping the rollout aligned

Follow [MAINTAINING.md](MAINTAINING.md) and [AGENTS.md](AGENTS.md). Add shared
regressions first, port affected independent cores, then test every consumer.
Metadata/dependency update PRs are automatic after successful checks; arbitrary
implementation translation, package publishing, PR approval and merging are not.
Administration stays in the Go CLI/web console. Native wrappers use the C core;
WASM/WASI uses the native Python client and an explicit host capability boundary.
Never copy private consuming applications, internal documents or server secrets
into these public source repositories.
