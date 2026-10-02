#!/usr/bin/env bash
# Stage committed sources and register/build/install without unloading the driver.
set -euo pipefail
umask 022
name=iomemory-vsl
subdir=root/usr/src/iomemory-vsl-3.2.16
source_tree=/usr/src
dkms_tree=/var/lib/dkms
install_tree=/lib/modules
lib_dir=/usr/lib/fio
kernels=()
all_kernels=0
usage() {
    echo "Usage: $0 [-k KERNEL ... | --all-kernels] [--sourcetree DIR] [--dkmstree DIR] [--installtree DIR] [--libdir DIR]"
}
die() { echo "iomemory-vsl DKMS: $*" >&2; exit 1; }
while (($#)); do
    case "$1" in
        -k|--kernel) (($# >= 2)) || die 'missing kernel'; kernels+=("$2"); shift 2 ;;
        --all-kernels) all_kernels=1; shift ;;
        --sourcetree|--dkmstree|--installtree|--libdir)
            (($# >= 2)) || die "missing argument to $1"
            case "$1" in
                --sourcetree) source_tree=$2 ;; --dkmstree) dkms_tree=$2 ;;
                --installtree) install_tree=$2 ;; --libdir) lib_dir=$2 ;;
            esac
            shift 2 ;;
        -h|--help) usage; exit 0 ;;
        *) usage >&2; die "unknown argument: $1" ;;
    esac
done
((EUID == 0)) || die 'run with sudo; no automatic privilege escalation is performed'
for cmd in git dkms tar mktemp flock diff install sed; do
    command -v "$cmd" >/dev/null || die "required command missing: $cmd"
done
for path in "$source_tree" "$dkms_tree" "$install_tree" "$lib_dir"; do
    [[ $path == /* && $path != / ]] || die "expected an absolute non-root directory: $path"
done
repo=$(git -C "$(dirname "${BASH_SOURCE[0]}")" rev-parse --show-toplevel)
commit=$(git -C "$repo" rev-parse --verify HEAD)
git -C "$repo" diff --quiet HEAD -- || die 'tracked changes exist; commit or use a clean worktree before staging'
# Archive only HEAD, never untracked scripts or build products in a live checkout.
# A timestamp before the hash makes source revisions sort by commit time, not hash.
epoch=$(git -C "$repo" show -s --format=%ct HEAD)
version="3.2.16.${epoch}.g${commit:0:12}"
if ((all_kernels)); then
    ((${#kernels[@]} == 0)) || die '--all-kernels cannot be combined with -k'
    for path in "$install_tree"/*; do
        [[ -d $path ]] && kernels+=("${path##*/}")
    done
else
    ((${#kernels[@]})) || kernels=("$(uname -r)")
fi
((${#kernels[@]})) || die 'no target kernels found'
# Check every target before any DKMS registration or replacement on disk.
for kernel in "${kernels[@]}"; do
    [[ $kernel =~ ^[A-Za-z0-9][A-Za-z0-9._+-]*$ ]] || die "invalid kernel release: $kernel"
    [[ -f $install_tree/$kernel/build/Makefile ]] || die "missing headers: $install_tree/$kernel/build/Makefile"
done
[[ -f $repo/root/usr/lib/fio/libvsl.so ]] || die 'missing userspace libvsl.so in checkout'
install -d -m 0755 "$source_tree" "$dkms_tree"
args=(--sourcetree "$source_tree" --dkmstree "$dkms_tree" --installtree "$install_tree")
# Serialize this installer's writers; external DKMS/package operations still need
# the normal package-manager maintenance window.
exec 9>"$dkms_tree/.iomemory-vsl-install.lock"
flock -x 9
# A previous installer used kernel-prefixed package versions. Registering a new
# lower-sorting version beside them can make autoinstall choose stale sources.
existing=$(dkms status -m "$name" "${args[@]}")
while IFS= read -r entry; do
    [[ -z $entry ]] && continue
    case "$entry" in
        "$name/$version:"*|"$name/$version,"*|"$name, $version:"*|"$name, $version,"*) ;;
        *) die "another registration exists: $entry; review migration before changing autoinstall selection" ;;
    esac
done <<<"$existing"
stage=$(mktemp -d "$source_tree/.iomemory-vsl-stage.XXXXXXXX")
trap 'rm -rf -- "$stage"' EXIT
git -C "$repo" archive HEAD "$subdir" | tar -x -C "$stage" --strip-components=4 --no-same-owner
printf '%s\n' "$commit" > "$stage/.source-revision"
sed -i "s/^PACKAGE_VERSION=.*/PACKAGE_VERSION=$version/" "$stage/dkms.conf"
chmod -R go-w "$stage"
chmod 0755 "$stage"
dest="$source_tree/$name-$version"
[[ ! -L $dest ]] || die "refusing symlink source destination: $dest"
if [[ -e $dest ]]; then
    # Reusing a version must never silently select different/stale source bytes.
    diff -qr "$stage" "$dest" >/dev/null || die "source collision at $dest; leaving existing registration untouched"
else
    mv -T "$stage" "$dest"
fi
status=$(dkms status -m "$name" -v "$version" "${args[@]}")
if [[ -z $status ]]; then
    dkms add -m "$name" -v "$version" "${args[@]}"
fi
for kernel in "${kernels[@]}"; do
    status=$(dkms status -m "$name" -v "$version" -k "$kernel" "${args[@]}")
    if ! grep -Eq ': installed$' <<<"$status"; then
        if ! grep -Eq ': built$' <<<"$status"; then
            dkms build -m "$name" -v "$version" -k "$kernel" \
                --kernelsourcedir "$install_tree/$kernel/build" "${args[@]}"
        fi
        # No --force, no remove --all, and no runtime module/card operations.
        dkms install -m "$name" -v "$version" -k "$kernel" "${args[@]}"
    fi
    status=$(dkms status -m "$name" -v "$version" -k "$kernel" "${args[@]}")
    grep -Eq ': installed$' <<<"$status" || die "DKMS did not confirm installation for $kernel: $status"
    printf '%s\n' "$status"
done
install -D -m 0755 "$repo/root/usr/lib/fio/libvsl.so" "$lib_dir/libvsl.so"
echo "Source commit: $commit; DKMS package: $name/$version"
echo 'No running module was unloaded or reloaded. Verify module selection, signing, and boot in a maintenance window.'
