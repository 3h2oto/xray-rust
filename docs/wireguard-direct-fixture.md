# WireGuard direct-target reference fixture

This fixture change is separate from the optional client diagnostics in PR #38.
Default redirect mode keeps the IPv4 source binding from PR #60. The explicit
`--direct-targets` mode removes that binding so IPv6 destinations can select
an IPv6 source, and restricts the outbound allowlist to the three owned targets.
It supports the WireGuard/Hysteria generator, not the v0.8 or legacy suites.

Linux CI runs `bash scripts/check-wireguard-direct-fixture.sh`, which verifies
both reference sources, creates ephemeral fixture keys and runs the reproducer
inside a fresh network namespace. Its temporary configuration is removed on exit.

The pinned Xray-core WireGuard inbound retains UDP associations by the inner
source endpoint. Its Freedom redirect mode cannot retain the correct reply
source when that association subsequently targets another address or port.
After a client restart, a reused inner port can therefore receive a reply
labelled with its older destination. A strict client must discard that reply.
This is separate from carrier loss before the client's UDP receive hook.

`scripts/check-wireguard-redirect-reuse.py` reproduces this with the official
wireguard-go raw client, without our engine or userspace stack. Build the
existing `tools/wireguard-reference` for Linux, then run the script in a fresh
Linux network namespace (for example `unshare --net python3 ...`). Pass
`--fixture-dir` for an existing private fixture, `--xray-binary`, `--go-binary`
and `--output`. It checks first destination, reused source port/new destination,
and fresh source port/new destination with and without redirect. All requests
are single-send. Synthetic addresses are provisioned only inside that namespace.

For physical restart/UDP acceptance, use
`scripts/run-v07-apple-protocol-fixture.py --direct-targets` after provisioning
`198.51.100.7/32`, `198.51.100.53/32` and `2001:db8::7/128` on the fixture host's
loopback. The supervising runner must remove only addresses it added, including
on timeout/failure. TCP/UDP echo and DNS then bind at their actual synthetic
destinations; outbound policy allows only those targets. Legacy redirect mode
is retained for reproducing older evidence, and is unsuitable for judging
source-port reuse across different targets.

Reference behavior is in the pinned
[WireGuard UDP association](https://github.com/XTLS/Xray-core/blob/v26.7.28/proxy/wireguard/tun.go)
and [Freedom reply-source handling](https://github.com/XTLS/Xray-core/blob/v26.7.28/proxy/freedom/freedom.go).
The physical DNS failure that led to this reproducer does not establish the
cause of earlier failures without matching packet evidence.
