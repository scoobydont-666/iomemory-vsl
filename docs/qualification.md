# Release qualification and recovery

## Evidence ledger and current boundary

The review baseline is `13145f4abf6caa575c1dcb149925bef7a90e7f1f`. Historical
[CI run 42450613664](https://github.com/scoobydont-666/iomemory-vsl/actions/runs/42450613664)
ran 19 tests and DKMS build/install against Ubuntu `6.8.0-149-generic` and
`7.0.0-42-generic` on a PR head. It does not qualify later source or hardware.

The security-modernization candidate at
`3325362db7016f1ab9185fa7f47087f3600a9c95` passed
[run 43082972226](https://github.com/scoobydont-666/iomemory-vsl/actions/runs/43082972226)
through merge candidate `e6336eed5bfc95eec557bc644673eaf1c057e940` (identical tree
`2f1ddb03ca2fde99a604f555c42e253b4f6580e9`). Its 67 tests, both real DKMS builds,
repeat install, Git-free autoinstall and manual modules build, module metadata,
library discovery, and evidence upload passed. Signing occurred with Secure Boot
disabled; no module was loaded. That run remains evidence for that exact tree,
not an automatically current "final" run.

The latest [source reconciliation](local-reconciliation-2026-11-11.md) incorporates
comparison `9d3c88e8f9a6044a307bf16301871883fdb93ece` and published historical source
`9328703e657943f1b15c0e94adc06762f3d22856`. The historical source is now directly
available, not just reconstructible. The evidence refactor adds 23 disposable-Git
regressions and an exact-candidate source receipt. It deliberately leaves runtime
code and binary inputs unchanged; the new final-head CI must still pass. Attach
its run to the PR rather than rewriting an older run's scope.

## Gate state: source agreement is not deployment approval

| Gate | Evidence/disposition | Owner's next action |
| --- | --- | --- |
| Historical tracked-source availability | Resolved by published commit and matching full tree. | No more reflog recovery is needed for this tree. |
| Source and input comparison | Executable verifier plus binary manifest; fail on mismatches. | Review the exact-head JSON receipts and final CI. |
| Loaded artifact identity/transition | Open: loaded, DKMS-installed, and repo-root artifacts differ. | Preserve rollback artifact; collect exact build/module identities and controlled activation record. |
| Firmware identity | Open: filenames/hashes/status strings, no image-to-card binding. | Supply image provenance/header evidence and a defensible active-image binding; no blind update. |
| Core/source/release evidence | Open for the binary core/library and command contracts. | Preserve notices; supply additional source/release evidence when available and record residual assurance limits. |
| Storage/platform and boot qualification | Open; hosted builds are not hardware acceptance. | Run the isolated lanes below on explicitly disposable media. |
| Repository controls | Outside a source PR. | Owner reviews rulesets and private reporting settings. |

The supplied host records are not a fresh host inspection. No blanket support
claim is made for every kernel or Fusion-io model. The source verifier, contract fixtures, and hosted build job do not authorize
deployment.

## Required evidence lanes

| Lane | Required behavior and evidence |
| --- | --- |
| Source evidence | Pinned original/latest snapshots, historical commit/tree/parent, actual Git blob hashes, preserved inert archives, candidate commit/tree. Missing refs and stale receipts fail. |
| Offline contracts | Proc EOF/beyond-EOF/partial-copy errors; numeric ranges and invalid input; failed sequence start; original/mapped DMA counts and lengths; SG offsets/capacity; exact completion on submission failure; preflush/write/postflush sequencing and errors; allocation/initialization rollback; build validation negative controls; installer repeat/failure behavior. |
| Kernel builds | Intended distro kernels plus CI targets; exact headers/config/compiler; generated capability header; selected binary hash; complete object validation; module SHA-256/version/vermagic. Missing or failed checks remain failures. |
| Build/install routes | Maintained DKMS, manual, and advertised packages; clean installation plus library discovery, repeat install, kernel upgrade/autoinstall, interruption/failure, and retention of known-good versions. |
| Isolated kernel faults | Allocation failure at each construction stage, partial/invalid usercopy, failed publication, repeated attach/detach, lockdep and memory diagnostics where practical. Opaque binary coverage is limited. |
| Disposable storage | Checksum-verified sequential/random and aligned/misaligned I/O, queue depths, merge boundaries, flush/FUA, discard, memory/DMA pressure, translated IOMMU, supported NUMA/multi-device placement, concurrency/removal, restart and recovery. |
| Persistence | Confirm the core/card's flush completion guarantee; controlled interruption/recovery on disposable media with an independent data/ordering oracle. A quiet soak cannot establish this property. |
| Signing and boot | Accepted and rejected module signatures, expected Secure Boot/lockdown policy, target initramfs, known-good fallback boot entry, and verified loaded module after reboot. |
| Operations | Source/module/blob identity, firmware/device model, kernel/configuration, intended DMA policy, performance/integrity results, recovery owner, and residual binary risk acceptance. |

Media, firmware, module activation/removal, power interruption, and boot changes
belong in an explicitly approved isolated maintenance procedure. Neither source
verification nor hosted CI issues these actions. Do not use the archived loader.

## Capture artifact identity before activation

Use the target kernel release, not an assumed match with the running kernel:

```sh
target_kernel=YOUR_TARGET_KERNEL_RELEASE
git rev-parse HEAD
python3 tools/verify_source_evidence.py
python3 tools/verify_binary_artifacts.py
dkms status -m iomemory-vsl -k "$target_kernel"
modinfo -k "$target_kernel" -F filename iomemory-vsl
modinfo -k "$target_kernel" -F version iomemory-vsl
modinfo -k "$target_kernel" -F srcversion iomemory-vsl
modinfo -k "$target_kernel" -F vermagic iomemory-vsl
modinfo -k "$target_kernel" -F license iomemory-vsl
modinfo -k "$target_kernel" -F signer iomemory-vsl
```

Hash the actual file reported by modinfo and record its compression. Preserve the
known-good artifact, not only the currently installed candidate. Inspect the
intended initramfs with the distribution's inspection tool. Verify signature
trust/enforcement separately; a nonempty signer is not proof of acceptance.

After an authorized activation/reboot, capture uname, loaded sysfs version and
srcversion, initialization log, actual parameters, attachment/health, and test
results. Bind those to the controlled activation and exact artifact; an on-disk
hash alone does not identify in-memory code. Sanitize host/serial details before
public posting. Do not include signing private keys or credentials.

## Recovery and performance

Retain the known-good kernel, module, and source registration. Confirm how the
operator selects the fallback before activation. Do not erase older registrations
to make installation appear clean. A source revert does not reverse firmware
updates or media changes.

After correctness passes, measure requested/allocated memory, low-zone and bounce
usage, allocation failures, throughput, CPU/IRQ cost, and p99/p99.9 latency under
representative pressure. Keep the opaque-core low-memory policy until buffer
contracts are known. Scope any relaxed policy by proven device/platform needs.

## Release record

For each supported tuple retain:

```text
Source revision, reviewed base, final PR and integrated revision:
Source-evidence receipt and binary manifest verification:
Input core/userspace hashes and provenance review:
Kernel release/configuration, headers and compiler:
Module digest, version, srcversion, vermagic and signer:
Card/OEM model, firmware, NUMA and IOMMU/DMA policy:
Exact-head offline/CI/build/package evidence:
Kernel-fault and storage/persistence evidence:
Signing/initramfs/activation/reboot evidence:
Recovery procedure and verification:
Independent reviews and remaining exceptions:
```

Incomplete records describe unqualified configurations. Keep draft/review status
until relevant gates are satisfied; never label missing evidence as a pass.
