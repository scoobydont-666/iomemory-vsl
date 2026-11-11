#!/usr/bin/env bash
set -euo pipefail
# Load iomemory-vsl driver with 32-bit DMA patch for dual-EPYC
# Usage: sudo ./load-fio-driver.sh [format|attach]
DRIVER=/opt/remixvsl-iomemory/root/usr/src/iomemory-vsl-3.2.16/iomemory-vsl.ko

echo 'Loading iomemory-vsl driver (32-bit DMA patched)...'
insmod $DRIVER auto_attach=0

sleep 3
echo 'Driver loaded. Card status:'
fio-status -a 2>&1 | head -10

if [ "${1:-}" = 'format' ]; then
    echo 'Formatting at 2500GB...'
    fio-format /dev/fct0 -y -f -s 2500G
    echo 'Format complete.'
fi

if [ "${1:-}" = 'attach' ] || [ "${1:-}" = 'format' ]; then
    echo 'Attaching...'
    fio-attach /dev/fct0
    echo 'Attach complete.'
    fio-status -a
fi
