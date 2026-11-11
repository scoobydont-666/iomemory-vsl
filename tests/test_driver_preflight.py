"""Inventory tests use regular fixture files and fake modinfo; no real devices."""
import copy
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

TOOL = Path(__file__).resolve().parents[1] / "tools/driver_preflight.py"
spec = importlib.util.spec_from_file_location("driver_preflight", TOOL)
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)


class DriverPreflightTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.candidate = self.root / "candidate.ko"
        self.installed = self.root / "installed.ko.zst"
        self.candidate.write_bytes(b"fixture candidate module")
        self.installed.write_bytes(b"fixture compressed and signed installed module")
        self.sysfs = self.root / "sys/module/iomemory_vsl"
        self.sysfs.mkdir(parents=True)
        (self.sysfs / "parameters").mkdir()
        self.kernel = "7.0.0-28-generic"
        self.version = "candidate.0123456789ab"
        self.revision = "a" * 40
        self.metadata = {"name": "iomemory_vsl", "version": self.version,
                         "srcversion": "A" * 24, "vermagic": self.kernel + " SMP modversions",
                         "signer": "Local test signer"}
        self.installed_metadata = dict(self.metadata)
        self.calls = []
        self.write_loaded()

    def write_loaded(self, **values):
        fields = {"version": self.version, "srcversion": "A" * 24, "initstate": "live", **values}
        for key, value in fields.items():
            (self.sysfs / key).write_text(value + "\n")

    def read_modinfo(self, *args):
        self.calls.append(args)
        if args == ("-k", self.kernel, "-F", "filename", "iomemory-vsl"):
            return str(self.installed)
        self.assertEqual(args[0], "-F")
        self.assertIn(args[1], m.FIELDS)
        self.assertIn(args[2], (str(self.candidate), str(self.installed)))
        data = self.metadata if args[2] == str(self.candidate) else self.installed_metadata
        return data[args[1]]

    def collect(self, *, active=False, firmware=None, running=None):
        return m.collect(self.candidate, self.kernel, self.version, self.revision, firmware or [], active,
                         sysfs=self.sysfs, read_modinfo=self.read_modinfo, running=running or self.kernel)

    def test_matching_metadata_does_not_qualify_storage_or_loaded_bytes(self):
        report = self.collect(active=True)
        self.assertEqual(report["metadata_drift"], [])
        self.assertTrue(report["loaded_metadata_agrees_with_candidate"])
        for field in ("loaded_module_bytes_verified", "hardware_qualified", "release_qualified",
                      "source_to_module_build_binding_verified", "firmware_file_to_card_binding_verified"):
            self.assertFalse(report[field])

    def test_three_distinct_module_identities_are_reported(self):
        self.installed_metadata["version"] = "installed.old"
        self.installed_metadata["srcversion"] = "B" * 24
        self.write_loaded(version="loaded.older", srcversion="C" * 24)
        report = self.collect(active=True)
        self.assertIn("installed_version_differs_from_candidate", report["metadata_drift"])
        self.assertIn("installed_srcversion_differs_from_candidate", report["metadata_drift"])
        self.assertIn("loaded_version_differs_from_candidate", report["metadata_drift"])
        self.assertIn("loaded_srcversion_differs_from_candidate", report["metadata_drift"])

    def test_prepare_mode_does_not_claim_that_candidate_is_loaded(self):
        self.write_loaded(version="old")
        report = self.collect()
        self.assertEqual(report["metadata_drift"], [])
        self.assertFalse(report["loaded_metadata_agrees_with_candidate"])
        self.assertFalse(report["require_active_metadata"])

    def test_active_mode_requires_running_kernel(self):
        report = self.collect(active=True, running="6.8.0-149-generic")
        self.assertIn("running_kernel_differs_from_target", report["metadata_drift"])

    def test_candidate_expected_version_and_target_are_checked(self):
        self.metadata["version"] = "unexpected"
        self.metadata["vermagic"] = "6.8.0-149-generic SMP"
        drift = self.collect()["metadata_drift"]
        self.assertIn("candidate_version_does_not_match_expected", drift)
        self.assertIn("candidate_vermagic_does_not_match_target", drift)

    def test_installed_vermagic_is_compared_in_full(self):
        self.installed_metadata["vermagic"] = self.kernel + " different-features"
        self.assertIn("installed_vermagic_differs_from_candidate", self.collect()["metadata_drift"])

    def test_signer_is_not_proof_of_trust(self):
        self.assertFalse(self.collect()["candidate"]["signature_trust_verified"])
        self.metadata["signer"] = ""
        self.assertEqual(self.collect()["candidate"]["signer"], "")

    def test_compressed_file_hash_is_not_raw_module_hash(self):
        report = self.collect()
        self.assertFalse(report["installed_file_bytes_equal_candidate"])
        self.assertEqual(report["metadata_drift"], [])
        self.assertIn("compression", report["installed"]["digest_scope"])

    def test_firmware_inventory_does_not_claim_active_image(self):
        image = self.root / "local.fff"
        image.write_bytes(b"fixture firmware")
        report = self.collect(firmware=[image])
        self.assertEqual(report["firmware_files"][0]["bytes"], 16)
        self.assertFalse(report["firmware_file_to_card_binding_verified"])

    def test_duplicate_or_excessive_images_fail(self):
        image = self.root / "local.fff"
        with self.assertRaisesRegex(m.PreflightError, "duplicate"):
            self.collect(firmware=[image, image])
        with self.assertRaisesRegex(m.PreflightError, "at most eight"):
            self.collect(firmware=[self.root / str(i) for i in range(9)])

    def test_no_path_or_option_injection(self):
        for kernel in ("--help", "../escape", "a\nb", "x;touch pwned", ""):
            with self.subTest(kernel=kernel), self.assertRaises(m.PreflightError):
                m.validate_request(self.candidate, kernel, self.version, self.revision)
        for rev in ("main", "abcd", "A" * 40, "--help"):
            with self.subTest(revision=rev), self.assertRaises(m.PreflightError):
                m.validate_request(self.candidate, self.kernel, self.version, rev)

    def test_candidate_requires_absolute_module_path(self):
        for path in (Path("relative.ko"), self.root / "not-a-module"):
            with self.subTest(path=path), self.assertRaises(m.PreflightError):
                m.validate_request(path, self.kernel, self.version, self.revision)

    def test_wrong_module_name_is_rejected(self):
        self.metadata["name"] = "another_driver"
        with self.assertRaisesRegex(m.PreflightError, "not iomemory"):
            self.collect()

    def test_missing_or_malformed_srcversion_is_rejected(self):
        for value in ("", "G", "Z" * 24, "A" * 65):
            self.metadata["srcversion"] = value
            with self.subTest(value=value), self.assertRaises(m.PreflightError):
                self.collect()

    def test_supplied_legacy_srcversion_is_preserved_not_assumed_24_digits(self):
        value = "A707FCA26416451F13ADC03"
        self.metadata["srcversion"] = value
        self.installed_metadata["srcversion"] = value
        self.write_loaded(srcversion=value)
        report = self.collect(active=True)
        self.assertEqual(report["metadata_drift"], [])
        self.assertEqual(report["loaded"]["srcversion"], value)

    def test_control_characters_are_rejected(self):
        self.metadata["signer"] = "key\x1b[31m"
        with self.assertRaisesRegex(m.PreflightError, "invalid signer"):
            self.collect()

    def test_symlink_fifo_and_device_nodes_are_not_hashed(self):
        link = self.root / "link.ko"
        link.symlink_to(self.candidate)
        fifo = self.root / "pipe.ko"
        os.mkfifo(fifo)
        for path in (link, fifo, Path("/dev/null")):
            with self.subTest(path=path), self.assertRaises((m.PreflightError, OSError)):
                m.file_identity(path)

    def test_empty_or_large_files_fail(self):
        path = self.root / "empty.ko"
        path.touch()
        with self.assertRaises(m.PreflightError):
            m.file_identity(path)
        with path.open("wb") as stream:
            stream.truncate(m.MAX_BYTES + 1)
        with self.assertRaises(m.PreflightError):
            m.file_identity(path)

    def test_changed_file_during_metadata_read_fails(self):
        def changing(*args):
            result = self.read_modinfo(*args)
            if args[:2] == ("-F", "signer"):
                self.candidate.write_bytes(b"modified")
            return result
        with self.assertRaisesRegex(m.PreflightError, "module changed"):
            m.module_record(self.candidate, changing)

    def test_loaded_module_transition_during_collection_fails(self):
        before = m.loaded_record(self.sysfs)
        after = {**before, "srcversion": "B" * 24}
        with mock.patch.object(m, "loaded_record", side_effect=[before, after]):
            with self.assertRaisesRegex(m.PreflightError, "loaded metadata changed"):
                self.collect()

    def test_absent_loaded_module_is_not_a_match(self):
        with mock.patch.object(m, "loaded_record", return_value={"present": False}):
            self.assertFalse(self.collect()["loaded_metadata_agrees_with_candidate"])
            self.assertIn("module_not_loaded", self.collect(active=True)["metadata_drift"])

    def test_non_live_module_is_not_an_active_match(self):
        self.write_loaded(initstate="coming")
        report = self.collect(active=True)
        self.assertIn("loaded_module_is_not_live", report["metadata_drift"])

    def test_only_allowlisted_parameters_are_read(self):
        parameters = self.sysfs / "parameters"
        (parameters / "dma32_clamp").write_text("0\n")
        (parameters / "do_not_read_secret").write_text("secret\n")
        params = self.collect()["loaded"]["parameters"]
        self.assertEqual(params["dma32_clamp"], "0")
        self.assertEqual(set(params), set(m.PARAMETERS))
        self.assertIsNone(params["sure_erase_mode"])

    def test_cli_exit_status_separates_drift_and_collection_failure(self):
        args = [str(TOOL), "--candidate-module", str(self.candidate), "--target-kernel", self.kernel,
                "--expected-version", self.version, "--source-revision", self.revision]
        for drift, expected in (([], 0), (["drift"], 2)):
            with mock.patch.object(sys, "argv", args), mock.patch.object(m, "collect", return_value={"metadata_drift": drift}), mock.patch("builtins.print"):
                self.assertEqual(m.main(), expected)
        with mock.patch.object(sys, "argv", args), mock.patch.object(m, "collect", side_effect=OSError("unavailable")), mock.patch("builtins.print") as output:
            self.assertEqual(m.main(), 1)
            self.assertEqual(output.call_count, 1)
            self.assertIs(output.call_args.kwargs["file"], sys.stderr)

    def test_cli_help_and_rejection_need_no_system_commands(self):
        result = subprocess.run([sys.executable, str(TOOL), "--help"], capture_output=True)
        self.assertEqual(result.returncode, 0)
        result = subprocess.run([sys.executable, str(TOOL), "--candidate-module", "relative.ko",
                                 "--target-kernel", self.kernel, "--expected-version", self.version,
                                 "--source-revision", self.revision], capture_output=True)
        self.assertEqual(result.returncode, 1)
        self.assertEqual(result.stdout, b"")


if __name__ == "__main__":
    unittest.main()
