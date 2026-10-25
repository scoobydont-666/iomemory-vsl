#!/bin/bash
# Register an immutable Git snapshot; DKMS, not this script, builds each kernel.
set -euo pipefail
umask 022

fail() { printf 'iomemory-vsl DKMS: %s\n' "$*" >&2; exit 1; }
[[ $# -le 2 ]] || fail 'usage: bash dkms-install.sh [kernel-release [kernel-build-directory]]'
name=iomemory-vsl
kernel=${1:-$(uname -r)}
kernel_build=${2:-/lib/modules/$kernel/build}
[[ $kernel =~ ^[[:alnum:]][[:alnum:]_.+-]*$ ]] || fail 'invalid kernel release'
[[ -f $kernel_build/Makefile ]] || fail "install headers for $kernel; missing $kernel_build/Makefile"
for tool in git dkms tar flock mktemp install diff sed grep find readlink realpath; do
    command -v "$tool" >/dev/null || fail "missing prerequisite: $tool"
done

# Installation requires a committed checkout. Rebuilds of the staged source do not.
source_dir=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd -P)
repo=$(git -C "$source_dir" rev-parse --show-toplevel) || fail 'install from a Git checkout'
revision=$(git -C "$repo" rev-parse HEAD)
prefix=$(git -C "$source_dir" rev-parse --show-prefix)
git -C "$repo" diff --quiet "$revision" -- || fail 'commit tracked changes before registering a snapshot'
# Timestamp first gives snapshot packages a chronological order, unlike bare hashes.
# It also sorts after the historical 3.x and kernel-prefixed package versions.
version=${DKMS_VERSION:-$(git -C "$repo" show -s --format=%ct "$revision").$(git -C "$repo" rev-parse --short=12 "$revision")}
[[ $version =~ ^[[:alnum:]][[:alnum:]_.-]{0,63}$ ]] || fail 'invalid DKMS_VERSION (use at most 64 letters, digits, dots, underscores or hyphens)'
git -C "$repo" cat-file -e "$revision:root/usr/lib/fio/libvsl.so" || fail 'committed libvsl.so is missing'

source_tree=${DKMS_SOURCE_TREE:-/usr/src}
state_tree=${DKMS_STATE_TREE:-/var/lib/dkms}
lib_dir=${DKMS_LIB_DIR:-/usr/lib/fio}
[[ $source_tree = /* && $state_tree = /* && $lib_dir = /* ]] || fail 'installation directories must be absolute'
install -d -m 0755 "$source_tree" "$state_tree" || fail 'cannot create DKMS directories; use sudo make dkms for system installation'
# Serialize this installer's registration work; DKMS owns its own build lifecycle.
exec 9>"$state_tree/.iomemory-vsl-install.lock"
flock -x 9
stage=$(mktemp -d "$source_tree/.iomemory-vsl-stage.XXXXXXXX")
trap 'rm -rf -- "$stage"' EXIT
mkdir "$stage/source"
git -C "$repo" archive "$revision:${prefix%/}" | tar -x --no-same-owner -C "$stage/source"
sed -i "s/^PACKAGE_VERSION=.*/PACKAGE_VERSION=$version/" "$stage/source/dkms.conf"
printf '%s\n' "$revision" > "$stage/source/.dkms-source-revision"
git -C "$repo" show "$revision:root/usr/lib/fio/libvsl.so" > "$stage/libvsl.so"
chmod 0755 "$stage/source"
# Archives exclude untracked build output, .git, and local administrative files.
# Keep relative in-tree links (such as the selected kfio blob), but reject
# references outside the archived source tree.
while IFS= read -r -d '' link; do
    [[ $(readlink -- "$link") != /* ]] || fail "absolute source symlink: $link"
    resolved=$(realpath -e -- "$link") || fail "broken source symlink: $link"
    [[ $resolved == "$stage/source/"* ]] || fail "external source symlink: $link"
done < <(find "$stage/source" -type l -print0)
destination=$source_tree/$name-$version
if [[ -e $destination || -L $destination ]]; then
    [[ -d $destination && ! -L $destination ]] || fail "refusing non-directory or symlink $destination"
    diff -qr "$stage/source" "$destination" >/dev/null || fail "source/version collision at $destination; use a new DKMS_VERSION, do not overwrite registered source"
else
    mv -- "$stage/source" "$destination"
fi

common=(-m "$name" -v "$version" --sourcetree "$source_tree" --dkmstree "$state_tree")
status=$(dkms status "${common[@]}")
if [[ -z $status ]]; then
    dkms add "${common[@]}"
fi
# Never remove older versions or force an overwrite. No direct device commands.
# Administrator-configured DKMS hooks remain under DKMS control.
# A failed build leaves existing installed kernels available for rollback.
status=$(dkms status "${common[@]}" -k "$kernel")
if ! grep -Eq ': installed$' <<< "$status"; then
    dkms build "${common[@]}" -k "$kernel" --kernelsourcedir "$kernel_build"
    dkms install "${common[@]}" -k "$kernel"
    status=$(dkms status "${common[@]}" -k "$kernel")
fi
grep -Eq ': installed$' <<< "$status" || fail "DKMS did not report installed for $name/$version on $kernel: $status"
install -d -m 0755 "$lib_dir"
install -m 0755 "$stage/libvsl.so" "$lib_dir/libvsl.so"
printf 'Registered source: %s\nInstalled for kernel: %s\nSource commit: %s\n' "$name/$version" "$kernel" "$revision"
printf 'Existing versions were retained. Verify DKMS autoinstall for the next kernel before rebooting.\n'
