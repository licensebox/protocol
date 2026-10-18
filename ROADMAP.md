# Application SDK roadmap

Ship usable clients with documentation, install checks, shared conformance and
tested update PRs. Do not create empty repositories for languages we cannot yet
validate. Linux is the first runtime target; other platform support needs its
own tests. All releases keep private consuming applications and server data out.

| Family | Targets | Implementation |
| --- | --- | --- |
| Existing | Go, Python 3, JavaScript, TypeScript, C, C++ | Published SDKs |
| Current batch | Rust, Java, Julia, C# | Native C bindings; validation/release in progress |
| JVM | Kotlin, Scala, Clojure | Share Java core; add language-specific APIs/examples and tests |
| .NET | F#, Visual Basic .NET | Share managed C# core; compile and test in each language |
| Apple | Swift, Objective-C | Native bindings; Linux validation first where available |
| Scientific | Fortran, R, MATLAB, GNU Octave, Wolfram Language | Native bindings; proprietary runtimes need available validation |
| Applications | Dart, Ruby, PHP | Native bindings |
| Systems | Zig, Nim, D, Free Pascal / Object Pascal | Native bindings |
| Functional | Haskell, OCaml, Elixir, Erlang | Native bindings or a safe managed worker transport |
| Embedded/scripting | Lua, Perl, Tcl, PowerShell | Native bindings or the common licensing CLI |
| Legacy | COBOL | Native C interop |
| Shells | Bash and other shells | Dedicated client CLI; no shell crypto/storage implementation |
| Runtime targets | WebAssembly / WASI | Separate host-assisted identity interface; browser IDs are insufficient |

Administration remains in the Go CLI/web console. The C JSON/FFI surface is a
convenience layer over the typed C client, not a second licensing implementation.
Every binding must preserve callback lifetimes, native allocation ownership,
fail-closed errors and explicit cleanup, and pass the same behavioral scenarios.
