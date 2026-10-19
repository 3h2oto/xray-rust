# 0.8.1 candidate measurements — 2026-10-18

**Publication authorized with explicit 0.8.1 limitations; distribution gates pending.**
The owner completed the physical iPhone network-switch and lock/wake actions.
Trojan and VMess passed; SS2022 passed only with the documented server UDP PMTU
condition, and its default-policy failure remains preserved. This directory is
a measured report supporting the exact-candidate schema-4 archive. The owner
explicitly selected “Выпускать 0.8.1 с описанными ограничениями”. The
[0.8.1 decision](../../releases/v0.8.1-owner-decisions.json) accepts the SS2022
WAN/remote-EOF limitations and defers the unconfirmed 5% latency bound for this
release. Failures remain failed; historical exceptions were not silently inherited.

## Candidate and artifact boundary

- Core commit `5b61eee201fac8639cb1dac0349e34af65db90f7`, tree
  `5f24e2368eb5c8ee34ae534de652a0f515dc6bb8`.
- SDK candidate `c5726d70139581ce0f15442eeb92c7056b14ef82` pins that core commit;
  public SDK artifact locks remain unprepared.
- Native libraries and host binaries use the workspace release profile/thin LTO.
  iPhone and Samsung host/probe apps are Debug harnesses, not store/release packages.
- Android native arm64 SHA256:
  `6d20112576b9136123a8543bc73a455201da1ca27ea8666c66e3c53976d3cffa`.
- Apple static library SHA256:
  `91009a0d8afc7d4bb68f43996646064af20264a09cb8bfa0c3f2ced0246b863c`.
- Devices: iPhone 17 Pro Max / iOS 27.0.1 (24A446), Samsung SM-A145F /
  Android 15 API 35, arm64. Identifiers and private addresses are redacted.

See [plan.json](plan.json), [build-manifest.json](build-manifest.json) and the
additional build manifests. The first Apple inventory records executable stubs;
the later projection/FakeDNS manifests inventory the full bundles, including
Debug dylibs. They must not be treated as identical application builds. The
production native library and production provider implementation are unchanged.
Only Debug probes and an allow-only sample-provider admission hook were added;
all source patches are included here.

## Measured physical-device coverage

Apple completed startup preflight success/failure/timeout/cancellation/disabled
cases (48 successful HTTPS requests), all supported Trojan/SS2022/VMess cipher
profiles, REALITY, XHTTP H1/H2/H3, WireGuard and Hysteria2. IPv4, IPv6, routed
domain/DNS, import, repeated start/stop, close-connections recovery, startup
cancellation, rapid restart and invalid-import redaction were exercised.
Host adapter projection was measured with actual TCP/UDP callback counters on
both FD and packet-pump backends (27 observations per backend).

Apple resource runs used two one/eight-flow cycles per protocol and 20 recovery
samples. Maximum RSS growth was 4,014,080 bytes (3.83 MiB), footprint growth
245,760 bytes, and thread growth zero. All preregistered 8 MiB/8-thread recovery
bounds passed; recorded thermal state remained nominal.

Android protocol/cipher smoke covered 14 combinations; resource tests covered
12 cipher/backend combinations with 5,760/5,760 HTTP and 11,520/11,520 UDP
successes. Resource recovery bounds were max(8 MiB, 25% of first recovery RSS)
and four threads, fixed before measurement; all 12 cases passed. Network/lock
checks on Android retain the explicitly documented v0.8 scope and were not run.

| Android suite | Smoke cases passed | Adapter observations | TCP cancellation observations | Remote close outside bound | Failure events |
| --- | ---: | ---: | ---: | ---: | ---: |
| android | 14 | 0 | 0 | 0 | 0 |
| android-shared | 6 | 6 | 0 | 0 | 0 |
| android-legacy | 8 | 0 | 0 | 0 | 0 |
| android-v07 | 4 | 0 | 0 | 0 | 0 |
| android-cancellation | 0 | 0 | 12 | 4 | 0 |

Use [device-inventory.json](device-inventory.json) and each suite's JSONL for
exact counts and bounds. A completed matrix is not evidence for manual network
switching or lock/wake. WireGuard uses canonical JSON import because the Android
automation host's link-import path accepts URI schemes, not wg-quick text.

## Physical iPhone WAN transitions and lock/wake

The owner resumed on 2026-10-18 (device log timestamps are 2026-10-19 UTC).
The normal signed Debug harness and unchanged release native library ran on the
physical iPhone. Each successful run exercised full IPv4/IPv6/domain TCP and
IPv4/IPv6 UDP traffic after every transition, with one stable runtime ID.
These are fresh-flow recovery checks, not established TCP-session continuity.

| Protocol / server condition | Cellular recovery | Wi-Fi return | Unlock recovery | Observed lock |
| --- | ---: | ---: | ---: | ---: |
| Trojan / default | 5.19 s | 5.02 s | 5.18 s | 24.97 s |
| VMess / default | 3.81 s | 3.92 s | 4.42 s | 26.80 s |
| SS2022 / owned UDP socket PMTU=0 | 3.82 s | 3.71 s | 4.38 s | 27.64 s |

Recovery is measured from the observed path change/unlock, including time until
the application resumes; each full traffic sweep succeeded on its first try.
The probe required at least 15 seconds of observed lock; the user was instructed
to hold approximately 30 seconds. Exact recorded intervals are retained.

The [SS2022 default-policy run](ios-wan-manual/shadowsocks2022-default-result.json)
failed its initial Wi-Fi traffic sweep: IPv4/IPv6/domain TCP and IPv4 UDP passed,
but the 1,372-byte IPv6 UDP echo timed out. No network/lock transition is claimed
for that attempt. A fresh fixture and synthetic domain were then used for the
conditional run. The public pinned helper changed only the owned temporary
IPv4 UDP listener's `IP_MTU_DISCOVER` from 1 to 0. Before/after audits verify the
same PID and FD retained that value; no host-wide PMTU setting or client change
was applied. See [the measured summary](ios-wan-manual/summary.json) and
[the existing deployment condition](../../ss2022-server-udp-pmtu.md).

Each successful run contains 12 TCP and 8 UDP exchanges, DNS checks, connection
closure verification and clean disconnect. Original failure events remain
failed. This conditional evidence does not establish a default-policy fix.

## IPOnDemand controls and preserved failed attempts

The initial Apple shared fixture used an unsupported raw VLESS share-link;
[the original failure](ios-shared-result.json) remains preserved. The corrected
shared run passed, but its initial IPOnDemand/AsIs control was insufficient:
the OS had already resolved the domain to a literal address.

A Debug-only FakeDNS assertion was added, requiring a `198.19.0.0/16` address
before domain traffic. The first FakeDNS attempt exposed a missing synthetic
probe-domain allow-route on the **fixture server**; positive, negative and
recovery failures remain preserved. No released client code was changed.
The final fixture allowed only that exact synthetic domain:

- [Positive](ios-fakedns-v2-positive-result.json): 18 TCP successes and 12
  FakeDNS proofs; full traffic passed.
- [AsIs negative](ios-fakedns-v2-negative-result.json): literal IPv4/IPv6 TCP
  succeeded, FakeDNS was proven, then domain traffic failed as expected. Its raw
  final result remains `failed`, not relabelled as a successful traffic run.
- [Recovery](ios-fakedns-v2-recovery-result.json): restoring IPOnDemand passed
  again, with 18 TCP successes and 12 FakeDNS proofs.

Fresh synthetic names prevent DNS cache contamination. Android likewise proved
literal-address success, domain failure with AsIs, and domain recovery with
IPOnDemand, on both FD and packet-pump backends.

## Active cancellation collector correction

The first Android TCP cancellation attempt failed its log assertion because
the collector compared phone log epochs with the Mac clock. The retained device
log contains a SocketException and the server recorded EOF. Five-sample clock
calibration now records the offset and uncertainty per case (about 1.13 seconds
of skew, about 27 ms uncertainty initially); bounded polling waits for the
asynchronous log event. The three-second local cancellation bound is unchanged.
See `android-cancellation/initial-failure-summary.json` and preserved collector
source. Local cancellation, remote EOF and subsequent traffic recovery are
reported separately. SS2022 remote EOF exceeded the three-second bound on
both backends and both operations while local cancellation passed. This known
limitation is preserved, not relabelled as end-to-end cancellation success.

## Host performance

Seven protocol/cipher profiles use five rotating-order paired repetitions of
single-flow loopback full-duplex and TCP latency, against the published 0.8.0
native binary and pinned Xray revision `5ca6f4b7d4dc20a881d4330e498892697627ec0c`.
The 0.8.0 baseline was built from clean tag commit
`fcce4be2771c1fb3f11e9503741d39a4d8df314e` with the same toolchain.
All results and outliers are retained. Peak RSS is sampled, not an allocator
high-water mark. This workload does not imply device/WAN throughput.

The first attempt was invalidated when macOS ANECompilerService became
CPU-active during a trial. Its manifest/raw measurements are retained under
`performance-protocols-interrupted-1`; the **entire attempt is excluded** from
acceptance. A fresh run uses the same collector and bounds.

Completed clean trials: **210/210**;
protocol collection complete: **True**.
The table shows medians of paired candidate/baseline ratios; preregistered
limits are throughput >=0.95, latency <=1.05, sampled memory <=1.05.

| Profile | Throughput ratio | p95 latency ratio | RSS ratio | 5% comparison |
| --- | ---: | ---: | ---: | --- |
| trojan-tls | 0.9831 | 0.9000 | 1.0263 | pass |
| ss2022-aes128 | 0.9748 | 0.9361 | 1.0111 | pass |
| ss2022-aes256 | 0.9726 | 1.0423 | 1.0111 | pass |
| ss2022-chacha20 | 1.0255 | 1.1094 | 1.0085 | FAIL |
| vmess-aes128 | 0.9997 | 0.9792 | 1.0112 | pass |
| vmess-chacha20 | 1.0335 | 0.8578 | 1.0054 | pass |
| vmess-auto | 0.9542 | 1.0198 | 1.0028 | pass |

The schema-4 protocol bounds are separate: throughput >=50% of paired Xray,
p95 latency <=200%, RSS <=64 MiB; aggregation takes the worst cipher per repeat.
Feature performance result: **pass**.
Legacy calibrated route/DNS/phase2/process/TUN result:
`{"status": "pass", "exitCode": 0, "finished": 1792368483.4967942}`.
The original five-pair SS2022 ChaCha20 p95 comparison exceeded its 5% limit
(ratio 1.109375). A predeclared 15-pair follow-up alternates candidate/baseline
order and retains the original failure. Its median paired ratio is
**0.9907407407407407** (limit 1.05): the observed
regression was not reproduced in the longer diagnostic series. See the
[follow-up summary](performance-ss2022-latency-followup/summary.json) for all 15
pairs and an explicitly exploratory combination of both series. This does not
turn the original five-pair failure into a pass or imply a universal latency
guarantee. The combined 95.86% median-ratio interval is 0.947–1.123, which
crosses 1.05: these samples do not establish a 5% non-regression bound with
95% confidence. The new 0.8.1 owner decision accepts this unconfirmed bound for publication;
it does not change the measurements or their statistical interpretation.

## CI, pending work and cleanup

CI details, exact revisions and job outcomes are in [ci-status.json](ci-status.json).

Remaining release work: validate the exact-commit schema-4 archive in CI under
the explicit 0.8.1 decision, then follow the core-tag / SDK-pin / prepared
Apple-checksum / SDK-tag / published-consumer sequence in
[the release plan](../../v081-release.md). Do not move an existing tag or replace
missing measurements with an older candidate's results.

The owner selected the private repository `.env` for the WAN fixture. Fresh
high TCP ports were unreachable from the Mac; an isolated port-80 echo test
passed TCP and timed out on UDP. Those are **fixture connectivity observations**,
not candidate protocol failures. The manual campaign subsequently used the
existing reachable test allocation on port 53053. Before each bounded fixture,
only the two pre-existing test services were suspended; systemd ExecStopPost
restored both. Their initial state and restoration after every run are retained.
The pinned public Linux Xray reference SHA256 was
`dad34bede2e76f66f3ade83cd1eba71c39bb2a065011528e5571c0638a5f64e1`.
All temporary units are now inactive, the temporary directory and keys were
removed, both original test services are active, and the original production
Xray PID remains present. The iPhone was relaunched in normal application mode.
See [cleanup verification](ios-wan-manual/cleanup.json) and [the WAN plan](ios-wan-plan.json).

Cleanup snapshot: `{"status": "completed", "androidOriginalVPNRestored": true, "androidActiveVPNPackage": "com.wireguard.android", "androidTunnelInterfaceMatchesOriginal": true, "androidTestVPNStopped": true, "appleNormalProviderAppRestored": true, "localCampaignFixtureProcessesStopped": true, "baselineSourceWorktreeRemoved": true, "WAN": {"temporaryFixtureDirectoryAbsent": true, "temporaryFixtureProcessAbsent": true, "temporaryEchoProcessAbsent": true, "productionXrayStillPresent": true, "originalTestXrayStillPresent": true}, "time": 1792368841.4729862, "manualWAN": "ios-wan-manual/cleanup.json: fixture units inactive, private directory removed, test services restored, production PID unchanged", "iPhone": "normal app mode relaunched after completed WAN/lock tests"}`.

## Evidence handling

[inventory.json](inventory.json) records SHA256 before and after sanitization.
Private addresses, usernames/paths and device IDs are replaced with labels.
Large JSON arrays use one event/run per line; parsed values are checked against
the sanitized originals. Unified diffs use `.patch.json` wrappers with a `patch`
string so meaningful diff whitespace is preserved.
Credentials, profile/share-link configuration files, private keys, provisioning
payloads, app bundles and raw system logs are excluded. Safe measurements,
collector source and Debug source patches are retained. These files preserve
observed failures and the distinction between expected negative controls,
fixture errors, historical limitations and pending required actions.
