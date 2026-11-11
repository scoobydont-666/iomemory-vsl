# EFI boot qualification

The unattended `install-ubuntu.sh` route is retired. The retained command exits
with an error before installing software, loading a module, editing filesystems,
or changing boot configuration.

Use a reviewed source revision and the maintained [DKMS procedure](../../DKMS.md)
for module installation. A successful DKMS build/install does not qualify booting
from the card. Boot support requires evidence for the exact card and firmware,
target kernel, module signature policy, initramfs contents, stable filesystem
identifiers, and a tested recovery path on isolated hardware.

Do not replace UUID-based filesystem references with discovery-order device
paths. Keep an independently bootable recovery environment and the previous
known-working kernel/module. This repository provides no unattended boot-device
migration or firmware configuration procedure.
