# Reconciliation of the supplied local build evidence

## Current evidence and scope

This record supersedes the earlier "local source pending" status. The historical
tracked-source availability and comparison work is complete. It does not identify
the exact module bytes already running on a host or qualify a deployment.

The canonical machine-readable references are in
[`local-compare/evidence-index.json`](local-compare/evidence-index.json).
The earlier [`reconstruction.json`](local-compare/reconstruction.json), raw logs,
patches, and captured narrative remain historical evidence; do not rewrite them
to imply that later observations occurred during their original collection.

| Role | Immutable revision | Meaning |
| --- | --- | --- |
| Audited baseline | `13145f4abf6caa575c1dcb149925bef7a90e7f1f` | Source reviewed before PR #6. |
| Original supplied comparison | `26ab52e788093fda314b112bf3f42ecdcd432689` | Host-reported observations, hashes, logs, and historical patches. |
| Updated comparison notes | `9d3c88e8f9a6044a307bf16301871883fdb93ece` | Publishes the historical branch reference; only its comparison README changes. |
| Published historical source | `9328703e657943f1b15c0e94adc06762f3d22856` | Tree `31922027d7a0a28752311b400838561b64df2168`, parent `d171d8b16fb04f2218586335a98c2099a2dfc7b0`. |
| Pre-refactor PR candidate | `3325362db7016f1ab9185fa7f47087f3600a9c95` | Prior build evidence and preserved reconstruction receipt. Not a floating current-head alias. |

The new historical branch is `local/loaded-build-ca4c075-20261111`. Its commit
message describes the earlier `ca4c075` work; the supplier reports replaced
identity metadata. Git independently exposes the same full tree ID as the
previous patch reconstruction. A changed commit ID with an identical tree does
not introduce a new implementation. Its new committer timestamp is
2026-11-11T19:29:24Z; the comparison-note update is 2026-11-11T19:30:17Z.
These are publication metadata, not new hardware measurements.

The updated comparison's section 9 still says the historical tree exists only
in a host reflog. That sentence is superseded by the published commit above.
Its separate missing binary/build-log/firmware items are not resolved by publishing
source. The archived README in this PR explicitly represents the original
`26ab52e` capture, not a current inventory.

## Reproducible source verification

Run from a trusted checkout with the pinned commits present:

```sh
python3 tools/verify_source_evidence.py --list-commits
python3 tools/verify_source_evidence.py
```

The first command validates the index and lists exact commit IDs to fetch. The
second is network-free and reads the committed index at HEAD (or an explicit full
`--candidate` ID). It never checks out, applies, sources, or executes historical
files. CI fetches only the listed commit IDs before verification. Missing Git
objects, invalid schemas, mismatched trees/hashes, changed archives, symlinks, and
executable evidence fail the check rather than becoming a skip or warning.

The check establishes:

- Both comparison snapshots retain the baseline `root/` and top-level Makefile.
- The later snapshot changes only `docs/local-compare/README.md`.
- The published historical commit has the expected reconstructed tree and parent.
- Its `kinfo.c`, `kblock.c`, and `kscatter.c` still match the original audit baseline.
- All 33 recorded historical/baseline/original-snapshot SHA-256 comparisons
  (11 files across three source revisions) match actual Git blob contents.
- Logs, installed-DKMS records, patches, and the inert loader are preserved, and
  the original reconstruction receipt is unchanged from the prior candidate.

The emitted JSON names the actual checked candidate commit/tree. It separately
reports whether the runtime source tree changed from the previous candidate.
A source change cannot inherit that candidate's build qualification. Runtime,
firmware-binding, license-release, and hardware/release qualification fields
remain false: this tool cannot establish them. The existing binary verifier and
full contract/DKMS/manual build jobs remain separate mandatory checks.

## Historical implementation and binary inputs

No additional historical fix needs transplantation. The matching source retains
the audited procfs, persistence, scatter/gather, and completion defects. Its old
`pci.c` uses streaming DMA mapping instead of coherent allocation, and its old
`kmem.c` lacks subsequent alignment, overflow, order, and provenance guards.
Current main and PR #6 already supersede those implementations. The earlier
stable-patch-ID comparison remains recorded in `reconstruction.json`; the new
source verifier does not claim to rerun that separate patch-ID analysis.

The selected latest/cc63 core remains SHA-256
`61ee1425207b317c9c327c7c9080ab201fdd01625a6138d893abd63d42021a4d`.
The library remains SHA-256
`0a57f8e2090841019c7e2cf1a6b5bb5ca61ba5a89be6c7cdac5236d68e7ee14d`.
The original License/NOTICE bytes also match across the compared source trees.
Identity is not proof of original vendor provenance, complete source coverage,
or a licensing determination. No replacement core/library source or new release
terms were included in these latest two commits; preserve the original notices.

## Supplied runtime observations: not independently observed activation

| Artifact | Reported version | Reported srcversion |
| --- | --- | --- |
| Loaded module / matching historical worktree build | `6.17.0-40-ca4c075-3.2.16` | `A707FCA26416451F13ADC03` |
| DKMS-installed baseline | `1794116140.13145f4abf6c` | `279D601848406282AAECD69` |
| Repo-root untracked build selected by the local loader | `7.0.0-28-13145f4-3.2.16` | `35B7CB4F0D266A4502E28CE` |

The reported running kernel is `7.0.0-28-generic`. The historical version's
kernel-looking prefix is not its verified vermagic. The loaded module reportedly
lacks `dma32_clamp`; the installed baseline includes it. File metadata and
matching version/srcversion support identification but are not a cryptographic
measurement of code already loaded in memory. The historical `.ko`, original
build log, generated inputs, and untracked build-time changes remain absent.

The captured `fio-status` reports four attached 825GB ioScale2 adapters, 4096-byte
sectors, and firmware `v7.1.17`, revision `116786 Public`. It reports protected
power-loss status, which does not establish Linux flush/FUA ordering. Two firmware
filenames and hashes are recorded. The standard image is attributed to the
RemixVSL split archive; `fusion_dell_nosmp.fff` has unresolved origin. Neither
image bytes, a full header parse, a modification recipe, nor a binding from an
image file to the running cards was supplied. Matching version strings cannot
select the active image. These are remaining evidence requests, not new defects
in the published historical tree.

## Loader and next decision

The supplied loader chooses a fixed repo-root module inconsistent with the
reported loaded identity. Its format option forcibly formats `/dev/fct0` at a
hard-coded 2500GB size. It remains only as nonexecutable
`local-compare/load-fio-driver.sh.txt`, outside installation paths. Do not merge
that loader from the evidence branch or use it for qualification.

Keep PR #6 as a review candidate. The next local-team work is an identity-bound
activation/rollback plan, then isolated persistence, translated-IOMMU/NUMA,
allocation-failure/removal-concurrency, packaging/signing/initramfs, and reboot
qualification. Core command contracts, firmware identity, residual source/release
evidence, and owner-managed GitHub controls are separate gates. See
[qualification](qualification.md). No module, device, firmware, or boot operation
is authorized or performed by this source reconciliation.
