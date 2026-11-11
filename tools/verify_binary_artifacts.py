#!/usr/bin/env python3
"""Verify the committed opaque inputs; hashes do not authenticate their vendor."""

import argparse
import hashlib
import json
from pathlib import Path
import struct
import sys


ROOT = Path(__file__).resolve().parents[1]
MANIFEST = "binary-artifacts.json"
ARTIFACT_GLOBS = (
    "root/usr/src/iomemory-vsl-*/kfio/*_libkfio.o_shipped",
    "root/usr/lib/fio/*.so",
)


def elf_identity(data):
    """Read the ELF class, byte order, object type and architecture only."""
    if len(data) < 20 or data[:4] != b"\x7fELF":
        raise ValueError("not an ELF object")
    if data[4] not in (1, 2) or data[5] not in (1, 2):
        raise ValueError("unsupported ELF class or byte order")
    byte_order = "<" if data[5] == 1 else ">"
    object_type, machine = struct.unpack(byte_order + "HH", data[16:20])
    return {
        "bits": 32 if data[4] == 1 else 64,
        "byte_order": "little" if data[5] == 1 else "big",
        "type": object_type,
        "machine": machine,
    }


def verify(root, manifest):
    """Return every inventory/content mismatch without modifying any artifact."""
    errors = []
    if manifest.get("schema_version") != 1:
        return ["unsupported binary manifest schema"]
    entries = manifest.get("artifacts")
    if not isinstance(entries, list) or not entries:
        return ["manifest must contain a nonempty artifacts list"]
    expected = set()
    for entry in entries:
        if not isinstance(entry, dict) or not isinstance(entry.get("path"), str):
            errors.append("invalid artifact entry")
            continue
        name = entry["path"]
        relative = Path(name)
        if relative.is_absolute() or ".." in relative.parts or name in expected:
            errors.append(f"invalid or duplicate artifact path: {name}")
            continue
        expected.add(name)
        path = root / relative
        if path.is_symlink() or not path.resolve().is_relative_to(root.resolve()):
            errors.append(f"artifact must be a regular in-tree file: {name}")
            continue
        try:
            data = path.read_bytes()
            identity = elf_identity(data)
        except (OSError, ValueError) as exc:
            errors.append(f"{name}: {exc}")
            continue
        if hashlib.sha256(data).hexdigest() != entry.get("sha256"):
            errors.append(f"SHA-256 mismatch: {name}")
        if len(data) != entry.get("size_bytes"):
            errors.append(f"size mismatch: {name}")
        if identity != entry.get("elf"):
            errors.append(f"ELF identity mismatch: {name}")
    actual = {str(path.relative_to(root))
              for pattern in ARTIFACT_GLOBS for path in root.glob(pattern)}
    for name in sorted(actual - expected):
        errors.append(f"unrecorded binary input: {name}")
    for name in sorted(expected - actual):
        errors.append(f"manifest entry outside the binary inventory: {name}")
    return errors


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=ROOT)
    args = parser.parse_args()
    try:
        manifest = json.loads((args.root / MANIFEST).read_text())
        errors = verify(args.root, manifest)
    except (OSError, ValueError, TypeError, AttributeError) as exc:
        print(f"binary manifest: {exc}", file=sys.stderr)
        return 1
    if errors:
        for error in errors:
            print(error, file=sys.stderr)
        return 1
    print(f"Verified {len(manifest['artifacts'])} opaque binary inputs; "
          "vendor provenance and licensing are outside this content check.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
