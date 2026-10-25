## Summary

Harden the existing DKMS installation path so a registered source snapshot can be rebuilt for a subsequent kernel without its original Git checkout, while preserving existing installations when a replacement build fails.

This change is based on `main` at `982f7164f97c40e13cc637cfcf9624c7f3ce8dfa` and is independent of the NUMA/DMA32 contribution in #157. No driver data-path C files or hardware-specific allocation behavior are changed.

## Motivation

The current path mixes Git-derived versioning, source preparation, DKMS registration and replacement. It first cleans against a kernel build tree, derives part of the package identity from the running kernel, and later invokes Git-based version operations from a copied source tree without `.git`. The dynamically selected source directory and fixed `PACKAGE_VERSION` lack a single explicit identity. Legacy status parsing depends on historical formatting, and replacement can remove a prior version with `--all` before building its successor. DKMS also does not explicitly select the same `gpl` target as `make module`.

These are lifecycle problems, separate from kernel-API compatibility or hardware qualification.

## Implementation

- Stage committed driver files with `git archive`, record the full commit and a kernel-independent source version, reject tracked changes and source/version collisions, and exclude untracked files. Relative in-tree symlinks are retained; external source links are rejected.
- Invoke DKMS with explicit module, version, target kernel and header directory. Serialize this installer's registration work and skip already-installed source/kernel pairs. Preserve prior registrations; avoid remove-all and forced replacement; propagate failed status/add/build/install operations.
- Generate `MODULE_VERSION` directly during DKMS builds without Git or linked-binary rewriting. Preserve the existing module-license declaration behavior. Set `AUTOINSTALL="yes"` and pass the target kernel to MAKE and CLEAN, with the same `gpl` target used by manual module builds.
- Add 17 offline regression tests, a verification guide and one ephemeral GitHub-hosted Ubuntu 24.04 job for real two-kernel DKMS testing. Repository permissions are read-only and checkout credentials are not persisted.

The normal entry point remains `sudo make dkms`; `KERNELVER` and `KERNEL_BUILD` select a non-running target. Registration requires a clean committed checkout, but subsequent DKMS builds do not. Packagers can set `DKMS_VERSION` explicitly. Timestamp/hash defaults do not replace a release-ordering policy; the guide documents same-second/backdated commits and selection among retained historical versions.

## Verification

Verified CI run: https://github.com/scoobydont-666/iomemory-vsl/actions/runs/37072130887

Runtime implementation: `192654e9e55835c14a35a0f75c89d88c46aa0062`.
The pull-request workflow checked out synthetic merge commit `3e03d999530540a0265c4a19d8fda5c13a34e9dd` over the base listed above. Subsequent submission documents do not change the runtime files.

On an Ubuntu 24.04.5 GitHub-hosted runner with DKMS `3.0.11-1ubuntu13`:

1. All 17 offline lifecycle/contract tests passed.
2. The full driver built, was signed by DKMS and installed for `6.8.0-146-generic`.
3. Repeating installation succeeded without a second build or destructive replacement.
4. `dkms autoinstall` built, signed and installed the same registered source for `7.0.0-38-generic`.
5. The target's installed status, exact kernel vermagic and matching module source version passed the workflow assertions.

The decoded job log was inspected, not only the green workflow conclusion. Source version in this run was `1790979742.3e03d9995305`. The offline tests also passed locally and cover failure preservation, invalid/dirty inputs, source collisions and Git-free metadata generation.

## Limitations and safety

Secure Boot was **disabled** on the CI runner: signing occurred, but key enrollment and Secure-Boot-enforced loading were not tested. Neither kernel was booted by this workflow, and no module load, device attach, sustained I/O integrity, initramfs or reboot validation was performed. A successful build is not proof of safe kernel-7 module loading or hardware compatibility.

No direct module load/unload, device attach/format/erase, bootloader or reboot operations are added. Administrator-configured DKMS hooks still apply. Preserving prior registrations is not a claim of transactionally rolling back an arbitrary failed install or hook. Review source-version ordering and retained-version selection for supported distributions before release, then validate on representative hardware under controlled maintenance.

Fork review: https://github.com/scoobydont-666/iomemory-vsl/pull/1
