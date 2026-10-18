# Application protocol v2

API endpoint paths retain `/v1`. The lease and signature domains use v2. All
requests are JSON over HTTPS. HTTP is permitted only on loopback for development.
Do not follow redirects with signed bodies. Public keys are administrator-provided
32-byte Ed25519 verification keys, encoded as unpadded base64url. Installation
private keys never leave the host. Product signing keys and admin credentials
never belong in an application client.

## Exact signature bytes

Times below are UTC RFC 3339, truncated to seconds, for example
`2026-10-18T12:00:00Z`. The server permits five minutes of skew. Encoding is UTF-8;
`\n` denotes one LF byte. Hash output is lowercase hex. Sign with **pure Ed25519**,
without prehashing the complete message. Signatures use unpadded base64url.

```text
device = "licensebox device v2\n" + product + "\n" + binding + "\n" + time
poll   = "licensebox token v2\n" + device_code + "\n" + binding + "\n" + time
call   = "licensebox " + kind + " v2\n" + lease + "\n" + binding + "\n" + time + "\n" + hex(SHA256(payload))
```

`payload` is a JSON **string** in the signed call envelope. Hash its exact UTF-8
bytes, including any escaping or whitespace, and transmit those same bytes in
the string. No canonical JSON reserialization is performed by the verifier.

## Activation

Generate an Ed25519 installation key, retained across process restarts. Derive the
native binding before contacting the server. Missing identity refuses activation.

`POST /v1/device` has `product`, `machine` (installation public key), `binding`,
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
over `"licensebox lease v2\n"` followed by the **original decoded payload bytes**.
Fields are `v=2`, `kid`, `product`, `user`, `email`, `machine`, `binding`, `modules`,
`issued`, `expires`, `terms`. Select only a trusted key by `kid`; match the product,
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
`macos-platform`. Binding namespace m1 is distinct from signature format v2.
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
files 0600, writes atomic. `install.key` is a base64url 32-byte seed; `lease` holds
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

## Crypto implementation references

- [Python cryptography: Ed25519](https://cryptography.io/en/46.0.4/hazmat/primitives/asymmetric/ed25519/)
- [Node.js crypto](https://nodejs.org/download/release/v22.18.0/docs/api/crypto.html)
- [OpenSSL Ed25519](https://docs.openssl.org/3.4/man7/EVP_SIGNATURE-ED25519/)
- [libcurl options](https://curl.se/libcurl/c/curl_easy_setopt.html)
