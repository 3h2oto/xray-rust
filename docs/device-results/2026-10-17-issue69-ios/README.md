# Issue #69: startup probe on a physical iPhone

Validated on 2026-10-17 with an iPhone 17 Pro Max, iOS 27.0.1 (24A446), wired
to Xcode. The signed Debug sample app links the current working tree's release
iOS library (LTO disabled), ABI 1.12. This is a development device build, not a
canonical distribution XCFramework. Source and binary hashes are recorded in
[build-manifest.json](build-manifest.json).

The same test was run with the fix, with a control recreating the old startup
order, and again with the fix. Both fixed runs passed all five scenarios and
completed **95 app-side HTTPS requests with zero failures**. The control
reproduced **nine `NSURLErrorDomain/-1009` failures** while the startup probe
waited for an HTTP 503 response. The first success case in the control had no
request failures; reproduction occurred on its second connection attempt.

| Scenario | Fixed run 1 | Fixed repeat after control | Expected VPN outcome |
| --- | --- | --- | --- |
| Delayed HTTP 204 | Passed | Passed | Connected after probe succeeds |
| Delayed HTTP 503 | Passed | Passed | Disconnected; app HTTPS remains available |
| Five-second timeout | Passed | Passed | Disconnected; app HTTPS remains available |
| Stop after two seconds | Passed | Passed | Pending probe cancelled; disconnected |
| Probe disabled | Passed | Passed | Connected without contacting probe server |

Requests run about every 500 ms plus request duration with an ephemeral
URLSession, disabled response cache and two-second request timeout. They begin
before `startTunnel`, continue through `connecting`, and continue after the
startup result. HTTPS requests to a second hostname also passed after successful
connections. Exact timings, statuses, request counts and errors are in the raw
reports. The test removes only its own `Xray #69 Startup Probe Check` manager
and secure config reference. The fixed app was restored after the control; its
final run completed cleanup before it was terminated.

## Inputs and scope

The native probe uses a controlled HTTP server on the development Mac. `/success`
waits five seconds and returns 204; `/failure` waits five seconds and returns
503; `/timeout` and `/cancel` wait longer than the probe deadline. The profile
contains the normal TUN inbound, a Freedom outbound, and `dns.servers` set to
1.1.1.1 / 8.8.8.8. Host DNS overrides are absent, so the provider advertises its
normal 198.18.0.1 DNS anchor. The app-side HTTPS endpoint is `example.com`.

The control shares the same native ABI 1.12 library and Debug harness. Its only
provider change bypasses preflight and calls `applyNetworkSettingsAndStartRuntime`
directly after DNS bootstrap, retaining the configured synchronous probe inside
`core.start()`. It isolates the ordering change rather than rebuilding an older
release. See [baseline-control.patch](baseline-control.patch) and
[baseline-manifest.json](baseline-manifest.json).

This establishes the system NetworkExtension behavior and app connectivity on
this iPhone with the stated TUN/Freedom profile. It does not validate tvOS or the
original report's VLESS/REALITY/Vision endpoint, or identify the alleged cached
negative DNS answer.

## Evidence

- [summary.json](summary.json): machine-readable comparison.
- [fixed-result.json](fixed-result.json): first fixed run, 47 HTTPS requests.
- [baseline-result.json](baseline-result.json): control, including nine -1009 errors.
- [final-result.json](final-result.json): fixed repeat, 48 HTTPS requests.
- [fixed-provider.log](fixed-provider.log), [baseline-provider.log](baseline-provider.log),
  [fixed-repeat-provider.log](fixed-repeat-provider.log): startup-probe excerpts
  from the actual extension's native log, limited to each run's time window.

## Repeating the check

Build the iOS library/XCFramework and signed sample app from the same source.
Start the controlled server on a Mac reachable from the device:

```sh
python3 scripts/run-apple-startup-probe-server.py --port 18669
```

Copy a small JSON fixture to the app's `Documents/issue69-probe.json`:

```json
{
  "baseURL": "http://MAC_LAN_IP:18669",
  "trafficURL": "https://example.com/"
}
```

Launch the Debug sample with both `XRAY_V07_DEVICE_PROBE=1` and
`XRAY_STARTUP_PROBE_DEVICE_CHECK=1`. Normal launches never enter this harness.
The device must permit this app's test VPN and local networking. Retrieve
`Documents/issue69-result.json`; a successful run ends with a `complete` event
whose `result` is `passed`. Each scenario must have zero failed HTTPS samples.
