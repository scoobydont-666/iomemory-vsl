# Independent review record: security modernization

## Candidate identity

- Baseline: `13145f4abf6caa575c1dcb149925bef7a90e7f1f`
- Published candidate: `547fc5432e34dda6927e09cbd56c3f23620abb67`
- Published Git tree: `162194aad659215fde07696226941e88c86b6f2e`
- Reviewed local candidate: `af839defc67dda64f16c5e9f5fb7263dad433d28`

Each published commit tree was checked against its tested local counterpart.
The GitHub API created different commit metadata/identities while preserving the
exact trees. The two reviewers were independent agent sessions that authored no
changes in the candidate. Their findings are source-review evidence, not GitHub
maintainer approvals or authorization to merge/deploy.

## Kernel-contract review

Session `independent_kernel_review` reviewed the complete candidate and independently
ran 67 tests (14.099 seconds, exit zero) at the code revision preceding the final
DKMS documentation-only commit. It also read that documentation delta and checked
the baseline-to-head diff for whitespace errors.

It inspected proc/sequence ownership, staged initialization, allocation policy,
original-versus-mapped DMA counts, SG bounds, ordered-I/O inline/error callbacks,
queue/disk registration and teardown, and the integrated build/package paths.
Primary Linux sources and selected shipped-core disassembly supported the checked
API/ownership contracts. No additional source-level blocker remained.

The integration review caught a userspace `/dev` dependency introduced while
repairing readiness. Device registration now relies on kernel registration status;
the exported legacy helper handles both character and block nodes. The reviewer
confirmed the correction and its early-boot rationale.

## Delivery/security review

Session `independent_delivery_review` independently ran all 67 tests at the reviewed
head (12.959 seconds, exit zero), verified all 10 binary inputs, checked the
baseline-to-head diff, and confirmed a clean worktree.

Its initial review found two build defects before publication: Git-free package
builds lacked version metadata, and Kbuild could overwrite generated metadata.
Both were corrected with regressions. It reviewed objtool exception scope,
canonical build routes, probe status, package metadata, installer ownership,
CI isolation, provenance wording, and the kernel changes' main failure paths.
No blocking source finding remained. A minor provenance-wording consistency
suggestion is incorporated in a subsequent documentation-only change.

## Verdict and remaining gates

Both reviews support publication as a **draft review candidate**. They do not
establish kernel-header compilation, full core behavior, device persistence,
removal concurrency, package/boot recovery, or equivalence to the maintainer's
custom local source and firmware.

[PR #6](https://github.com/scoobydont-666/iomemory-vsl/pull/6) carries the current
candidate and CI status. The initial real build run is
[43080537080](https://github.com/scoobydont-666/iomemory-vsl/actions/runs/43080537080).
Consult its actual result and later runs; this record does not mark a pending
or failed run as passing. Any later code change requires its affected checks and
review to be renewed.
