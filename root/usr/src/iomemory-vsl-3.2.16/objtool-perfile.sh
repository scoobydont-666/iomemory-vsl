#!/bin/bash
# Kernel 7 links before objtool. An opaque core can prevent the linked pass
# from reaching transformations required by first-party static-branch sites.
set -euo pipefail
tool=${1:?objtool path required}
major=${2:?target kernel major required}
shift 2
[[ $major =~ ^[0-9]+$ ]] || { echo 'Invalid target kernel major' >&2; exit 1; }
if (( major < 7 )); then
    exit 0 # Kbuild already runs objtool per first-party compilation.
fi
# Successful whole-module validation already performed its transformations.
# Apply the corrective pass only when the wrapper recorded the core limitation.
[[ -f .objtool-link-needs-perfile ]] || exit 0
[[ -x $tool && -s .objtool-link-args ]] || {
    echo 'Missing objtool or recorded kernel objtool flags; clean and rebuild' >&2
    exit 1
}
flags=()
while IFS= read -r -d '' arg; do
    [[ $arg == --link ]] || flags+=("$arg")
done < .objtool-link-args
[[ ${#flags[@]} -gt 0 && $# -gt 0 ]] || exit 1
# A changed tool/configuration requires rebuilding compiler output, not applying
# prefix/jump-label transformations twice to already transformed objects.
context=$( { sha256sum "$tool" .objtool-link-args; printf '%s\n' "$major"; } | sha256sum)
mkdir -p .objtool-first-party
if [[ -f .objtool-first-party/context ]]; then
    [[ $(cat .objtool-first-party/context) == "$context" ]] || {
        echo 'objtool context changed: run make clean before rebuilding' >&2
        exit 1
    }
fi
printf '%s\n' "$context" > .objtool-first-party/context
for object in "$@"; do
    [[ $object != */* && $object == *.o && -f $object ]] || {
        printf 'Missing or invalid first-party object: %s\n' "$object" >&2
        exit 1
    }
    checksum=$(sha256sum "$object")
    if [[ -f .objtool-first-party/$object && $(cat ".objtool-first-party/$object") == "$checksum" ]]; then
        continue
    fi
    "$tool" "${flags[@]}" "$object"
    sha256sum "$object" > ".objtool-first-party/$object"
    touch .objtool-relink-required
done
