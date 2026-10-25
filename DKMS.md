# DKMS: durable source registration and kernel-upgrade verification

DKMS support already existed in this project. This change hardens its source
registration and build lifecycle; it does not add a second kernel-upgrade daemon
or claim compatibility with every future kernel.

## Installation

Install your distribution's DKMS package, Git, build tools (including GCC and
Perl), and the headers for every kernel you intend to boot. On Ubuntu/Debian,
keep the appropriate headers metapackage installed so later kernel packages also
bring their headers. Custom and Proxmox kernels need their matching headers,
not a generic Ubuntu headers package.

From a clean, committed checkout of the **reviewed source revision**:

```sh
sudo make dkms
# Alternatively, build for an installed, not necessarily running kernel:
sudo make dkms KERNELVER=YOUR_TARGET_KERNEL_RELEASE
```

The target defaults to `uname -r`. `KERNEL_BUILD=/path/to/headers` can override
the target's header directory. The top-level DKMS target does not clean against
the running kernel first. The installer invokes DKMS explicitly for the target.
Use `make dkms`, not the historical `module_operations.sh -d` implementation.

Only committed driver files and the committed `libvsl.so` are staged. Tracked
local changes are rejected; untracked files and build products are not copied.
Make a commit before installing a local patch. Source symlinks must resolve
within the archived driver tree. The selected checkout must include any hardware
or kernel-specific fixes the machine needs; DKMS does not import other branches.

Registration uses a source version independent of the running kernel:
`COMMIT_TIMESTAMP.SHORT_COMMIT`. It is recorded in the staged `dkms.conf`,
`MODULE_VERSION`, and `/usr/src/iomemory-vsl-VERSION/.dkms-source-revision`.
The full commit is retained in the latter file. Subsequent DKMS builds need
neither the original checkout nor Git metadata.

Packagers may explicitly set a stable, monotonically increasing `DKMS_VERSION`
(e.g. through `sudo make dkms DKMS_VERSION=...`). A version must not identify
multiple source snapshots. An existing source/version directory is compared to
the committed snapshot and never overwritten on a collision. Timestamp-based
versions are a convenience, not a release-ordering policy: backdated commits,
same-second commits and mixed historical version schemes require checking
which version your installed DKMS selects.

`DKMS_SOURCE_TREE`, `DKMS_STATE_TREE`, and `DKMS_LIB_DIR` override installation
directories for controlled packaging/testing. Normal installations must keep
the defaults (`/usr/src`, `/var/lib/dkms`, `/usr/lib/fio`) unless the system's
DKMS configuration and kernel hooks are deliberately configured to match.
Filesystem permissions and DKMS enforce write privileges; use sudo for normal
system installation.

## Before rebooting into a new kernel

The distribution's DKMS/kernel-header hooks must be installed and functional.
`AUTOINSTALL="yes"` opts the registered source into that mechanism. It does not
repair incompatible driver code, supply missing headers, enroll a signing key,
or prove the storage is attached and mounted.

```sh
# Replace this with the exact kernel release you intend to boot.
next_kernel=YOUR_TARGET_KERNEL_RELEASE
sudo dkms autoinstall -k "$next_kernel"
dkms status -m iomemory-vsl -k "$next_kernel"
modinfo -k "$next_kernel" -F filename iomemory-vsl
modinfo -k "$next_kernel" -F vermagic iomemory-vsl
modinfo -k "$next_kernel" -F version iomemory-vsl
```

Require the intended source version to report `installed` for the target kernel,
and require its vermagic to begin with that exact release. Verify module signing
and key enrollment on Secure Boot systems. Boot-critical storage also requires
checking the distribution's initramfs integration and actual module inclusion.
Do not reboot solely because the build returned success.

There are no direct device attach, format, erase, module unload/load, bootloader,
or reboot commands in the installer. Administrator-configured DKMS hooks
(including `modprobe_on_install` or post-transaction hooks) still apply: inspect
those before changing a live storage driver. A disk-installed module and the
currently loaded module are different things. Activate changes only in a
controlled maintenance window with a known-good boot entry and backup.

## Failure and rollback boundaries

A failed build is propagated and no install command is issued after that
failure. The installer does not remove older DKMS versions, run `remove --all`,
or force replacement. Repeating the same source/kernel registration skips
already installed builds. Different source under the same version fails rather
than replacing registered inputs. Installer instances sharing a DKMS state tree
are serialized; administrators must still avoid racing unrelated manual DKMS
maintenance or a distribution package transaction.

Existing versions and kernel images remain available for operator-selected
rollback. Retaining them is not a guarantee that every DKMS release will select
the desired version automatically: verify autoinstall as above and plan explicit
cleanup only after the new version has been validated. The installer does not
claim a transactionally atomic rollback of a failed DKMS install or arbitrary
administrator hooks. Never remove a known-good kernel/module to make a failing
upgrade look clean.

## Verification and evidence boundaries

```sh
python3 -m unittest discover -s tests -p 'test_dkms.py' -v
```

These offline tests use a fake DKMS backend and temporary source/state/library
directories. They execute the actual installer, Git snapshot operations,
configuration evaluation, and real Makefile metadata-generation targets in a
Git-free copy. They cover repeat installs, two target kernels, failure
propagation, old-install preservation, source collisions, dirty/untracked files,
invalid arguments, missing headers and source symlinks. They do **not** compile
the complete driver, exercise real DKMS version selection, or access hardware.

The `DKMS lifecycle` workflow separately attempts real builds on Ubuntu 24.04
with GA and HWE headers, repeats installation, then runs `dkms autoinstall` for
the second kernel and checks version/vermagic. It uses an ephemeral GitHub-hosted
runner with read-only repository permissions, never a self-hosted storage host.
A workflow definition is not a passing run. Review the actual run before merge.
Hardware load, attach, I/O integrity, Secure Boot, initramfs and reboot validation
remain necessary on representative machines; CI does not perform them.

Reference: the DKMS project's `dkms(8)` documentation, especially `add`, `build`,
`install`, `autoinstall`, `DKMS.CONF`, and `DKMS.CONF VARIABLES`:
https://manpages.debian.org/testing/dkms/dkms.8.en.html
