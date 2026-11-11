# Release qualification and recovery

## Current evidence boundary

The review baseline is `13145f4abf6caa575c1dcb149925bef7a90e7f1f`. Its historical
[CI run](https://github.com/scoobydont-666/iomemory-vsl/actions/runs/42450613664)
ran 19 tests and performed real DKMS build/install against Ubuntu
`6.8.0-149-generic` and `7.0.0-42-generic` on a PR head. It is not evidence for
later source revisions, a load test, or a persistence test.

The security-modernization PR adds contract regressions and code repairs. Its
initial [CI run 43080537080](https://github.com/scoobydont-666/iomemory-vsl/actions/runs/43080537080)
passed 67 offline tests and real DKMS build/install for both header releases above,
including repeat installation, Git-free second-kernel autoinstall, version/vermagic,
and library discovery. This run covers PR head `547fc5432e34dda6927e09cbd56c3f23620abb67`
through GitHub merge candidate `f23074cf7fdb5c9c5995be272f42ddc4eff1b2ca`.
Subsequent workflow changes add the Git-free manual `modules` route and preserve
its generated header and objtool evidence; their actual result must be checked
on the final PR head.

The [supplied local comparison](local-reconciliation-2026-11-11.md) is complete
for tracked source. Its reported loaded, installed, and repo-root module identities
differ. Hardware qualification, a controlled artifact transition, signing/boot
recovery, core rights/provenance, and GitHub settings remain separate acceptance
conditions. There is no claim that every 5.x, 6.x, or 7.x kernel or every Fusion-io
card is supported.

## Required evidence lanes

| Lane | Required behavior and evidence |
| --- | --- |
| Offline contracts | Proc EOF/beyond-EOF/partial-copy errors; numeric ranges and invalid input; failed sequence start; original/mapped DMA counts and lengths; SG offsets/capacity; exact completion on submission failure; preflush/write/postflush sequencing and errors; allocation/initialization rollback; build validation negative controls; installer repeat/failure behavior. |
| Kernel builds | Actual intended distro kernels plus maintained CI targets; exact headers/config/compiler; generated capability header; selected binary hash; complete object validation; module SHA-256/version/vermagic. Missing or failed checks remain failures. |
| Build/install routes | Maintained DKMS, manual, and every advertised package route; clean installation plus library discovery, repeat install, kernel upgrade/autoinstall, interruption/failure, and retention of known-good versions. |
| Isolated kernel faults | Allocation failure at each construction stage, partial/invalid usercopy, failed publication, repeated attach/detach, lockdep and memory diagnostics where practical. Opaque binary coverage is limited. |
| Disposable storage | Checksum-verified sequential/random and aligned/misaligned I/O, varying queue depth, merge boundaries, flush/FUA, discard, memory/DMA pressure, translated IOMMU, supported NUMA/multi-device placement, concurrency/removal, restart and recovery. |
| Persistence | Confirm the core/card's flush completion guarantee; exercise controlled interruption and recovery on explicitly disposable media with an independent data/ordering oracle. A quiet soak cannot establish this property. |
| Signing and boot | Accepted and rejected module signatures, expected Secure Boot/lockdown policy, initramfs contents for the target kernel, known-good fallback boot entry, and verified loaded module after reboot. |
| Operations | Source/module/blob identity, firmware and device model, current kernel/configuration, intended DMA policy, performance/integrity results, recovery owner, and residual binary risk acceptance. |

All tests involving media, firmware, module activation/removal, power interruption,
or boot changes belong in an approved isolated maintenance procedure. The offline
suite and hosted CI do not issue these actions.

## Capture artifact identity before activation

Use the target kernel release, not an assumed match with the running kernel:

```sh
target_kernel=YOUR_TARGET_KERNEL_RELEASE
git rev-parse HEAD
python3 tools/verify_binary_artifacts.py
dkms status -m iomemory-vsl -k "$target_kernel"
modinfo -k "$target_kernel" -F filename iomemory-vsl
modinfo -k "$target_kernel" -F version iomemory-vsl
modinfo -k "$target_kernel" -F vermagic iomemory-vsl
modinfo -k "$target_kernel" -F license iomemory-vsl
modinfo -k "$target_kernel" -F signer iomemory-vsl
```

Hash the actual file reported by `modinfo`, record any compression, and verify
the expected module is included in the intended initramfs using the distribution's
inspection tool. Check signature enforcement and key enrollment separately;
a nonempty signer alone does not prove that the target kernel trusts the key.

After an authorized activation/reboot, capture `uname -r`, the loaded module's
sysfs version, the driver initialization log, attachment and device health, and
the qualification workload results. A disk file's hash does not identify code
already loaded into memory; use the controlled boot/activation record to bind
those facts. Sanitize serial numbers and host details before public posting.

## Recovery and performance

Retain the known-good kernel, matching module, and source registration. Confirm
the boot fallback and how the operator will select the previous version before
activation. Do not erase older registrations to make installation appear clean.
A source revert does not reverse firmware updates or persisted media changes.

After correctness passes, measure requested/allocated memory, low-zone and bounce
usage, allocation failures, throughput, CPU/IRQ cost, and p99/p99.9 latency under
representative pressure. Keep the opaque-core low-memory policy until buffer
contracts are known. Scope any relaxed policy by proven device/platform needs.

## Release record

For each supported tuple retain:

```text
Source revision and reviewed base:
Final PR and integrated revision:
Input core/userspace hashes and provenance review:
Kernel release/configuration, headers and compiler:
Module digest, version, vermagic and signer:
Card/OEM model, firmware, NUMA and IOMMU/DMA policy:
Offline/CI/build/package evidence:
Kernel-fault and storage/persistence evidence:
Signing/initramfs/activation/reboot evidence:
Recovery procedure and verification:
Independent reviews and remaining exceptions:
```

An incomplete record is an unqualified configuration. Use draft/review status
until the relevant gates are satisfied; do not label missing evidence as a pass.
