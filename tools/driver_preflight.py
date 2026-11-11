#!/usr/bin/env python3
"""Read-only ioMemory artifact inventory; never load, install, flash, or write media.

Exit 0: collection complete and requested metadata checks agree.
Exit 2: collection complete but identity drift or a planned transition is present.
Exit 1: collection failed. No successful receipt is emitted on collection failure.
A zero exit is NOT hardware qualification or proof of the loaded module's bytes.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import platform
import re
import stat
import subprocess
import sys
from typing import Any

FIELDS = ("name", "version", "srcversion", "vermagic", "signer")
PARAMETERS = ("dma32_clamp", "auto_attach", "sure_erase_mode")
TOKEN = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.+\-]{0,127}\Z")
SHA = re.compile(r"[0-9a-f]{40}\Z")
# Preserve bounded hexadecimal metadata; supplied legacy builds use 23 digits.
SRC = re.compile(r"[0-9a-fA-F]{1,64}\Z")
MAX_BYTES = 128 * 1024 * 1024


class PreflightError(ValueError):
    pass


def require(condition: bool, message: str) -> None:
    if not condition:
        raise PreflightError(message)


def text(value: str, label: str, *, empty: bool = False) -> str:
    value = value.strip()
    require(len(value) <= 4096 and (empty or bool(value)) and
            all(32 <= ord(ch) < 127 for ch in value), f"invalid {label}")
    return value


def validate_request(candidate: Path, kernel: str, version: str, revision: str) -> None:
    require(candidate.is_absolute(), "candidate module path must be absolute")
    require(any(candidate.name.endswith(s) for s in (".ko", ".ko.xz", ".ko.gz", ".ko.zst")),
            "candidate must be a .ko or supported compressed module file")
    require(TOKEN.fullmatch(kernel) is not None, "invalid target kernel")
    require(TOKEN.fullmatch(version) is not None, "invalid expected version")
    require(SHA.fullmatch(revision) is not None, "source revision must be a full lowercase Git commit ID")


def file_identity(path: Path) -> dict[str, Any]:
    """Do not hash device nodes, FIFOs, final-component symlinks, or changing files."""
    require(path.is_absolute(), "artifact paths must be absolute")
    fd = os.open(path, os.O_RDONLY | os.O_CLOEXEC | os.O_NOFOLLOW | os.O_NONBLOCK)
    try:
        before = os.fstat(fd)
        require(stat.S_ISREG(before.st_mode), "artifact must be a regular file")
        require(0 < before.st_size <= MAX_BYTES, "artifact is empty or exceeds 128 MiB")
        digest = hashlib.sha256()
        size = 0
        while True:
            chunk = os.read(fd, 1024 * 1024)
            if not chunk:
                break
            size += len(chunk)
            require(size <= MAX_BYTES, "artifact grew beyond 128 MiB")
            digest.update(chunk)
        after = os.fstat(fd)
        current = os.stat(path, follow_symlinks=False)
        keys = ("st_dev", "st_ino", "st_size", "st_mtime_ns", "st_ctime_ns")
        require(size == before.st_size and
                all(getattr(before, k) == getattr(after, k) == getattr(current, k) for k in keys),
                "artifact changed while hashing")
        return {"filename": path.name, "bytes": size, "sha256": digest.hexdigest(),
                "digest_scope": "on-disk file bytes, including compression/signature"}
    finally:
        os.close(fd)


def modinfo(*args: str) -> str:
    # Resolve only from administrator-controlled system directories, not cwd/PATH.
    executable = next((p for p in ("/usr/sbin/modinfo", "/sbin/modinfo", "/usr/bin/modinfo", "/bin/modinfo")
                       if os.path.isfile(p) and os.access(p, os.X_OK)), None)
    require(executable is not None, "system modinfo is unavailable")
    result = subprocess.run([executable, *args], stdin=subprocess.DEVNULL,
                            stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                            timeout=15, check=False,
                            env={"PATH": "/usr/sbin:/usr/bin:/sbin:/bin", "LC_ALL": "C"})
    require(result.returncode == 0, "modinfo failed; check the selected module and installed target kernel")
    require(len(result.stdout) <= 16384, "modinfo output exceeds bound")
    return result.stdout.decode("ascii", errors="strict").strip()


def module_record(path: Path, read_modinfo=modinfo) -> dict[str, Any]:
    before = file_identity(path)
    values = {field: text(read_modinfo("-F", field, str(path)), field, empty=(field == "signer"))
              for field in FIELDS}
    require(values["name"].replace("-", "_") == "iomemory_vsl", "artifact is not iomemory_vsl")
    require(SRC.fullmatch(values["srcversion"]) is not None, "missing or malformed module srcversion")
    require(file_identity(path) == before, "module changed while reading metadata")
    return {**before, **values, "signature_trust_verified": False}


def loaded_record(sysfs: Path = Path("/sys/module/iomemory_vsl")) -> dict[str, Any]:
    # No kernel/device writes and no ioctl tools. This is a small allowlist.
    if not sysfs.exists():
        return {"present": False}
    result: dict[str, Any] = {"present": True}
    for field in ("version", "srcversion", "initstate"):
        with (sysfs / field).open("r", encoding="ascii") as stream:
            result[field] = text(stream.read(4097), f"loaded {field}")
    require(SRC.fullmatch(result["srcversion"]) is not None, "invalid loaded srcversion")
    parameters = {}
    for name in PARAMETERS:
        path = sysfs / "parameters" / name
        if path.exists():
            with path.open("r", encoding="ascii") as stream:
                value = stream.read(128).strip()
            require(re.fullmatch(r"[0-9]+|[YN]", value) is not None, f"invalid parameter {name}")
            parameters[name] = value
        else:
            parameters[name] = None
    result["parameters"] = parameters
    return result


def evaluate(candidate: dict[str, Any], installed: dict[str, Any], loaded: dict[str, Any],
             target: str, running: str, version: str, require_active: bool) -> list[str]:
    drift = []
    if candidate["version"] != version:
        drift.append("candidate_version_does_not_match_expected")
    if candidate["vermagic"].split()[0] != target:
        drift.append("candidate_vermagic_does_not_match_target")
    if not installed.get("present", True):
        drift.append("no_installed_module_reported")
    else:
        for field in ("version", "srcversion", "vermagic"):
            if installed[field] != candidate[field]:
                drift.append(f"installed_{field}_differs_from_candidate")
    if require_active:
        if target != running:
            drift.append("running_kernel_differs_from_target")
        if not loaded["present"]:
            drift.append("module_not_loaded")
        else:
            if loaded["initstate"] != "live":
                drift.append("loaded_module_is_not_live")
            for field in ("version", "srcversion"):
                if loaded[field] != candidate[field]:
                    drift.append(f"loaded_{field}_differs_from_candidate")
    return drift


def collect(candidate: Path, kernel: str, version: str, revision: str, firmware: list[Path],
            require_active: bool = False, *, sysfs: Path = Path("/sys/module/iomemory_vsl"),
            read_modinfo=modinfo, running: str | None = None) -> dict[str, Any]:
    validate_request(candidate, kernel, version, revision)
    require(len(firmware) <= 8, "at most eight firmware files may be inventoried")
    require(len({str(p) for p in firmware}) == len(firmware), "duplicate firmware path")
    active_kernel = text(running or platform.release(), "running kernel")
    candidate_info = module_record(candidate, read_modinfo)
    installed_path = Path(text(read_modinfo("-k", kernel, "-F", "filename", "iomemory-vsl"), "installed filename"))
    require(installed_path.is_absolute(), "modinfo did not return an absolute installed module filename")
    installed_info = module_record(installed_path, read_modinfo)
    loaded = loaded_record(sysfs)
    images = [file_identity(p) for p in firmware]
    # Avoid a receipt made from two different loaded states across module replacement.
    require(loaded_record(sysfs) == loaded, "loaded metadata changed during collection")
    drift = evaluate(candidate_info, installed_info, loaded, kernel, active_kernel, version, require_active)
    loaded_agrees = (loaded["present"] and loaded["initstate"] == "live" and active_kernel == kernel and
                     all(loaded[f] == candidate_info[f] for f in ("version", "srcversion")))
    return {
        "schema_version": 1, "scope": "read-only-artifact-inventory",
        "observed_at_utc": datetime.now(timezone.utc).isoformat(),
        "source_revision_claimed_by_operator": revision,
        "source_to_module_build_binding_verified": False,
        "target_kernel": kernel, "running_kernel": active_kernel,
        "candidate": candidate_info, "installed": installed_info, "loaded": loaded,
        "installed_file_bytes_equal_candidate": installed_info["sha256"] == candidate_info["sha256"],
        "loaded_metadata_agrees_with_candidate": bool(loaded_agrees),
        "require_active_metadata": require_active, "metadata_drift": drift,
        "firmware_files": images, "firmware_file_to_card_binding_verified": False,
        "loaded_module_bytes_verified": False, "hardware_qualified": False,
        "release_qualified": False,
        "limitations": ["Matching metadata does not measure already-loaded code.",
                        "A signer string is not signature trust or enforcement.",
                        "Firmware hashes inventory files; they do not identify active firmware.",
                        "No identity check proves persistence, recovery, or media correctness."],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--candidate-module", type=Path, required=True)
    parser.add_argument("--target-kernel", required=True)
    parser.add_argument("--expected-version", required=True)
    parser.add_argument("--source-revision", required=True)
    parser.add_argument("--firmware", type=Path, action="append", default=[])
    parser.add_argument("--require-active", action="store_true",
                        help="Also fail metadata checks if the requested module/kernel is not active")
    args = parser.parse_args()
    try:
        report = collect(args.candidate_module, args.target_kernel, args.expected_version,
                         args.source_revision, args.firmware, args.require_active)
    except (PreflightError, OSError, UnicodeError, subprocess.SubprocessError) as exc:
        # No raw command output or environment. Review paths/signer metadata before sharing.
        print(f"Preflight collection FAILED: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 1
    print(json.dumps(report, indent=2, sort_keys=True))
    return 2 if report["metadata_drift"] else 0


if __name__ == "__main__":
    sys.exit(main())
