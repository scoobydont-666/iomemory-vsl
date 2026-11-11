# Reconciliation of the supplied local build evidence

## Input and verified repository facts

The maintainer supplied branch `local/loaded-build-compare-20261111` at
[`26ab52e788093fda314b112bf3f42ecdcd432689`](https://github.com/scoobydont-666/iomemory-vsl/commit/26ab52e788093fda314b112bf3f42ecdcd432689).
Its parent is the reviewed baseline `13145f4abf6caa575c1dcb149925bef7a90e7f1f`.
The branch adds comparison documents, logs, historical patches and a loader script.
An exact Git diff confirms **no changes under `root/` or to the top-level Makefile**
relative to that baseline. There is no newer tracked driver/core implementation
in this snapshot to substitute into PR #6.

The supplied hash inventory matches the PR's committed binary manifest: selected
`latest`/`cc63` core SHA-256
`61ee1425207b317c9c327c7c9080ab201fdd01625a6138d893abd63d42021a4d`, and
`libvsl.so` SHA-256
`0a57f8e2090841019c7e2cf1a6b5bb5ca61ba5a89be6c7cdac5236d68e7ee14d`.
The snapshot reports the same selected host-side hashes. Those host statements
are supplied measurements; this PR did not access the host.

The sanitized evidence is preserved under [local-compare](local-compare/README.md).
Its copied narrative and logs are evidence, not executable instructions or proof
that a later host state is unchanged. The narrative's broad collection window
is not an independently verified clock/activation receipt.

## Installed, built, and loaded identities differ

The supplied measurements distinguish three artifacts:

| Artifact | Reported version | Reported srcversion |
| --- | --- | --- |
| Loaded module / matching historical worktree build | `6.17.0-40-ca4c075-3.2.16` | `A707FCA26416451F13ADC03` |
| DKMS-installed baseline | `1794116140.13145f4abf6c` | `279D601848406282AAECD69` |
| Repo-root untracked build selected by the local loader | `7.0.0-28-13145f4-3.2.16` | `35B7CB4F0D266A4502E28CE` |

The reported running kernel is `7.0.0-28-generic`. A kernel-looking component of
the historical version string does not establish its actual vermagic. Matching
version/srcversion values support the supplied identification but do not provide
a cryptographic hash of code already loaded in memory.

The loaded module reportedly has no `dma32_clamp` parameter. The installed
baseline does. Do not assume an installed module's parameters or behavior apply
to the running module. Before a controlled activation, record all identities,
module/firmware settings, the rollback artifact and known-good boot entry. After
activation, bind actual loaded identity to the activation/boot evidence.

## Firmware and licensing/source evidence

The supplied `fio-status` output describes four attached 825GB ioScale2 adapters,
firmware `v7.1.17`, revision `116786 Public`, and 4096-byte formatted sectors.
It reports protected power-loss status; this alone does not establish Linux
flush/FUA ordering or the behavior of this PR's code.

Two firmware filenames/hashes are recorded. The standard image is attributed to
the `RemixVSL/vsl_downloads` split archive; the `fusion_dell_nosmp.fff` image has
unestablished origin. No firmware image, full header parse, modification recipe,
or evidence binding a particular file to the running cards was supplied. The
same version string occurring inside two images cannot select the active image.

The package provides the existing EULA/NOTICE hashes and source-header notices.
It also reports no replacement `libvsl.so` source and no vendor source-release
package in the supplied tree. The existing kfio README and generated GPL module
tag remain different kinds of evidence. No new source-release terms were
supplied that resolve the binary-core licensing/provenance question. Preserve
the original notices and update [binary assurance](binary-assurance.md) if further
source or release documents become available; this is not a legal determination.

## Historical changes and the loader

The historical source was reconstructed in a detached worktree by applying
`patches/reflog-only-task15303-objtool/0001-ca4c075.patch` to
`d171d8b16fb04f2218586335a98c2099a2dfc7b0`. The patch passed `git apply --check`
and produces tree **`31922027d7a0a28752311b400838561b64df2168`**. Its only change
from the parent is the driver Makefile. Compared with the old branch tip
`ec10ef2abf4ab63f7050f3c9404af7f57c2e7fd7`, only `objtool_wrapper` differs,
with 38 insertions and two deletions. No build or host command was needed.

The reconstructed tree's `kinfo.c`, `kblock.c`, and `kscatter.c` are byte-identical
to the baseline, so the reviewed procfs, persistence, SG and completion defects
remain applicable. The historical `pci.c` substituted a streaming DMA mapping
for coherent allocation; current main and this PR retain the proper coherent
allocation/free pairing. The old `kmem.c` also lacks main's alignment, overflow,
order and provenance guards. Those historical implementations must remain
superseded. The exported objtool patches have the same stable patch IDs as
changes already represented by main's `eb33cb2` and `dd0c13b`.

The selected core/library hashes and all three License/NOTICE files are
byte-identical in the reconstruction, baseline, snapshot and reviewed PR tree.
The PR's pinned validation exception therefore remains tied to the same input
bytes. [Machine-readable comparison evidence](local-compare/reconstruction.json)
records hashes, patch IDs and tree differences.

This reconstruction establishes the source described by the supplied patch,
not the exact bytes already loaded on the host. The matching historical `.ko`,
its original build log, generated inputs and untracked build-time changes were
not supplied. Current DKMS object-selection evidence must not be assigned to
the historical loaded module without its own build evidence.

The supplied `load-fio-driver.sh` selects a hard-coded repo-root module that
differs from the reportedly loaded module. Its `format` option executes forced
formatting of `/dev/fct0` at a hard-coded 2500GB size, and its other path attaches
that fixed device. It is retained as inert text only. Do not incorporate that
helper into deployment automation; retire it on the host or replace it through
a separately reviewed, identity-bound maintenance procedure. This PR performs
no load, unload, attach, format, or firmware update.

## Resulting PR disposition

The provided source comparison is complete: it does not require transplanting a
different current tracked driver or replacing the pinned binary inputs. It does
require an explicit deployment identity correction plan because the reported
loaded, installed and repo-root artifacts differ.

PR #6 remains a draft for the isolated hardware, persistence, removal/concurrency,
package/signing/boot recovery and residual core/source evidence described in
[qualification](qualification.md). Successful builds prove neither activation of
this candidate on that host nor safety of the old loader. No host mutation is
part of this reconciliation.
