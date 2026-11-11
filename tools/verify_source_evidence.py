#!/usr/bin/env python3
"""Verify pinned Git evidence, not a running driver or release qualification.

Network-free: populate the required commits before running. Never check out,
execute, apply, or source supplied historical files. All Git operations are reads.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys
from typing import Any

DEFAULT_INDEX = "docs/local-compare/evidence-index.json"
OID = re.compile(r"[0-9a-f]{40}\Z")
ROLES = {"baseline", "original_snapshot", "latest_snapshot", "published_historical", "previous_candidate"}


class EvidenceError(ValueError):
    """Missing, malformed, or inconsistent evidence (never a skipped pass)."""


def require(condition: bool, message: str) -> None:
    if not condition:
        raise EvidenceError(message)


def unique_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        require(key not in result, f"Duplicate JSON key: {key}")
        result[key] = value
    return result


def load_json(data: bytes) -> dict[str, Any]:
    try:
        result = json.loads(data, object_pairs_hook=unique_object)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise EvidenceError(f"Invalid JSON: {exc}") from exc
    require(isinstance(result, dict), "JSON root must be an object")
    return result


def oid(value: Any) -> str:
    require(isinstance(value, str) and OID.fullmatch(value) is not None,
            "Expected a full lowercase 40-character Git object ID")
    return value


def repo_path(value: Any) -> str:
    require(isinstance(value, str) and bool(value) and
            re.fullmatch(r"[A-Za-z0-9_.\-/]+", value) is not None and
            not value.startswith(("/", "-")) and
            all(part not in {"", ".", ".."} for part in value.split("/")),
            f"Unsafe repository path: {value!r}")
    return value


def validate_index(index: dict[str, Any]) -> dict[str, Any]:
    expected = {"schema_version", "commits", "historical_tree", "historical_parent",
                "snapshot_unchanged_paths", "snapshot_update_paths", "historical_equal_paths",
                "preserved_evidence", "reconstruction_record", "scope"}
    require(set(index) == expected, "Unexpected or missing evidence-index fields")
    require(type(index["schema_version"]) is int and index["schema_version"] == 1,
            "Unsupported evidence-index schema")
    require(isinstance(index["commits"], dict) and set(index["commits"]) == ROLES,
            "All five named commit roles are required")
    for revision in index["commits"].values():
        oid(revision)
    oid(index["historical_tree"])
    oid(index["historical_parent"])
    for field in ("snapshot_unchanged_paths", "snapshot_update_paths", "historical_equal_paths"):
        paths = index[field]
        require(isinstance(paths, list) and 0 < len(paths) <= 64 and
                all(isinstance(path, str) for path in paths), f"Invalid {field}")
        require(len(paths) == len(set(paths)), f"Duplicate paths in {field}")
        for path in paths:
            repo_path(path)
    records = index["preserved_evidence"]
    require(isinstance(records, list) and 0 < len(records) <= 64, "Missing preserved evidence")
    destinations = set()
    for record in records:
        require(isinstance(record, dict) and set(record) == {"source", "destination", "mode"},
                "Invalid preserved-evidence entry")
        repo_path(record["source"])
        destination = repo_path(record["destination"])
        require(destination not in destinations, "Duplicate preserved-evidence destination")
        destinations.add(destination)
        require(record["mode"] in {"100644", "040000"}, "Evidence must be inert text or a tree")
    repo_path(index["reconstruction_record"])
    require(index["scope"] == "git-source-only", "This verifier cannot qualify runtime or licensing")
    return index


class Git:
    def __init__(self, root: Path):
        self.root = root
        # Do not let replace refs or caller repository/index overrides alter receipts.
        self.env = {k: v for k, v in os.environ.items() if not k.startswith("GIT_")}
        self.env.update(GIT_NO_REPLACE_OBJECTS="1", GIT_OPTIONAL_LOCKS="0",
                        GIT_TERMINAL_PROMPT="0", GIT_NO_LAZY_FETCH="1",
                        GIT_ALLOW_PROTOCOL="", GIT_LITERAL_PATHSPECS="1", LC_ALL="C")

    def run(self, *args: str) -> bytes:
        try:
            result = subprocess.run(["git", "--no-pager", "-C", str(self.root), *args],
                                    env=self.env, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                    timeout=30, check=False)
        except (OSError, subprocess.TimeoutExpired) as exc:
            raise EvidenceError(f"Git read failed: {exc}") from exc
        require(result.returncode == 0,
                f"Git read failed ({' '.join(args)}): {result.stderr.decode(errors='replace').strip()}")
        return result.stdout

    def commit(self, revision: str) -> tuple[str, list[str]]:
        revision = oid(revision)
        require(self.run("cat-file", "-t", revision).strip() == b"commit",
                f"Not a commit: {revision}")
        header = self.run("cat-file", "-p", revision).split(b"\n\n", 1)[0].splitlines()
        trees = [line[5:].decode() for line in header if line.startswith(b"tree ")]
        require(len(trees) == 1, f"Invalid commit tree: {revision}")
        return oid(trees[0]), [oid(line[7:].decode()) for line in header if line.startswith(b"parent ")]

    def entry(self, revision: str, path: str) -> tuple[str, str, str]:
        raw = self.run("ls-tree", "-z", oid(revision), "--", repo_path(path)).split(b"\0")
        entries = [item for item in raw if item]
        require(len(entries) == 1, f"Missing or ambiguous path {revision}:{path}")
        metadata, name = entries[0].split(b"\t", 1)
        require(name.decode() == path, f"Path mismatch: {path}")
        mode, kind, digest = metadata.decode().split()
        require(mode in {"100644", "100755", "040000"} and kind in {"blob", "tree"},
                f"Symlink/submodule is not source evidence: {path}")
        return mode, kind, oid(digest)

    def blob(self, revision: str, path: str) -> bytes:
        _, kind, digest = self.entry(revision, path)
        require(kind == "blob", f"Expected file: {path}")
        size = int(self.run("cat-file", "-s", digest))
        require(size <= 16 * 1024 * 1024, f"Evidence blob exceeds size bound: {path}")
        return self.run("cat-file", "blob", digest)


def verify(root: Path, index: dict[str, Any], candidate: str) -> dict[str, Any]:
    validate_index(index)
    git = Git(root)
    candidate = oid(candidate)
    revisions = index["commits"]
    commits = {role: git.commit(revision) for role, revision in revisions.items()}
    candidate_tree, _ = git.commit(candidate)
    require(commits["published_historical"][0] == index["historical_tree"],
            "Published historical tree differs from the reconstructed tree")
    require(commits["published_historical"][1] == [index["historical_parent"]],
            "Published historical parent differs from the reconstruction parent")
    changed = git.run("diff", "--no-ext-diff", "--no-renames", "--name-only", "-z",
                      revisions["original_snapshot"], revisions["latest_snapshot"], "--")
    require(set(filter(None, changed.decode().split("\0"))) == set(index["snapshot_update_paths"]),
            "Snapshot update includes unexpected or missing paths")
    for path in index["snapshot_unchanged_paths"]:
        baseline = git.entry(revisions["baseline"], path)
        for role in ("original_snapshot", "latest_snapshot"):
            require(git.entry(revisions[role], path) == baseline, f"Snapshot changes {path}")
    for path in index["historical_equal_paths"]:
        require(git.entry(revisions["published_historical"], path) ==
                git.entry(revisions["baseline"], path), f"Historical source differs at {path}")
    for record in index["preserved_evidence"]:
        source = git.entry(revisions["original_snapshot"], record["source"])
        target = git.entry(candidate, record["destination"])
        require(source[1:] == target[1:] and target[0] == record["mode"],
                f"Archived evidence changed or executable: {record['destination']}")
        if target[1] == "tree":
            entries = git.run("ls-tree", "-rz", candidate, "--", record["destination"])
            require(all(item.startswith(b"100644 blob ") for item in entries.split(b"\0") if item),
                    f"Archived evidence tree contains executable/link entries: {record['destination']}")
    record_data = git.blob(candidate, index["reconstruction_record"])
    require(record_data == git.blob(revisions["previous_candidate"], index["reconstruction_record"]),
            "Original reconstruction receipt was rewritten; append evidence instead")
    record = load_json(record_data)
    require(record.get("snapshot") == revisions["original_snapshot"] and
            record.get("baseline") == revisions["baseline"] and
            record.get("reconstructed_claimed_source_tree") == index["historical_tree"] and
            record.get("reconstruction_parent") == index["historical_parent"],
            "Reconstruction receipt disagrees with the evidence index")
    hashes = record.get("hashes")
    require(isinstance(hashes, dict) and 0 < len(hashes) <= 64, "Missing reconstruction hashes")
    checked = 0
    for path, values in hashes.items():
        repo_path(path)
        require(isinstance(values, dict), f"Invalid hash record: {path}")
        for column, role in (("loaded_reconstruction", "published_historical"),
                             ("baseline", "baseline"), ("snapshot", "original_snapshot")):
            expected = values.get(column)
            require(isinstance(expected, str) and re.fullmatch(r"[0-9a-f]{64}", expected) is not None,
                    f"Invalid {column} hash for {path}")
            require(hashlib.sha256(git.blob(revisions[role], path)).hexdigest() == expected,
                    f"Hash mismatch in {column}: {path}")
            checked += 1
    return {
        "schema_version": 1, "scope": "git-source-only", "source_evidence_verified": True,
        "candidate_commit": candidate, "candidate_tree": candidate_tree,
        "commits": revisions, "historical_tree": index["historical_tree"],
        "historical_hash_checks": checked,
        "preserved_evidence_items": len(index["preserved_evidence"]),
        "runtime_source_tree_unchanged_since_previous_candidate":
            git.entry(candidate, "root") == git.entry(revisions["previous_candidate"], "root"),
        "loaded_module_bytes_verified": False, "firmware_binding_verified": False,
        "license_release_verified": False, "hardware_qualified": False,
        "release_qualified": False,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--index", default=DEFAULT_INDEX, help="Path relative to --repo")
    parser.add_argument("--candidate", help="Full commit ID; defaults to HEAD")
    parser.add_argument("--list-commits", action="store_true", help="Validate index and list pinned fetch inputs")
    args = parser.parse_args()
    try:
        index_path = repo_path(args.index)
        if args.list_commits:
            path = args.repo / index_path
            require(not path.is_symlink(), "Index must not be a symlink")
            index = validate_index(load_json(path.read_bytes()))
            print("\n".join(sorted(set(index["commits"].values()))))
        else:
            git = Git(args.repo)
            candidate = args.candidate or git.run("rev-parse", "--verify", "HEAD").decode().strip()
            index = validate_index(load_json(git.blob(oid(candidate), index_path)))
            print(json.dumps(verify(args.repo, index, candidate), indent=2, sort_keys=True))
        return 0
    except (EvidenceError, OSError, ValueError, KeyError, TypeError) as exc:
        print(f"Source evidence verification FAILED: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
