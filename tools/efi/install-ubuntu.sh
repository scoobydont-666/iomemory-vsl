#!/bin/bash
# Retained only to fail safely for old bookmarks and download instructions.
printf '%s\n' \
    'iomemory-vsl: the unattended EFI installer is retired.' \
    'It did not validate boot-device identity, command failures, or recovery.' \
    'Use a reviewed checkout and the maintained DKMS procedure in DKMS.md.' \
    'Boot-from-ioMemory needs separate target-kernel, firmware, signing,' \
    'initramfs and recovery qualification before any reboot.' >&2
exit 1
