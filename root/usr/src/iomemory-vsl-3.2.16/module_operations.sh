#!/bin/bash
# Old callers must fail before deleting DKMS versions or mutating binaries.
printf '%s\n' \
    'iomemory-vsl: module_operations.sh is retired.' \
    'Use make dkms for committed-source registration and installation.' \
    'Use make modules MODULE_VERSION=<source-version> for manual builds.' \
    'Version metadata is generated before linking; linked/signed modules and' \
    'the proprietary core are never rewritten by the supported build path.' >&2
exit 1
