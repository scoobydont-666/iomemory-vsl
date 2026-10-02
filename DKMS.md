# DKMS installation and kernel-upgrade verification

This procedure manages build/install artifacts, not running storage. It never
unloads a module, detaches a card, formats media, changes GRUB, or reboots.
A successful build is **not** evidence that a module will load or that I/O is safe.
Validate new driver revisions and kernel combinations in a maintenance window.

## Install from a reviewed commit

Install the distribution's DKMS package, compiler/build dependencies and headers
for **every** target kernel. Review the repository's existing build prerequisites.
Use a clean checkout at the exact reviewed commit, not an uncommitted live tree.

```sh
git status --short
git rev-parse HEAD
# Current running kernel:
sudo make dkms
# All kernel directories under /lib/modules (fails if any lacks headers):
sudo make dkms DKMS_ARGS='--all-kernels'
# A particular installed kernel, including one not currently running:
sudo make dkms DKMS_ARGS='-k <target-kernel-release>'
```

`make dkms` archives committed driver sources, writes the full commit to
`.source-revision`, and creates a kernel-independent package version of the form
`3.2.16.<commit-epoch>.g<12-character-commit>`. The generated `dkms.conf` contains
that same version. Sources remain under `/usr/src` after the checkout is removed;
a future rebuild does not need Git metadata or network access. The module's
`modinfo -F version` identifies this package; vermagic identifies the target kernel.

The existing `libvsl.so` installation under `/usr/lib/fio` is retained. Utility
packages and service configuration are separate; see the main README.

The installer:

- checks all requested headers before registration or module installation;
- excludes untracked recovery scripts and untracked build products;
- rejects tracked working-tree changes and differing bytes under an existing
  source-version directory rather than silently reusing a stale snapshot;
- handles DKMS 2-style and 3-style status text, skips completed work on repeat
  invocation, and propagates status/build/install errors;
- refuses competing source versions because DKMS autoinstall version selection
  must not silently choose an older, kernel-prefixed package;
- does not run `dkms remove --all`, force replacement, or change running modules.

`--sourcetree`, `--dkmstree`, `--installtree`, and `--libdir` accept alternate
absolute paths for disposable lifecycle tests. They are not a chroot or a safety
sandbox for arbitrary real DKMS execution. Use an isolated VM/container for tests.
Run installation outside concurrent package-manager/DKMS operations; the advisory
lock serializes this installer only.

## Existing installations and migration

Preserve known-good modules and their hashes before changing installed artifacts.
A previous DKMS source version must be reviewed and deliberately migrated; this
installer does not remove it on your behalf. Build a candidate separately before
retiring any known-good registration. A future commit timestamp generally sorts
later, but rebased/backdated commits still need deliberate version selection.

DKMS may reject replacing a manually installed module whose old, kernel-prefixed
`modinfo` version sorts later than the new driver package version. Do not make
`--force` the default. Stop, record both modules, verify the candidate, and decide
whether a force-install is appropriate in the reviewed migration procedure.
Legacy `module_operations.sh -d` is not the supported installer entry point;
use `make dkms` so the new lifecycle checks are applied.

## Verify before booting another kernel

For each retained/next kernel:

```sh
dkms status -m iomemory-vsl
sudo dkms autoinstall -k <target-kernel-release>
modinfo -k <target-kernel-release> -F filename iomemory-vsl
modinfo -k <target-kernel-release> -F vermagic iomemory-vsl
modinfo -k <target-kernel-release> -F version iomemory-vsl
modinfo -k <target-kernel-release> -F signer iomemory-vsl
```

Require the exact source package to be installed for each target, and verify that
module resolution selects that artifact rather than a stale manual copy. Inspect
DKMS logs after any error. Missing headers, API changes, compiler incompatibility,
module-signing trust, and boot-loader/initramfs state are not solved by registration.
Keep a known-good boot entry. Do not disable Secure Boot as a shortcut; use the
distribution's signing/key-enrollment procedure when required.

After an authorized boot, verify the actually loaded module, device attachment,
and the backing device of every expected mount. A `nofail` mount can leave a plain
directory on the root filesystem; directory existence alone is not health.
Use filesystem-level checks and workloads that cannot accidentally target a raw
card. Never use formatting or secure erase as an installation test.

## Development tests and current validation boundary

In a disposable root-capable container with Git, Bash, make and Python 3:

```sh
bash -n scripts/install-dkms.sh
python3 -m unittest discover -s tests -p 'test_dkms_lifecycle.py' -v
```

The suite has 12 hardware-free tests. Ten exercise a **stubbed** DKMS executable;
two check configuration expansion and Git-free Makefile version generation.
They cover installation/repeat invocation, both status formats, source collisions,
missing headers, dirty trees, failure propagation, competing versions and symlinks.
They do **not** compile a real kernel module, test a real DKMS installation,
prove kernel-7 objtool correctness, exercise module signing, or test physical I/O.
Those remain required integration/host acceptance checks before production use.

## References

- [DKMS configuration and command contract](https://github.com/dkms-project/dkms/blob/main/dkms.8.in)
- [DKMS source installation and module signing](https://github.com/dkms-project/dkms/blob/main/README.md)
