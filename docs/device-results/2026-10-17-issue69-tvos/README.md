# Issue #69: physical Apple TV, VLESS + REALITY + Vision

Validated on 2026-10-17 with the physical Apple TV HD / fourth-generation
Apple TV, **AppleTV5,3**, running **tvOS 26.6 (23L773)**. This matches the
hardware and OS reported in issue #69. The signed Debug sample uses the current
working tree's release tvOS library, ABI 1.12, with LTO disabled. It is a
development device build, not the canonical distribution XCFramework.

The fix was tested, followed by a control recreating the previous startup
order, followed by the fix again. The two fixed runs passed all five scenarios
and completed **101 app-side HTTPS requests with zero failures** (51 + 50).
The old-order control reproduced **six `NSURLErrorDomain/-1009` errors and
one `-1001` request timeout** during the first delayed successful probe. Its
VPN ultimately connected, and HTTPS worked again after connection. The check
then failed as intended and removed its test VPN.

| Scenario | Fixed run | Fixed repeat after control | VPN outcome |
| --- | --- | --- | --- |
| HTTP 204 delayed five seconds | Passed | Passed | Connected |
| HTTP 503 delayed five seconds | Passed | Passed | Startup failed; HTTPS continued working |
| Five-second startup-probe timeout | Passed | Passed | Startup failed; HTTPS continued working |
| Stop after two seconds | Passed | Passed | Probe cancelled; disconnected |
| Startup probe disabled | Passed | Passed | Connected without another probe request |

Requests run about every 500 ms plus request duration, beginning before
`startTunnel`, continuing through `connecting` and after the startup result.
The URLSession is ephemeral, disables response caching and uses a two-second
request timeout. A second HTTPS hostname is requested after successful
connections. Both fixed runs completed cleanup. The fixed signed app was
restored after the control, and only the test's own VPN manager was removed.

## Actual protocol and network path

- The reference server is Xray-core **v26.7.28**, clean revision
  `5ca6f4b7d4dc20a881d4330e498892697627ec0c`, built with Go 1.26.0.
- Its authenticated inbound uses VLESS, REALITY over raw TCP, and a user whose
  flow is `xtls-rprx-vision`. The client uses the Chrome fingerprint and the
  generated REALITY public key/short ID. REALITY's TLS target/SNI is
  `www.example.com:443` / `www.example.com`.
- The Apple TV profile has the normal TUN inbound and **one outbound**, that
  VLESS/REALITY/Vision proxy. It has no Freedom fallback or bypass routing.
  The Debug check validates these protocol/security/flow fields before starting.
- `dns.servers` is 1.1.1.1 / 8.8.8.8. There is no explicit host DNS override;
  NetworkExtension advertises its normal 198.18.0.1 DNS anchor.
- The delayed HTTP server binds only to the reference server's loopback. Probe
  URLs use `http://127.0.0.1:18669/...`: this is the **remote** loopback reached
  through VLESS, not the Apple TV's local interface. The Go server explicitly
  allows this one loopback address in Freedom final rules.
- The server accepted the Apple TV's VLESS requests for that loopback endpoint
  and logged Vision padding/unpadding and inner TLS 1.3 detection for the
  device's tunneled HTTPS traffic. Selected records are in
  [reference-server-evidence.log](reference-server-evidence.log).

The HTTP server holds `/success` and `/failure` for five seconds before
returning 204 or 503. `/timeout` and `/cancel` hold longer than the client
deadline/cancellation. App-side HTTPS uses `example.com`, with
`www.example.com` requested after connection.

## Control and provenance

The control shares the same native ABI 1.12 library, protocol fixture and
device-check harness. Its only provider difference calls
`applyNetworkSettingsAndStartRuntime` directly after DNS bootstrap, retaining
the configured synchronous probe inside `core.start()`. It isolates startup
ordering rather than rebuilding release 0.6.1. See
[baseline-control.patch](baseline-control.patch) and
[baseline-manifest.json](baseline-manifest.json).

[build-manifest.json](build-manifest.json) records source/binary hashes and the
client-config SHA-256. Temporary UUIDs, REALITY private keys and configuration
files are excluded from the evidence. Both test servers were stopped and
the temporary local credential directory was removed after collection.

## Evidence

- [summary.json](summary.json): machine-readable device, transport and comparison.
- [fixed-result.json](fixed-result.json): first fixed run, 51 HTTPS requests.
- [baseline-result.json](baseline-result.json): old-order control with seven failures.
- [final-result.json](final-result.json): fixed repeat, 50 HTTPS requests.
- [fixed-provider.log](fixed-provider.log), [baseline-provider.log](baseline-provider.log),
  [fixed-repeat-provider.log](fixed-repeat-provider.log): native startup-probe
  records from the actual Packet Tunnel extension, limited to each run.
- [http-server.jsonl](http-server.jsonl): controlled HTTP endpoint timings.
- [native-preflight.json](native-preflight.json): preliminary macOS Rust FFI
  check of the same server/transport, separate from the physical tvOS proof.

## Repeating the check

Build and sign the tvOS sample with a tvOS slice of the matching native
library. Provision a controlled VLESS/REALITY/Vision server with temporary
credentials and use `scripts/run-apple-startup-probe-server.py` for the delayed
HTTP responses behind it. For loopback-only HTTP, pass `--host 127.0.0.1`.

Copy a JSON fixture to the tvOS app's
**`Library/Caches/issue69-probe.json`**, containing `baseURL`, `trafficURL`,
and `configJSON`. `configJSON` is a JSON string containing the single-outbound
VLESS/REALITY/Vision TUN profile. Launch the Debug tvOS app with
`XRAY_STARTUP_PROBE_DEVICE_CHECK=1`; normal launches retain the regular UI.
Retrieve `Library/Caches/issue69-result.json` and require a final `complete`
event with result `passed` and zero failed samples in each scenario.

tvOS denied the initial attempt's Documents access before any VPN startup;
the shared check now uses Caches on tvOS and Documents on iOS. That setup error
is not included in the three comparison runs. A stale setup fixture was cleared
without touching other app documents.

This check establishes application connectivity and DNS reachability with the
stated protocol on the reported Apple TV model/OS. It does not identify the
unconfirmed negative DNS-cache answer from #69, and it does not automatically
assert the presence or absence of tvOS's system network banner. The endpoint
uses temporary reference-server credentials rather than the original Browsec
server credentials.
