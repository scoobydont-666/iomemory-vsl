# Security and modernization remediation

## Scope and baseline

This change responds to the 11 November 2026 review of
`13145f4abf6caa575c1dcb149925bef7a90e7f1f`. It repairs the Linux adapter and
build/install contracts while preserving the selected core binary ABI and the
recent committed-source DKMS/DMA improvements. No module was loaded and no
live device, firmware, bootloader, or storage contents were modified by the
implementation work.

The maintainer has identified an updated/customized local driver/firmware copy
and additional licensing/source context. Reconciliation of that copy is pending.
The binary inventory and audit conclusions describe the GitHub baseline only;
they do not classify files that have not been supplied. Keep this PR in draft
until that comparison and the relevant qualification are complete.

## Finding-to-change map

| Finding | Repository correction | Remaining acceptance |
| --- | --- | --- |
| F01 proc reads | Kernel bounded-read helper handles offset/EOF/partial-copy errors. | Kernel fault/hardening behavior on target configuration. |
| F02 proc writes | Terminated range-checked numeric parsing; invalid trailing input rejected; bounded zero-padded strings; balanced allocation cleanup. | Actual core handler/string contracts with the selected local core. |
| F03 sequence cleanup | Per-open node/optional-handle context; failure-safe start/stop/release ownership. | Kernel allocation-failure injection and repeated reads. |
| F04 persistence | Correct queue-limit features; preserved BIO flags; explicit preflush/write/postflush callbacks; unsupported operations rejected; merge boundaries retained. | Exact core/card/firmware flush completion and power-loss ordering proof. |
| F05 DMA/completion | Legal DMA merging accepted; original and mapped counts/lengths kept distinct; bounded slices; each original BIO completed on pre-submit failure. | Translated-IOMMU and concurrency/pressure hardware tests. |
| F06 SG copying | Segment-relative cursors and page offsets separated; capacity/entry bounds enforced. | Representative hardware workloads and stress. |
| F07 lifecycle | Allocation/error-pointer checks, registered-state tracking, correct lock representation, native BIO-queue teardown, staged init rollback and add_disk errors. | Target-header compilation, lockdep, removal and unload/failure qualification. |
| F08 allocation policy | Host-only SG/map metadata uses slab allocations; coherent allocation preserves device NUMA topology; inclusive/exclusive order bounds corrected. | Opaque generic allocations retain DMA32 policy until callers are classified; performance tuning requires measurement. |
| F09 maintenance/readiness | Load-only validated erase/submission modes; exported readiness helper checks actual nodes and releases paths; kernel registration no longer waits for userspace /dev creation. | Command-level erase buffer contracts and offline firmware behavior remain unverified. |
| F10 objtool/build routes | One validated module path, exhaustive first-party object list, preserved kernel argv/flags, narrow known-core exception; unknown diagnostics fail. | Actual target-kernel builds and package artifacts; opaque-core validation remains limited. |
| F11 probes/metadata | Correct add_disk type probe, logging-independent failure status, checked metadata generation; supported builds avoid linked-binary version rewriting. | Required checks on the final candidate. |
| F12 installation | Dangerous legacy DKMS/EFI helpers retired; maintained source-snapshot installer owns library discovery and propagates failures. | Clean-host install, kernel upgrade, signing/initramfs, and rollback qualification. |
| F13 compatibility | Upstream add_disk/ccflags-y work adapted; bounded string implementation preserves strncpy copy/padding semantics for removed APIs. | Supported kernel matrix, including newer kernels only when actually tested. |
| F14 binary assurance | Manifest verifies exact opaque inputs; source/rights/provenance limits and transformation records documented; mutating fake_license target removed. | Compare maintainer local source/release evidence; resolve rights, provenance, module metadata, firmware and command audit. |
| F15 CI/docs/governance | PR/main validation scope expanded; offline negative controls and build evidence retained; fork-specific install/support guidance and security reporting instructions corrected. | Owner configures GitHub rulesets/private reporting; final-head CI and hardware release evidence remain mandatory. |

## Regression evidence

Run the repository suite and input check:

```sh
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s tests -p 'test_*.py' -v
python3 tools/verify_binary_artifacts.py
git diff --check
```

The new kernel tests extract actual production function bodies into small
userspace kernel/core fixtures. They establish adapter behavior and ownership,
including immediate/reentrant callbacks, zero/merged/error DMA results, partial
usercopy, boundaries, allocation failures, and registration rollback. They do
not simulate the complete kernel or establish hardware persistence guarantees.

Initial negative controls reproduced the original proc/sequence, initialization,
readiness, DMA-coalescing, SG-copy, BIO-flag, and build-wrapper/probe defects.
The readiness follow-up deliberately removes a newly introduced userspace-node
gate: successful kernel device registration must not depend on a mounted /dev or
an already running udev. The exported legacy helper accepts character and block
nodes and continues to report real lookup/time-out errors to explicit callers.

Binary tests reject changed/missing/extra inputs, incorrect ELF identity,
symlinks, and invalid manifests. Installer tests use temporary roots and a fake
DKMS backend; CI supplies separate real DKMS/header-build evidence. Preserve
negative tests for every validation exception and supported artifact route.

## Review and release boundary

Attach test counts/results and the actual CI run to the final PR head. Reviewers
must independently check persistence sequencing, callback ownership, DMA count
semantics, old/new kernel compatibility, cleanup ordering, and build exception
scope. Source changes invalidate affected prior evidence.

The implementation is a review candidate. It is not a hardware-qualified release
and has not been deployed. The remaining owner tasks are the local-tree
comparison, source/license evidence, GitHub controls, and the isolated platform
qualification in [qualification.md](qualification.md). Do not replace those
conditions with a successful build or quiet soak.
