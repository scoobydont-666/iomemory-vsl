# Repository completion pass — 11 November 2026

## Changes in this pass

- Added a read-only candidate/installed/loaded-module preflight with explicit
  expected version, target kernel and source revision, bounded artifact hashing,
  optional firmware-file inventory and no activation/device commands.
- Added 25 hardware-free regressions covering the actual three-identity mismatch,
  supplied 23-digit legacy srcversion values, compressed/signed file distinctions,
  invalid metadata, changing artifacts, symlinks, FIFOs, device nodes and CLI exits.
- Updated checkout and upload-artifact to full-SHA-pinned Node 24 releases:
  checkout v7.0.1 `3d3c42e5aac5ba805825da76410c181273ba90b1`;
  upload-artifact v7.0.2 `cf430e030ddbb5b0abf93d22962f4752f3646cd9`.
  Tag-to-commit and action.yml runtime/input definitions were inspected upstream.
- The existing hosted job still runs source/binary verification, the entire test
  suite, both DKMS builds, repeat installation, Git-free autoinstall, and the
  separate manual build. It now also runs the preflight against the real manual
  and DKMS artifacts, with no module activation.
- Evidence collection/upload now uses `!cancelled()` instead of `always()`, and
  missing upload inputs fail. A stable new concurrency namespace avoids sharing
  the old queued-run group without weakening any checks or moving public PR code
  to a persistent/self-hosted storage host.
- Retain a deterministic Git source archive and its SHA-256 alongside the build
  receipts. Git archive excludes generated files, credentials and signing keys;
  the repo's already tracked binary inputs remain part of the source archive.
- Added [the executable local-team handoff](activation-handoff.md).

## Validation actually performed before publication

All 25 new tests passed locally on regular fixture files. YAML parsed and every
embedded workflow shell block passed `bash -n`. The tool was also exercised with
real system modinfo against a freshly compiled, synthetic no-op module using
Debian `6.12.107+deb13-amd64` headers. That was not an ioMemory driver build, and
no module was loaded. Uploaded tool/test blob identities were compared with the
locally tested bytes.

The expected full hosted suite is 115 tests (the prior 90 plus these 25). Record
the current-head CI run and actual outcome on PR #6. This document does not claim
a hosted pass in advance and does not reuse the older head's green badge.

## CI incident context

The preceding run `43096011352`, head `0052c854`, was still queued with no job
result when this pass began. GitHub's status API reported an Actions incident
starting at 20:48 UTC and a newer 21:21 UTC summary reported operational status.
That overlaps this work, but does not prove the cause of the earlier queue.
Do not change permissions, spend limits or hardware policies based on this
inference. A new candidate run must produce its own checks and evidence.

References: https://www.githubstatus.com/api/v2/summary.json and
https://docs.github.com/en/actions/how-tos/troubleshoot-workflows .

## Completion boundary

No runtime driver code, opaque binary input, firmware, archived local evidence,
or original reconstruction record was changed by this completion pass. The
source fixes and historical-source comparison remain in PR #6. Repository code
and tooling are not the same as platform acceptance: final-head CI, actual
activation/rollback, persistence, IOMMU/NUMA/concurrency, package/signing/initramfs,
firmware identity and residual core/source assurance are distinct gates.

Keep the PR unmerged and unreleased until the applicable gates in
[qualification.md](qualification.md) have their own evidence. The local handoff
assigns those operational tests without implying that a remote source edit ran
them. Repository rulesets and security-reporting settings also remain owner
administration tasks; source write access is not evidence they were changed.
