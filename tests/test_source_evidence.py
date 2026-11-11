"""Hardware/network-free regressions using real, disposable Git object stores."""
import copy
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest

TOOL = Path(__file__).resolve().parents[1] / "tools/verify_source_evidence.py"
spec = importlib.util.spec_from_file_location("source_evidence", TOOL)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


class SourceEvidenceTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.repo = Path(self.temp.name)
        self.git("init", "-q")
        self.git("config", "user.name", "Test")
        self.git("config", "user.email", "test@example.invalid")
        self.git("config", "commit.gpgsign", "false")
        self.put("root/proc.c", "old-proc\n")
        self.put("root/pci.c", "old-dma\n")
        self.put("Makefile", "all:\n\ttrue\n")
        parent = self.commit("parent")
        self.put("root/Makefile", "historical objtool\n")
        historical = self.commit("historical")
        historical_tree = self.git("rev-parse", "HEAD^{tree}").strip()
        self.put("root/pci.c", "corrected-dma\n")
        baseline = self.commit("baseline")
        self.put("docs/local-compare/README.md", "original observations\n")
        self.put("docs/local-compare/log.txt", "historical log\n")
        self.put("docs/local-compare/patches/fix.patch", "inert patch\n")
        self.put("load-fio-driver.sh", "echo 'historical only'\n")
        (self.repo / "load-fio-driver.sh").chmod(0o755)
        original = self.commit("original snapshot")
        self.put("docs/local-compare/README.md", "published historical branch\n")
        latest = self.commit("latest snapshot")
        self.git("checkout", "-q", "--detach", baseline)
        self.put("docs/local-compare/log.txt", "historical log\n")
        self.put("docs/local-compare/patches/fix.patch", "inert patch\n")
        self.put("docs/local-compare/load-fio-driver.sh.txt", "echo 'historical only'\n")
        hashes = {}
        for path in ("root/proc.c", "root/pci.c"):
            hashes[path] = {column: hashlib.sha256(self.git_bytes("show", f"{revision}:{path}")).hexdigest()
                            for column, revision in (("loaded_reconstruction", historical),
                                                     ("baseline", baseline), ("snapshot", original))}
        self.record = {"snapshot": original, "baseline": baseline,
                       "reconstructed_claimed_source_tree": historical_tree,
                       "reconstruction_parent": parent, "hashes": hashes}
        self.put("docs/local-compare/reconstruction.json", json.dumps(self.record))
        previous = self.commit("previous candidate")
        self.index = {
            "schema_version": 1,
            "commits": {"baseline": baseline, "original_snapshot": original,
                        "latest_snapshot": latest, "published_historical": historical,
                        "previous_candidate": previous},
            "historical_tree": historical_tree, "historical_parent": parent,
            "snapshot_unchanged_paths": ["root", "Makefile"],
            "snapshot_update_paths": ["docs/local-compare/README.md"],
            "historical_equal_paths": ["root/proc.c"],
            "preserved_evidence": [
                {"source": "docs/local-compare/log.txt", "destination": "docs/local-compare/log.txt", "mode": "100644"},
                {"source": "docs/local-compare/patches", "destination": "docs/local-compare/patches", "mode": "040000"},
                {"source": "load-fio-driver.sh", "destination": "docs/local-compare/load-fio-driver.sh.txt", "mode": "100644"}],
            "reconstruction_record": "docs/local-compare/reconstruction.json", "scope": "git-source-only"}
        self.put(module.DEFAULT_INDEX, json.dumps(self.index))
        self.candidate = self.commit("candidate with evidence index")

    def git_bytes(self, *args):
        env = {k: v for k, v in os.environ.items() if not k.startswith("GIT_")}
        env.update(GIT_CONFIG_NOSYSTEM="1")
        return subprocess.run(["git", "-C", str(self.repo), *args], env=env,
                              check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE).stdout

    def git(self, *args):
        return self.git_bytes(*args).decode()

    def put(self, path, content):
        target = self.repo / path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content)

    def commit(self, message):
        self.git("add", "-A")
        self.git("commit", "-qm", message)
        return self.git("rev-parse", "HEAD").strip()

    def verify(self, index=None, candidate=None):
        return module.verify(self.repo, index or self.index, candidate or self.candidate)

    def test_source_agreement_does_not_qualify_runtime(self):
        result = self.verify()
        self.assertTrue(result["source_evidence_verified"])
        self.assertEqual(result["historical_hash_checks"], 6)
        self.assertEqual(result["candidate_commit"], self.candidate)
        for field in ("loaded_module_bytes_verified", "firmware_binding_verified",
                      "license_release_verified", "hardware_qualified", "release_qualified"):
            self.assertIs(result[field], False)

    def test_wrong_historical_tree(self):
        self.index["historical_tree"] = self.git("rev-parse", self.candidate + "^{tree}").strip()
        with self.assertRaisesRegex(module.EvidenceError, "historical tree"):
            self.verify()

    def test_wrong_historical_parent(self):
        self.index["historical_parent"] = self.index["commits"]["baseline"]
        with self.assertRaisesRegex(module.EvidenceError, "historical parent"):
            self.verify()

    def test_missing_commit_is_failure(self):
        self.index["commits"]["latest_snapshot"] = "0" * 40
        with self.assertRaisesRegex(module.EvidenceError, "Git read failed"):
            self.verify()

    def test_commit_must_not_be_a_tree(self):
        self.index["commits"]["latest_snapshot"] = self.index["historical_tree"]
        with self.assertRaisesRegex(module.EvidenceError, "Not a commit"):
            self.verify()

    def test_branch_names_abbreviations_and_options_are_rejected(self):
        for value in ("main", "9328703", "--help", "f" * 39, "A" * 40):
            with self.subTest(value=value):
                index = copy.deepcopy(self.index)
                index["commits"]["baseline"] = value
                with self.assertRaises(module.EvidenceError):
                    self.verify(index)

    def test_snapshot_runtime_change_is_rejected(self):
        self.git("checkout", "-q", "--detach", self.index["commits"]["latest_snapshot"])
        self.put("root/pci.c", "new unreviewed implementation\n")
        self.index["commits"]["latest_snapshot"] = self.commit("unexpected runtime change")
        with self.assertRaisesRegex(module.EvidenceError, "Snapshot update"):
            self.verify()

    def test_snapshot_baseline_mismatch_is_rejected(self):
        self.git("checkout", "-q", "--detach", self.index["commits"]["original_snapshot"])
        self.put("Makefile", "different build\n")
        self.index["commits"]["original_snapshot"] = self.commit("altered snapshot")
        self.put("docs/local-compare/README.md", "new historical branch\n")
        self.index["commits"]["latest_snapshot"] = self.commit("notes")
        with self.assertRaisesRegex(module.EvidenceError, "Snapshot changes Makefile"):
            self.verify()

    def test_historical_equal_path_is_checked(self):
        self.index["historical_equal_paths"] = ["root/pci.c"]
        with self.assertRaisesRegex(module.EvidenceError, "Historical source differs"):
            self.verify()

    def test_missing_path_is_failure(self):
        self.index["historical_equal_paths"] = ["root/missing.c"]
        with self.assertRaisesRegex(module.EvidenceError, "Missing or ambiguous path"):
            self.verify()

    def test_archive_content_cannot_be_rewritten(self):
        self.put("docs/local-compare/log.txt", "invented success\n")
        with self.assertRaisesRegex(module.EvidenceError, "Archived evidence changed"):
            self.verify(candidate=self.commit("changed log"))

    def test_archived_loader_cannot_be_executable(self):
        (self.repo / "docs/local-compare/load-fio-driver.sh.txt").chmod(0o755)
        with self.assertRaisesRegex(module.EvidenceError, "Archived evidence changed or executable"):
            self.verify(candidate=self.commit("executable loader"))

    def test_archive_symlink_is_rejected(self):
        path = self.repo / "docs/local-compare/log.txt"
        path.unlink()
        path.symlink_to("/etc/passwd")
        with self.assertRaisesRegex(module.EvidenceError, "Symlink/submodule"):
            self.verify(candidate=self.commit("symlink"))

    def test_reconstruction_receipt_is_append_only(self):
        self.put(self.index["reconstruction_record"], json.dumps({**self.record, "scope": "rewritten"}))
        with self.assertRaisesRegex(module.EvidenceError, "receipt was rewritten"):
            self.verify(candidate=self.commit("rewritten receipt"))

    def test_hash_values_are_verified_against_actual_git_blobs(self):
        self.record["hashes"]["root/pci.c"]["baseline"] = "0" * 64
        self.put(self.index["reconstruction_record"], json.dumps(self.record))
        self.index["commits"]["previous_candidate"] = self.commit("invalid historical receipt")
        self.put("docs/new.md", "candidate\n")
        with self.assertRaisesRegex(module.EvidenceError, "Hash mismatch"):
            self.verify(candidate=self.commit("new candidate"))

    def test_duplicate_json_keys_are_rejected(self):
        with self.assertRaisesRegex(module.EvidenceError, "Duplicate JSON key"):
            module.load_json(b'{"schema_version":1,"schema_version":2}')

    def test_unsafe_paths_are_rejected(self):
        for path in ("/etc/passwd", "../outside", "root/../outside", "root//file", "--help", "root/a\n"):
            with self.subTest(path=path):
                with self.assertRaises(module.EvidenceError):
                    module.repo_path(path)

    def test_unknown_fields_and_missing_roles_are_rejected(self):
        for index in (dict(self.index, release_qualified=True), dict(self.index, commits={})):
            with self.assertRaises(module.EvidenceError):
                self.verify(index)

    def test_git_replace_cannot_change_recorded_evidence(self):
        self.git("replace", self.index["commits"]["published_historical"], self.candidate)
        self.assertTrue(self.verify()["source_evidence_verified"])

    def test_candidate_source_changes_are_reported_not_hidden(self):
        self.put("root/proc.c", "candidate refactor\n")
        result = self.verify(candidate=self.commit("new driver source"))
        self.assertFalse(result["runtime_source_tree_unchanged_since_previous_candidate"])
        self.assertFalse(result["release_qualified"])

    def test_list_commits_has_only_full_unique_ids(self):
        result = subprocess.run(["python3", str(TOOL), "--repo", str(self.repo), "--list-commits"],
                                capture_output=True, text=True, check=True)
        self.assertEqual(result.stdout.splitlines(), sorted(set(self.index["commits"].values())))

    def test_cli_verifies_committed_index_not_dirty_worktree(self):
        self.put(module.DEFAULT_INDEX, "not JSON")
        result = subprocess.run(["python3", str(TOOL), "--repo", str(self.repo)],
                                capture_output=True, text=True, check=True)
        self.assertEqual(json.loads(result.stdout)["candidate_commit"], self.candidate)

    def test_cli_missing_candidate_has_no_success_receipt(self):
        result = subprocess.run(["python3", str(TOOL), "--repo", str(self.repo),
                                 "--candidate", "0" * 40], capture_output=True, text=True)
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(result.stdout, "")
        self.assertIn("FAILED", result.stderr)


if __name__ == "__main__":
    unittest.main()
