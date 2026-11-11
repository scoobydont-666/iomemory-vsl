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
establish full core behavior, device persistence, removal concurrency, or
package/boot recovery. Kernel-header compilation and supplied-source
reconciliation have separate evidence below.

[PR #6](https://github.com/scoobydont-666/iomemory-vsl/pull/6) carries the current
candidate and CI status. The initial real build run
[43080537080](https://github.com/scoobydont-666/iomemory-vsl/actions/runs/43080537080)
passed all 67 tests and real DKMS build/install on Ubuntu `6.8.0-149-generic`
and `7.0.0-42-generic`, including repeat install, second-kernel autoinstall,
version/vermagic, and library discovery. It tested the published candidate above
through merge candidate `f23074cf7fdb5c9c5995be272f42ddc4eff1b2ca`.
Later workflow changes add a manual artifact build and preserve its generated
inputs; consult the final PR head's actual run for that evidence. Any later code
change requires its affected checks and review to be renewed.

Session `storage_fixes` independently reconstructed the historical source from
`d171d8b` plus the supplied `ca4c075` patch, producing tree
`31922027d7a0a28752311b400838561b64df2168`. It confirmed the source and binary
comparisons in [the reconciliation record](../local-reconciliation-2026-11-11.md).
This was a separate historical comparison, not an independent review of the
agent's own storage implementation. No additional historical change needs to be
transplanted; the actual loaded artifact and firmware remain supplied host evidence.

## Follow-up delivery and reconciliation review

Session `independent_delivery_review` reviewed the manual-build workflow at local
commit `ef10fc18745479d1c3b6c4e3deda8b9c8067c210` and the subsequent staged
documentation tree `c6c7f84697fdf2323ae49b19b5cf3c08eb7cb207`. No blocking finding
remained. This receipt is a documentation-only addition after that review.

The workflow parsed successfully and every shell block passed `bash -n`.
The actual manual-build block was exercised with temporary command fixtures:
success returned zero, compiler failure propagated through `tee`, and wrong
version/vermagic each failed. These fixture checks do not replace its final
hosted kernel build. Retained artifacts include probe/objtool inputs and
module/core digests; complete release-record compiler/configuration evidence
still requires the corresponding target-platform record.

The reviewer independently verified 44 historical/reference hashes, 11 staged
counterparts, all 10 recorded patch IDs, the published candidate's tree, and
the unchanged driver tree in the supplied snapshot. Twelve archived payloads
match the supplied commit byte-for-byte, including the loader renamed to inert
text. Canonical patch/log whitespace is preserved in those captured files;
the whitespace check passes for authored changes. No code-check suppression was
introduced. The reviewer also checked the prior CI logs and artifacts against
the source identity and results described above.
