# Upstream submission handoff — 2026-10-02

The connected integration successfully wrote the fork, but attempts to create a
PR in `RemixVSL/iomemory-vsl` and comment on its existing #157 returned HTTP 403,
`Resource not accessible by integration`. No new upstream PR or upstream
comment was created. These files preserve the submission text for an authorized
account. Do not change repository visibility, credentials or permissions as a
workaround.

From an isolated checkout of `astra/dkms-lifecycle-20261002`, first inspect the
upstream PR list to avoid duplicates, then use an authenticated GitHub CLI account
that is allowed to create upstream contributions:

```sh
gh pr list --repo RemixVSL/iomemory-vsl --state all \
  --head scoobydont-666:astra/dkms-lifecycle-20261002

# Only if no equivalent submission exists:
gh pr create --repo RemixVSL/iomemory-vsl --base main \
  --head scoobydont-666:astra/dkms-lifecycle-20261002 --draft \
  --title 'dkms: rebuild from committed source snapshots without Git metadata' \
  --body-file docs/upstream/dkms-pr.md
```

Do not create another NUMA PR. Existing upstream #157 is the canonical thread.
Read its current discussion before posting the prepared follow-up once:

```sh
gh pr view 157 --repo RemixVSL/iomemory-vsl --comments
gh pr comment 157 --repo RemixVSL/iomemory-vsl \
  --body-file docs/upstream/numa-review.md
```

Record the resulting upstream URL in fork #1. Fork #2 tracks the existing NUMA
contribution's review and remains draft. Keep the DKMS implementation, allocator
changes and kernel-7 objtool work independently reviewable. Do not deploy the
DKMS-only branch to a machine requiring hardware-specific patches absent from
that branch. No merge, storage operation or reboot is authorized by this handoff.

Verified runtime CI evidence is linked in `dkms-pr.md`; hardware activation and
boot qualification remain separate acceptance gates.
