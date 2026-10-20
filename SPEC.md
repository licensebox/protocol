# Application protocol v3

API endpoint paths retain `/v1`. The lease and signature domains use v3. All
requests are JSON over HTTPS. HTTP is permitted only on loopback for development.
Do not follow redirects with signed bodies. Native transports may accept an explicit
CA certificate PEM bundle for environments whose TLS library lacks a default
trust store. This never disables certificate-chain or hostname verification. Public keys are administrator-provided
and carry their algorithm (below). Installation private keys never leave the host.
Product signing keys and admin credentials never belong in an application client.

Protocol v3 is a clean break from v2: v2 keys, leases, installation keys and
signatures are refused. There is no compatibility path.

## Keys and signatures

Every signature, by a product key or an installation key, uses one algorithm,
`ed25519-mldsa65`: Ed25519 (RFC 8032) and ML-DSA-65 (FIPS 204) over the **same
message bytes**. A signature is valid only if **both** halves verify, so it
stays unforgeable if either algorithm or one implementation of it is broken.
Parts are fixed-length concatenations, Ed25519 first:

| | Ed25519 | ML-DSA-65 | `ed25519-mldsa65` |
| --- | --- | --- | --- |
| public key | 32 B | 1952 B | `ed25519_pk ‖ mldsa_pk` = 1984 B |
| signature | 64 B | 3309 B | `ed25519_sig ‖ mldsa_sig` = 3373 B |
| private key | 32 B seed | 32 B seed (ξ) | `ed25519_seed ‖ mldsa_seed` = 64 B |

- Ed25519 is pure Ed25519, without prehashing. ML-DSA-65 is pure ML-DSA with an
  **empty context**, signed hedged (randomized, the default); verifiers accept
  any valid signature. Keep only seeds; expand ML-DSA keys from the seed.
- A key is written `<alg>:<unpadded base64url>`, for example
  `ed25519-mldsa65:AAAA…` (2,662 characters for a public key). A missing,
  unknown or differently cased algorithm, or a wrong length, is malformed:
  refuse it, never fall back to treating the bytes as an Ed25519 key.
- **The verifier takes the algorithm from the trusted key, never from a token
  or request.** Leases carry no algorithm field. A signature of the wrong length
  for the key's algorithm is a bad signature.
- Every signed message names the algorithm, so a signature is never checked
  under a different algorithm than it was made with.
- A future algorithm is a new `<alg>` value implemented in each SDK; the wire
  format does not change.

The construction is deliberately the plain one above, not the
[IETF composite signature](https://datatracker.ietf.org/doc/draft-ietf-lamps-pq-composite-sigs/)
message representative: licensebox uses no X.509 tooling, the domain prefixes
already separate every message, and naming the algorithm in each message binds
both halves to it.

## Exact signature bytes

Times below are UTC RFC 3339, truncated to seconds, for example
`2026-10-18T12:00:00Z`. The server permits five minutes of skew. Encoding is UTF-8;
`\n` denotes one LF byte. Hash output is lowercase hex. `alg` is the signing key's
algorithm, `ed25519-mldsa65`. Signatures use unpadded base64url.

```text
lease  = "licensebox lease v3\n"  + alg + "\n" + original payload bytes
device = "licensebox device v3\n" + alg + "\n" + product + "\n" + binding + "\n" + time
poll   = "licensebox token v3\n"  + alg + "\n" + device_code + "\n" + binding + "\n" + time
call   = "licensebox " + kind + " v3\n" + alg + "\n" + lease + "\n" + binding + "\n" + time + "\n" + hex(SHA256(payload))
```

`payload` is a JSON **string** in the signed call envelope. Hash its exact UTF-8
bytes, including any escaping or whitespace, and transmit those same bytes in
the string. No canonical JSON reserialization is performed by the verifier.

## Activation

Generate an `ed25519-mldsa65` installation key, retained across process restarts. Derive the
native binding before contacting the server. Missing identity refuses activation.

`POST /v1/device` has `product`, `machine` (installation public key, `<alg>:<base64url>`), `binding`,
`os`, `arch`, `version`, `time`, `signature`. The result has `device_code`,
`user_code`, `verification_uri`, `verification_uri_complete`, `expires_in`,
`interval`, optionally `interval_ms`. Display the URI and user code or call the
application's sign-in callback. Never log a lease or the private device code.

After the interval, `POST /v1/token` with `device_code`, `binding`, `time`,
`signature`. Sign polling with the initiating installation key. Handle
`authorization_pending` by waiting, `slow_down` by adding five seconds, and
`expired_token`/`access_denied` by stopping. Respect timeout/cancellation. Retry
transport errors and server outages only until the device code expires.

Success returns `{ "lease": "...", "usage": true|false }`. Verify the complete
lease and both identities before saving. Completed activation may transfer a
seat; ordinary renewal must never activate again merely to steal a seat back.

## Signed operations

The envelope contains `lease`, `binding`, `time`, `payload`, `signature`, `version`.
The kind matches the final endpoint component:

| Kind | Payload | Result |
| --- | --- | --- |
| `renew` | `{"usage": [...]}` | fresh lease and usage collection flag |
| `modules` | `{}` | module objects (`name`, `description`, `free`, `have`, `requested`) |
| `request` | `{"modules":["export"],"note":"..."}` | request object |
| `requests` | `{}` | user's requests |
| `access-link` | `{}` | `{ "url": "..." }`, a short-lived private access link |

Request results include `id`, `modules`, `note`, `status` and, when answered,
`granted`, `until`, `answer`, `answered`. Treat access links as credentials.

## Lease verification

A token is `base64url(payload) + "." + base64url(signature)`. Verify the signature
with the trusted key over the lease message above: `"licensebox lease v3\n"`, the
key's algorithm and `"\n"`, then the **original decoded payload bytes**.
Fields are `v=3`, `kid`, `product`, `user`, `email`, `machine`, `binding`, `modules`,
`issued`, `expires`, `terms`. Refuse any `v` other than 3. Select only a trusted key by `kid`; match the product,
current installation public key and current native binding. Parsing JSON alone
never authorizes an operation. Do not grant a module absent from `modules`.

The first protected call in every new process silently attempts renewal with a
three-second bound. A successfully renewed lease may be reused within that
process until expiry. Transport failures and 5xx outages may use a verified,
unexpired cached lease. Once expired, return `offline`; expiry alone must not
require email authentication, even after months of inactivity. A changed terms
version or invalid/retired signing key can require activation again.

Explicit 3xx/4xx refusals must not become offline fallback, including HTML/non-JSON
responses. Persist `machine_changed`, `seat_transferred`, `location_denied` and
`location_unknown` before returning, and refuse cached offline use afterward.
A saved refusal that is empty, unreadable or malformed must also block cached
offline access. Connect and successfully renew or explicitly sign in to recover;
do not interpret corrupted refusal state as an absent policy decision.
A successful renewal or explicit sign-in clears the persisted refusal. On
`revoked`, discard the lease and queued usage. Do not automatically transfer a
seat after `seat_transferred`. Check access before reading or processing user
files. A command-start check does not create a background heartbeat.

## Optional heartbeat checks

A product may configure `heartbeat` as
`{"interval_seconds":300,"grace_seconds":900}`. Zero/zero disables it (the
initial default). Enabled values are integers: interval 30–86,400 seconds and
grace at least the interval, at most 31,536,000 seconds. Omitted product settings
preserve the existing policy; an explicit zero object disables it.

An enabled policy appears in the signed lease's optional `heartbeat` object.
Missing or null means no policy. A present object MUST contain valid enabled
values. Its `expires` MUST be after `issued` and no later than `issued + grace`;
normal offline and grant limits can shorten it further. The server omits the
field when disabled. This additive field preserves v2 signature domains and
original signed bytes. Earlier clients already enforce the shorter expiry.

Every SDK exposes an explicit, synchronous `Heartbeat(module)` operation with
idiomatic naming. Its result is `{"lease": <verified lease>, "online": true|false}`.
The module is mandatory and nonempty. The C JSON operation is `heartbeat` with
`{"module":"core"}`. The operation MUST attempt signed `/v1/renew`, bounded to
three seconds, even when the process has a fresh lease. It MUST verify the
renewed lease, replace cached authorization before checking the requested
module, and preserve usage acknowledgement, identity and refusal rules.

Heartbeat MUST NOT start interactive sign-in, create or rotate an installation
key, or transfer a seat. A missing saved lease or existing key returns
`not_signed_in`; damaged credentials retain their verification error. An expired
trusted lease may silently renew. Public key and current native binding MUST be
checked before server contact. Never follow redirects carrying signed requests.

Eligible transport failures and 5xx outages may return an otherwise valid,
unexpired saved lease with `online=false`. They MUST NOT extend its expiry or
clear a saved refusal. Recheck time after a failed request. Parent cancellation,
explicit 3xx/4xx and policy refusals never permit offline fallback. Known refusal
headers remain authoritative when reading the response body fails or times out. Revocation
discards the lease and usage. Changed terms and invalid leases return an error
without interactive activation. Successful renewal clears saved refusal state;
removed modules return `module_denied`, without preserving the old grant.

Scheduling is consumer-owned. Client construction and ordinary command-start
checks do not start a background task. Optional monitor helpers MUST be started
explicitly and cleaned up when work finishes. A monitor uses the signed interval
(or a faster caller choice) and independently enforces the last signed expiry,
even while HTTP or an observer callback is blocked. It signals cancellation or
failure; the application decides how to checkpoint or stop its work. It never
terminates the process automatically. Native bindings may expose only the
primitive so consumers retain their runtime's scheduling and callback rules.

## Native binding m1

Use exactly the sources and normalization described in the
[machine identity guide](https://github.com/licensebox/go/blob/main/docs/machine-identity.md).
Linux prefers readable DMI UUID, then device-tree serial, then machine-id/DBus.
Windows uses raw SMBIOS Type 1 UUID bytes; macOS uses IOPlatformUUID. No random,
hostname, network address, MAC or browser identifier substitutes for native IDs.

Normalize terminal NUL bytes and surrounding whitespace, lowercase, remove UUID
hyphens. Require hex: 16 decoded bytes for UUID/machine-id sources, 8–32 for
device-tree serials. Reject all-zero/all-FF values. Raw IDs stay local.

```text
key     = SHA256(UTF8("licensebox machine binding v1\n" + product))
digest  = HMAC_SHA256(key, UTF8(source + "\n" + canonical_identifier))
binding = "m1:" + source + ":" + lowercase_hex(digest)
```

Sources are `linux-dmi`, `linux-device-tree`, `linux-machine-id`, `windows-smbios`,
`macos-platform`. Binding namespace m1 is distinct from signature format v3.
The derivation key is public namespace material, not hardware attestation. Full
VM clones, spoofed native IDs or modified host software remain limitations.

Copying credentials to another native identity refuses both online and offline
use before server contact. Explicit sign-in there rotates the copied key. New
keys on unchanged native identity replace that host's seat; revocation follows
the product/native binding. The server remains authoritative for allocation and
country/city/radius restrictions based on trusted ingress metadata.

## Storage and usage

Default Linux directory: `$XDG_CONFIG_HOME/licensebox/<product>` or
`$HOME/.config/licensebox/<product>`. The product directory is private (0700),
files 0600, writes atomic. `install.key` is `ed25519-mldsa65:` and the unpadded
base64url 64-byte seed pair. A v2 key file (a bare 32-byte seed) is malformed. `lease` holds
the signed token; `seen` holds the latest observed UTC time. Retain this latest
time across restarts so rolling the wall clock back cannot revive an already
observed expired lease. `policy-denial` is JSON with `code` and `detail`.
Logout retains the key and saved clock, removing the lease, denial and usage.
Coordinate simultaneous key creation so processes use the same installation key.

Collect usage only after `usage=true`. `usage.json` queues cumulative counts by
`id` (random 16-byte lowercase hex), `day`, fixed `command`, `version`, `os`, `ok`,
`failed`, `ms`. Reuse each ID across retries. Drop an acknowledged count only if
its cumulative values have not changed. Bound to 1,000 queued counts and send at
most 100 per renewal. Never send filenames, arguments, file data or geometry.

## Sizes

A lease is about 8 KB: its payload (~3.2 KB) carries the 2.7 KB installation
public key, and the signature is 4.5 KB in base64url. Signed calls carry the
lease, so request bodies are about 10 KB. Keep a product public key in a file or
constant rather than inline in configuration.

## Crypto implementation references

- [FIPS 204, ML-DSA](https://nvlpubs.nist.gov/nistpubs/FIPS/NIST.FIPS.204.pdf)
- [Go crypto/mldsa](https://pkg.go.dev/crypto/mldsa) (Go 1.26+) and crypto/ed25519
- [Python cryptography](https://cryptography.io/en/latest/hazmat/primitives/asymmetric/mldsa/) 48 or later: `MLDSA65PrivateKey.from_seed_bytes`
- [Node.js crypto](https://nodejs.org/api/crypto.html) 24.6 or later: `ml-dsa-65` keys from a seed-only PKCS#8
- [OpenSSL ML-DSA](https://docs.openssl.org/3.5/man7/EVP_SIGNATURE-ML-DSA/) 3.5 or later, and [OpenSSL Ed25519](https://docs.openssl.org/3.5/man7/EVP_SIGNATURE-ED25519/)
- [libcurl options](https://curl.se/libcurl/c/curl_easy_setopt.html)
