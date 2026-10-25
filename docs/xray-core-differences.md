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

### Pending integration

The table below distinguishes follow-up work from the reviewed main snapshot.
Neither PR expands main's support until it is merged. Keep this section current
when integrating the branches rather than silently applying their results to
the older snapshot.

| Change | Evidence | Integration state |
| --- | --- | --- |
| [#86: mobile SOCKS carrier bootstrap](https://github.com/aimalygin/xray-rust/pull/86), `312f26477b696789a7978e71e7b293fadcc74127` | Flat/legacy server settings, static mappings and aliases, IPv4/IPv6 literals, and tunnel-owned address rejection; 107 Android tests passed with 12 native-only skips and 350 Swift tests passed; [all six CI jobs passed](https://github.com/aimalygin/xray-rust/actions/runs/40120289548) | Implemented; awaiting merge |
| [#87: SOCKS UDP outbound](https://github.com/aimalygin/xray-rust/pull/87), contributor head `9fcf7443b9f170d374d424bc55e03cdf583f2b52` | Adds a declared UDP endpoint and association lifecycle. Review follow-up fixes unspecified relay addresses after Happy Eyeballs and mapped IPv6 proxy literals; adds pinned UDP/TLS/TUN interop and the reverse-direction restriction test described below | Review follow-up prepared separately; awaiting integration and CI on the final PR revision |

The #87 review follow-up is
[`36ade5937ed92eea2ab5b568603b4509f38f1745`](https://github.com/aimalygin/xray-rust/commit/36ade5937ed92eea2ab5b568603b4509f38f1745)
on `codex/socks-udp-interop`. Its local workspace run passed 2,552 tests with
109 standard ignored tests; all four pinned SOCKS interop tests, Clippy,
formatting, mobile script guards, and the generated configuration contract
check passed. The #86 and #87 trees merge without conflicts; this is not a
physical-device test of the combined branches.
The contributor revision's
[CI run](https://github.com/aimalygin/xray-rust/actions/runs/40124846131) passed
rust, android, apple, supply-chain and secrets, but go-oracles failed while a
WireGuard reference server tried to bind an occupied local UDP port. That run
is not green and does not validate the subsequent review fixes.

## Decisions at a glance

| Area | Behavior at the reviewed main snapshot | Relationship to the reference |
| --- | --- | --- |
| #74 / #83: dependencies and Tokio descriptors | Updated dependency locks, private CLOEXEC descriptor duplicates, corrected Gradle checksum retry handling | Internal Rust/build changes; no intended Xray JSON or wire-format change |
| #80 / #78: SOCKS inbound authentication | SOCKS5 username/password; stricter credential/configuration validation | RFC 1929 TCP authentication; authenticated UDP has the deliberate restriction below |
| #84 / #79: SOCKS outbound | TCP CONNECT, noauth or password, flat or legacy settings, raw TCP with none/TLS security | Tested subset of Xray-core; #87 adds UDP, while the transport restrictions remain |
| #82 / #81: Android fixes | VPN metering policy, cached native FFI information, checked stats array length | Host SDK behavior, not an Xray network protocol extension |
| #81: proposed Android cleanup/helpers | Cleanup, descriptor/snapshot/package helpers, optional network-change integration | Not yet implemented by these PRs; must preserve documented ownership and lifecycle rules |
| #79: HTTP outbound | Not implemented | Proposed CONNECT/Basic-auth/TLS support; scope decisions and checks remain below |
| Mobile SOCKS bootstrap | SOCKS is omitted from Android and Apple carrier-host collection | Integration gap fixed in pending #86, not an intended compatibility restriction |

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
  password-protected SOCKS inbound. The #87 review follow-up test
  `socks_runtime_pinned_xray_client_preserves_password_udp_restriction`
  confirms this against the pinned Go client: TCP authentication and echo pass,
  while UDP is rejected. The test is pending integration with that branch.

Declaring a local port also does not guarantee operation across NAT: a NAT
that rewrites the UDP source port makes it differ from the declared endpoint.
The loopback tests do not establish NAT interoperability. Do not restore
first-sender learning to address that limitation without a replacement for the
isolation this policy provides.

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

At the main snapshot, the outbound implements TCP CONNECT only. It rejects UDP,
enabled Mux, non-raw transports, and REALITY. Xray-core has a SOCKS UDP client and a broader
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

The pending #87 follow-up extends the pinned script with UDP in both settings
forms, password/noauth and wrong/missing credentials, plain/TLS control
connections, IPv4/IPv6/domain destinations, the 8 KiB datagram framing boundary,
socket protection, host close, and TUN UDP/DNS under `StaticOnly` bootstrap.
It resolves destination names at the proxy. Separate regressions show that an
unspecified relay IP must use the actual connected TCP peer after a candidate
fallback, and that an IPv4-mapped IPv6 proxy literal needs an IPv4 UDP socket,
matching the TCP connection and #86's Apple carrier exclusions.

These tests passed locally against the pinned Go revision. They do not prove
physical-device routing, NAT traversal, an IPv6 proxy carrier, TLS TCP CONNECT,
`proxySettings` or `probeOutboundUrl` interoperability. TLS protects only the
SOCKS control connection; UDP relay datagrams remain plain. UDP proxy chaining
and Mux remain rejected. No C ABI or host ownership contract changes are needed.

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

The initial reproduction was not committed. PR #86 now includes permanent
Android and Apple regressions for the same gap, covering both settings forms,
static hosts/aliases, literal normalization, and tunnel-owned address rejection.
It resolves the proxy's carrier hostname before installing the VPN and applies
Apple carrier exclusions, while destination domains in CONNECT or UDP relay
datagrams remain the proxy's responsibility. Host unit tests and CI passed;
physical-device routing is not established by those tests. The fix remains
pending integration.

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

- [ ] Integrate the #87 review follow-up, including both relay-address fixes,
  the pinned UDP/TLS/TUN tests, and the direct Go-client password-UDP restriction
  regression. Keep the foreign-first sender protection tests. Run CI on the
  final contributor revision before merging.
- [ ] Integrate the tested #86 Android and Apple SOCKS bootstrap fixes; verify
  the combined #86/#87 branches without changing destination DNS semantics.
- [ ] Add live TCP CONNECT over TLS, an IPv6 proxy carrier, `proxySettings`, and
  `probeOutboundUrl` coverage; distinguish them from UDP TLS control and IPv6
  destination coverage already added in the #87 follow-up.
- [ ] Resolve the HTTP scope decisions above before claiming #79 complete.
- [ ] Keep #81 cleanup separate from new SDK API/lifecycle behavior and verify
  each against the documented FFI/host contract.

When an item is resolved, update its status, the tested xray-rust and upstream
revisions, and links to durable tests/results in the same PR. Update
[config-compatibility.md](config-compatibility.md) and the generated parser
contract whenever supported fields change. A green workflow alone does not
close an untested compatibility item.
