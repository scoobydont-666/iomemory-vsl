# Artifact identity and activation handoff

## Current boundary

Historical source recovery and comparison are complete. The supplied snapshot
reports three distinct module identities: loaded historical `ca4c075`, installed
DKMS baseline `13145f4`, and the repo-root build used by an old loader. Do not
assume a successful install activated the candidate. Do not use the archived
loader, its forced-format option, or a fixed `/dev/fct0` for this procedure.

The new `tools/driver_preflight.py` turns the identity comparison into a repeatable,
read-only JSON report. It is not an installer, a firmware updater, a storage test,
or a release approval. It invokes only the system modinfo program, reads a small
sysfs allowlist, and hashes explicitly selected regular artifact files. It never
loads/unloads modules, opens storage devices for hashing, or runs fio utilities.
No live host was accessed during its implementation.

## Before an approved activation

Preserve the known-good module and kernel separately, along with their source
registration, configuration, parameter choices and recovery instructions. Record
the selected candidate's build log, generated capability header, exact core hash,
version, srcversion, vermagic and file digest. Expected values must come from the
candidate build receipt, not from whichever module happens to be installed.

Run from the trusted PR checkout on the intended host, after the target-kernel
candidate is built/installed but before activation. Set these variables to the
reviewed artifacts rather than using example values blindly:

```sh
# Required inputs from the reviewed build receipt:
: "${candidate_module:?absolute path to the candidate .ko or compressed .ko}"
: "${target_kernel:?exact intended kernel release}"
: "${expected_version:?module version from the candidate build receipt}"
: "${source_revision:?full reviewed Git commit ID}"
umask 077
python3 tools/driver_preflight.py \
  --candidate-module "$candidate_module" \
  --target-kernel "$target_kernel" \
  --expected-version "$expected_version" \
  --source-revision "$source_revision" > preflight-before.json
```

The file contains candidate, installed and loaded metadata, bounded parameter
values, on-disk hashes and explicit limits on what was verified. Add one or more
`--firmware /absolute/path/to/image.fff` arguments to inventory supplied image
files. This does not bind an image to a card or parse a vendor firmware format.
Files must be nonempty regular files no larger than 128 MiB; final symlinks,
FIFOs, devices, changing files and duplicate image paths are rejected. A missing
installed module, missing required metadata or unreadable sysfs fails collection.
Read permissions may require an administrator, but the tool never invokes sudo.

Exit codes:

| Code | Meaning |
| --- | --- |
| 0 | Requested metadata comparisons agree. In preparation mode, an older loaded module is allowed but clearly reported. This is not activation or release approval. |
| 2 | Collection succeeded, but expected/candidate/installed metadata differs, or required active metadata does not match. Keep the report and resolve the mismatch. |
| 1 | Collection failed; no successful JSON receipt is emitted. Do not interpret an empty redirected file as a pass. |

If using `set -e`, handle code 2 explicitly as a diagnostic failure; do not hide it
with `|| true`. No report is automatically uploaded. Review filenames, signer
subjects and any error paths before public sharing. Never include private keys,
credentials, serial inventories, or unrestricted host logs.

## Controlled activation and after-state

Module activation/removal, boot changes and storage tests belong to the separate
local maintenance procedure. Establish the device/consumer map, quiesce consumers,
verify recovery access and select disposable test media before any such operation.
This document intentionally provides no auto-format, auto-flash or blind unload
command. Preserve the previously running artifact rather than assuming the
currently installed file is the rollback artifact.

After the approved activation, rerun the same command with `--require-active`,
writing `preflight-after.json`. This also checks that the running kernel matches
the target, that the loaded module is live, and that loaded version/srcversion
match the candidate. A detected change in loaded metadata during collection is
fatal. Match the before/after reports with the exact activation and boot record.

The source revision remains explicitly operator-asserted. Matching sysfs metadata
is not a cryptographic measurement of loaded code. Different compressed/signed
file hashes do not necessarily mean different compiled code. A signer string does
not prove trust or enforcement. Hardware, persistence, firmware binding and
release qualification remain false in every preflight report.

## Remaining local evidence and acceptance

| Work package | Required result | Execution boundary |
| --- | --- | --- |
| Loaded artifact and rollback | Candidate/installed/loaded identities, build inputs, preserved rollback artifact and actual activation record agree. | Local operator; never inferred from Git or a CI build. |
| Persistence and integrity | Disposable-media checksum tests, flush/FUA ordering oracle, controlled interruption and recovery results. | Isolated test host; no production media. |
| DMA/platform | Translated IOMMU, supported NUMA placements, low-memory pressure, multiple cards and expected DMA policy. | Actual supported hardware and kernel tuple. |
| Lifetime/failure | Allocation and usercopy faults, registration failures, concurrency/removal and lock diagnostics. | Isolated instrumented kernel. |
| Packaging and boot | Clean-host packages, trusted and rejected signatures, initramfs inspection, boot and verified fallback. | Local platform owner; hosted signing without enforcement is insufficient. |
| Core/firmware assurance | Exact core command/buffer contract, image provenance and image-to-card evidence, any available original source/release terms. | Supplier evidence; unchanged hashes do not establish rights or behavior. |
| Repository settings | Required checks/rulesets and private security reporting configured by owner. | GitHub administration, separate from source-file writes. |

Record completed results and immutable references in the release record in
[qualification.md](qualification.md). Leave absent tests open; neither this tool
nor a green Actions badge may manufacture their results.
