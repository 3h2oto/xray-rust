# 0.8.1 release preparation

Requested on 2026-10-18. The candidate includes all changes merged into `main`
through `2255fdf919efcbbda4ea5a13f0fd949a8c61f835`, plus the 0.8.1 workspace,
lockfile, generated configuration-contract and release documentation updates.
Publication is pending.

## Scope

- Apple startup-probe preflight before tunnel routes/DNS, with cancellation,
  timeout and failure handling; additive C ABI 1.12 and matching Swift sources
  ([#70](https://github.com/aimalygin/xray-rust/pull/70)).
- Merged Rust dependency updates and the core Android Gradle/AGP/Kotlin build
  updates. Protocol and configuration formats are unchanged.
- UDP/WireGuard fixture corrections, scheduled interoperability repairs and
  CI artifact updates. Fixture fixes do not change released client binaries.

## Evidence boundary

The published [0.8.0 archive](releases/v0.8.0-device-evidence.json) remains
bound to core `fcce4be2771c1fb3f11e9503741d39a4d8df314e`. The
[Android UDP follow-up](device-results/2026-10-13-issue56/README.md) used the
existing release APKs. The
[iPhone startup-probe report](device-results/2026-10-17-issue69-ios/README.md)
and [Apple TV report](device-results/2026-10-17-issue69-tvos/README.md) identify
their pre-rebase source snapshots, native binaries and Debug applications.
These reports support the changes but are not fresh full-candidate 0.8.1
device/performance acceptance. Original failures and limitations remain intact.

The ordinary main CI passed at `2255fdf`; its optional release jobs were
skipped. The existing v0.8 schema-4 gate requires the exact release commit and
tree. Do not relabel an old archive or replace missing measurements with unit
test results. The 0.8.0-specific owner decisions are historical records, not
new 0.8.1 decisions. The existing v0.8 Android network/lock omissions retain
their documented scope.

## Candidate qualification snapshot

The [2026-10-18 measurement report](device-results/2026-10-18-v081-candidate/README.md)
records exact-candidate CI, physical-device and performance results, including
original fixture failures and controls. Full core and SDK CI passed. Thirteen
schema-4 performance metrics and the historical calibrated checks passed.
Apple Wi-Fi/cellular and lock/wake actions were postponed by the owner, not
waived. The initial SS2022 latency comparison exceeded 5%; a longer diagnostic
series did not reproduce it, but the uncertainty interval crosses the 5% bound.
The existing SS2022 remote-EOF limitation remains explicit. No passing release
evidence archive or public tag has been created. This documentation commit does
not replace the qualified runtime source identity `5b61eee`.

## Publication order

1. Commit the candidate, pin its exact revision/tree in `xray-rust-mobile`,
   synchronize canonical adapters/header/tests, and pass both repositories' CI.
2. Run full core release CI, collect the required candidate-bound device and
   host evidence, and pass `v08-release-evidence.yml` on that exact commit.
3. Verify and publish the annotated core tag without moving an existing tag.
4. Change the SDK candidate pin to the verified core tag, prepare the canonical
   Apple archive, and merge its generated checksum/source lock.
5. Publish the verified SDK tag, XCFramework, four-ABI AAR and Maven artifacts;
   resolve the published packages from clean external consumers.

Until those steps pass, the SDK remains an untagged candidate with unprepared
artifact locks and no public 0.8.1 release.
