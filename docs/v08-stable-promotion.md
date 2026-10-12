# v0.8.0 stable release preparation

On 2026-10-11 the owner requested release and updates to issues #47/#51–53,
while explicitly deferring the reproduced iPhone Hysteria startup failure
and the unconfirmed calibrated 5% performance gate. The
[decision record](releases/v0.8.0-owner-decisions.json) preserves the exact scope.
The [latest device report](device-results/2026-10-11-iphone17-hysteria/README.md)
retains failures. No packet capture with administrator privileges was run.

The reviewed runtime base is core
`f61eddaf40bcb2144933208438f3f4791cbbabca`, tree
`21ab7af488504b190f259123df9d1588b37590b1`; the development SDK was
`ca0ba5480b4764f210cc7d16961ee00abe9dc4e7`. Promotion changes version metadata
and documentation only; runtime sources, canonical adapters, ABI, dependencies
and build settings stay unchanged. Historical binary evidence retains its
original version and source identity.

Implemented issue scope: #51 admission and #53 Salamander/hopping, limits and
Android rebind. #52 has ClientHello fragmentation; UDP noise stays open.
#47 Linux TPROXY remains deferred. Existing documented Android UID visibility,
SS2022 UDP, WireGuard and VMess performance limitations remain visible.

Publication is requested but not yet complete. CI, remaining release-evidence
requirements, core annotated tag verification, the canonical SDK artifact lock
and consumer validation still apply. Do not replace a missing result with a
pass or broaden the two scoped owner decisions to unrelated cases.
