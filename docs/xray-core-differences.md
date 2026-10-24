# Xray-core differences and verification gaps

This records compatibility decisions and unfinished integration work from
[issues #79](https://github.com/aimalygin/xray-rust/issues/79) and
[#81](https://github.com/aimalygin/xray-rust/issues/81), and PRs
[#74](https://github.com/aimalygin/xray-rust/pull/74),
[#80](https://github.com/aimalygin/xray-rust/pull/80),
[#82](https://github.com/aimalygin/xray-rust/pull/82), and
[#84](https://github.com/aimalygin/xray-rust/pull/84).
The [configuration contract](config-compatibility.md) remains authoritative for
accepted fields. This document records consequences, evidence, and follow-up
checks; it does not expand the supported configuration surface.

## Reference and evidence

Reviewed on 2026-10-24 against xray-rust main
`6168fdaf9c8939941ed3f7009753ba98b1574e0f` and Xray-core **v26.7.28**,
`5ca6f4b7d4dc20a881d4330e498892697627ec0c`. The upstream pin is enforced by
[verify-oracle-fixtures.py](../scripts/verify-oracle-fixtures.py). These findings
do not establish compatibility with every later Xray-core revision.

The [main CI run](https://github.com/aimalygin/xray-rust/actions/runs/40104360249)
passed rust, android, apple, go-oracles, supply-chain, and secrets. Passing a job
establishes the scenarios that job exercises, not every combination of a
protocol, platform, transport, and API. In particular, mobile SOCKS bootstrap
and a real Xray SOCKS client using our password-protected UDP inbound were not
covered by that run.

The changes from these PRs were unreleased at this review; the latest published
release was [v0.8.1](https://github.com/aimalygin/xray-rust/releases/tag/v0.8.1).

## Decisions at a glance

| Area | Current behavior | Relationship to the reference |
| --- | --- | --- |
| #74 / #83: dependencies and Tokio descriptors | Updated dependency locks, private CLOEXEC descriptor duplicates, corrected Gradle checksum retry handling | Internal Rust/build changes; no intended Xray JSON or wire-format change |
| #80 / #78: SOCKS inbound authentication | SOCKS5 username/password; stricter credential/configuration validation | RFC 1929 TCP authentication; authenticated UDP has the deliberate restriction below |
| #84 / #79: SOCKS outbound | TCP CONNECT, noauth or password, flat or legacy settings, raw TCP with none/TLS security | Tested subset of Xray-core; no UDP outbound and fewer allowed transports |
| #82 / #81: Android fixes | VPN metering policy, cached native FFI information, checked stats array length | Host SDK behavior, not an Xray network protocol extension |
| #81: proposed Android cleanup/helpers | Cleanup, descriptor/snapshot/package helpers, optional network-change integration | Not yet implemented by these PRs; must preserve documented ownership and lifecycle rules |
| #79: HTTP outbound | Not implemented | Proposed CONNECT/Basic-auth/TLS support; scope decisions and checks remain below |
| Mobile SOCKS bootstrap | SOCKS is omitted from Android and Apple carrier-host collection | Known integration gap, not an intended compatibility restriction |

## Password-protected SOCKS UDP: deliberate restriction

RFC 1929 authenticates the TCP control connection. SOCKS UDP datagrams do not
carry that username/password authentication. Our password-protected inbound
therefore requires a nonzero client UDP port in `UDP ASSOCIATE` and admits only
the declared endpoint. An unspecified IP can use the TCP peer's IP with the
declared port. A zero port, including `0.0.0.0:0`, is refused before a relay is
created. This prevents a different local socket from claiming the association
by sending the first datagram. The rule applies to password mode.

This is narrower than the reference and the zero-address client case described
by [RFC 1928 section 6](https://www.rfc-editor.org/rfc/rfc1928.html#section-6):

- The pinned Xray-core [SOCKS client](https://github.com/XTLS/Xray-core/blob/5ca6f4b7d4dc20a881d4330e498892697627ec0c/proxy/socks/protocol.go#L490)
  sends `0.0.0.0:0` for UDP association.
- Its [server](https://github.com/XTLS/Xray-core/blob/5ca6f4b7d4dc20a881d4330e498892697627ec0c/proxy/socks/protocol.go#L198)
  accepts that case and [learns the UDP port](https://github.com/XTLS/Xray-core/blob/5ca6f4b7d4dc20a881d4330e498892697627ec0c/proxy/socks/temp_udp_listen.go#L30)
  from the first matching source IP.
- Consequently, that Xray-core client cannot relay UDP through our
  password-protected SOCKS inbound. This conclusion follows from the two code
  paths; a direct Go-client-to-Rust-server interop regression is still pending.
  SOCKS TCP authentication is unaffected by this restriction.

Existing Rust [runtime tests](../crates/xray-core-rs/tests/runtime_data_path_tests.rs)
cover `socks_password_udp_association_refuses_undeclared_client_endpoint` and
`socks_password_udp_association_ignores_other_local_senders`, including a foreign
sender arriving first. Preserve those tests if this policy changes. Accepting
the first local sender again would remove the protection; any proposal to
broaden compatibility must explain how it retains the intended isolation.

## SOCKS outbound: supported subset and evidence

The [parser contract](config-compatibility.md#socks-outbound) records the exact
limits. Both flat settings and one legacy `servers` entry with at most one user
match the reference's supported shapes. Our parser additionally rejects mixed
forms, zero ports, incomplete/empty credentials, and unknown fields instead of
silently accepting or ignoring them. `level` also applies without credentials;
`email` is type-checked but does not supply upstream user-identity accounting.

The outbound implements TCP CONNECT only. It rejects UDP, enabled Mux,
non-raw transports, and REALITY. Xray-core has a SOCKS UDP client and a broader
transport surface. SOCKS support does not imply `socks://` or `socks5://` import
support in our mobile profile importers.

[check-socks-interop.sh](../scripts/check-socks-interop.sh) runs a real pinned
Xray-core SOCKS server against the Rust client. Its
[runtime test](../crates/xray-core-rs/tests/socks_runtime_tests.rs) covers both
settings shapes, password/noauth, wrong/missing credentials, IPv4 and remote
domain resolution, 64 KiB payloads, socket protection, and connection inventory.
Separate [client tests](../crates/xray-proxy/tests/socks_client_tests.rs) cover
IPv6 address encoding, malformed/truncated replies, and preserving tunnel data
after the reply. These are different evidence levels: the live upstream test
does not currently cover IPv6, TLS, `proxySettings`, or `probeOutboundUrl`.

## Mobile SDK and the SOCKS bootstrap gap

`setMetered(false)`, FFI caching, stats decoding, and the proposed #81 helpers
belong to the Kotlin SDK. They do not add a protocol to Xray-core. A descriptor
helper must preserve BORROWED/OWNED lifetime rules; a network-change helper must
preserve the [host's network selection and shutdown rules](../platform/android/README.md#network-changes-and-hysteria-limits).
Coroutines remain a separate dependency/API decision.

At the reviewed commit, Android's `collectOutboundBootstrapDomains` in
[XrayAndroidDnsBootstrap.kt](../platform/android/xraymobile/src/main/java/org/xrayrust/mobile/XrayAndroidDnsBootstrap.kt)
and Apple's `outboundBootstrapAddresses` in
[XrayPacketTunnelProvider.swift](../platform/apple/Sources/XrayAppleTunnel/XrayPacketTunnelProvider.swift)
omit `socks`. A SOCKS server specified by domain without a usable static host
mapping is therefore not prepared for the SDK's `StaticOnly` bootstrap mode.
This is a bug to fix, not a permanent divergence from Xray-core.

A local Android unit reproduction used the existing
`prepareAndroidVpnConfigWithinDeadline` entry point with a stub resolver
returning `192.0.2.8` for `proxy.example`. Both settings forms below failed the
assertion that the resolver is called and a `full:proxy.example` mapping is
inserted; the observed lookup list was empty. An equivalent flat Trojan
control passed. The bootstrap source tested was identical to the reviewed main.

```json
{"outbounds":[{"protocol":"socks","settings":{"address":"proxy.example","port":1080}}]}
```

```json
{"outbounds":[{"protocol":"socks","settings":{"servers":[{"address":"proxy.example","port":1080}]}}]}
```

This reproduction was not added to the normal test suite. Apple has the same
omission by source inspection; no Apple runtime/device reproduction was run.
The fix must resolve the proxy's carrier hostname before installing the VPN,
without changing the remote resolution of destination domains sent in CONNECT.

## HTTP outbound: proposed scope, not implemented support

The #79 request for CONNECT, optional Basic authentication, TCP-only operation,
and plain TCP or TLS follows the pinned
[Xray HTTP client](https://github.com/XTLS/Xray-core/blob/5ca6f4b7d4dc20a881d4330e498892697627ec0c/proxy/http/client.go).
Before implementing it, record decisions for these remaining differences:

- HTTP/1.1 versus HTTP/2: the reference supports both. If the first version
  implements only HTTP/1.1, constrain TLS ALPN accordingly and document the
  unsupported HTTP/2 path rather than negotiating a protocol it cannot speak.
- CONNECT success: the reference accepts only status 200; the issue sketch
  accepts all 2xx, consistent with
  [RFC 9110 section 9.3.6](https://www.rfc-editor.org/rfc/rfc9110.html#section-9.3.6).
  Choose and test the behavior explicitly.
- The reference accepts flat and legacy settings and custom `headers`. Define
  the initial parser surface, including `level`/`email`, and reject unsupported
  options rather than implying that accepting them implements their behavior.
- Bound response-header parsing and retain bytes immediately following the
  CONNECT response. Cover authentication failure, malformed responses, TLS,
  IPv4/IPv6/domain authorities, chaining, probes, and mobile carrier bootstrap.

## Follow-up checks

- [ ] Add direct pinned Xray-client-to-Rust-server TCP/auth coverage and an
  explicit regression for the current password-UDP incompatibility. Keep the
  foreign-first sender protection tests.
- [ ] Fix Android and Apple SOCKS bootstrap and commit regressions for flat and
  legacy settings, static mappings, aliases, and tunnel-owned address rejection.
- [ ] Add live SOCKS IPv6/TLS, `proxySettings`, and `probeOutboundUrl` coverage;
  distinguish those results from unit-level protocol coverage.
- [ ] Resolve the HTTP scope decisions above before claiming #79 complete.
- [ ] Keep #81 cleanup separate from new SDK API/lifecycle behavior and verify
  each against the documented FFI/host contract.

When an item is resolved, update its status, the tested xray-rust and upstream
revisions, and links to durable tests/results in the same PR. Update
[config-compatibility.md](config-compatibility.md) and the generated parser
contract whenever supported fields change. A green workflow alone does not
close an untested compatibility item.
