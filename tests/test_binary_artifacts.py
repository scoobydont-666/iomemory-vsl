"""Content/inventory negative controls for the opaque binary manifest."""

import hashlib
import importlib.util
import json
from pathlib import Path
import struct
import subprocess
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "tools/verify_binary_artifacts.py"
SPEC = importlib.util.spec_from_file_location("binary_verifier", SCRIPT)
VERIFIER = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(VERIFIER)


class BinaryManifestTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="iomemory-binary-test-")
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.name = "root/usr/src/iomemory-vsl-3.2.16/kfio/x86_64_latest_libkfio.o_shipped"
        self.path = self.root / self.name
        self.path.parent.mkdir(parents=True)
        self.data = b"\x7fELF\x02\x01\x01" + bytes(9) + struct.pack("<HH", 1, 62) + bytes(44)
        self.path.write_bytes(self.data)
        self.manifest = {
            "schema_version": 1,
            "artifacts": [{
                "path": self.name,
                "sha256": hashlib.sha256(self.data).hexdigest(),
                "size_bytes": len(self.data),
                "elf": {"bits": 64, "byte_order": "little", "type": 1, "machine": 62},
            }],
        }

    def test_committed_inventory(self):
        result = subprocess.run([sys.executable, str(SCRIPT)], capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_valid_fixture(self):
        self.assertEqual(VERIFIER.verify(self.root, self.manifest), [])

    def test_changed_payload(self):
        self.path.write_bytes(self.data[:-1] + b"X")
        self.assertTrue(any("SHA-256 mismatch" in e for e in VERIFIER.verify(self.root, self.manifest)))

    def test_wrong_elf_architecture(self):
        self.manifest["artifacts"][0]["elf"]["machine"] = 183
        self.assertTrue(any("ELF identity mismatch" in e for e in VERIFIER.verify(self.root, self.manifest)))

    def test_missing_or_extra_binary(self):
        self.path.unlink()
        self.assertTrue(VERIFIER.verify(self.root, self.manifest))
        self.path.write_bytes(self.data)
        self.path.with_name("x86_64_unknown_libkfio.o_shipped").write_bytes(self.data)
        self.assertTrue(any("unrecorded" in e for e in VERIFIER.verify(self.root, self.manifest)))

    def test_symlink_is_rejected(self):
        target = self.root / "alternate"
        target.write_bytes(self.data)
        self.path.unlink()
        self.path.symlink_to(target)
        self.assertTrue(any("regular in-tree" in e for e in VERIFIER.verify(self.root, self.manifest)))

    def test_invalid_manifest_exits_nonzero(self):
        (self.root / VERIFIER.MANIFEST).write_text(json.dumps({"schema_version": 99}))
        result = subprocess.run([sys.executable, str(SCRIPT), "--root", str(self.root)],
                                capture_output=True, text=True)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("unsupported", result.stderr)


if __name__ == "__main__":
    unittest.main()
