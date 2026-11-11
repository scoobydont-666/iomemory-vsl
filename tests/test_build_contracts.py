"""Offline build contracts using the shipped scripts and isolated fake tools.

These tests never load a module, install software, or access a storage device.
The real header builds in CI remain necessary for kernel compatibility.
"""
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "root/usr/src/iomemory-vsl-3.2.16"


def shell_function(text, name):
    matches = list(re.finditer(r"^([A-Za-z_]\w*)\(\)\n\{", text, re.M))
    for index, match in enumerate(matches):
        if match[1] == name:
            end = matches[index + 1].start() if index + 1 < len(matches) else len(text)
            body = text[match.start():end]
            return body[:body.rfind("\n}") + 3]
    raise AssertionError("missing shell function: " + name)


class ObjtoolContracts(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="iomemory-build-test-")
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.kernel = self.root / "kernel"
        tool = self.kernel / "tools/objtool/objtool"
        tool.parent.mkdir(parents=True)
        tool.write_text("#!/usr/bin/env python3\nimport json,os,sys\n"
                        "open(os.environ['ARGV_FILE'],'w').write(json.dumps(sys.argv[1:]))\n"
                        "print(os.environ.get('DIAGNOSTIC',''),end='')\n"
                        "sys.exit(int(os.environ.get('TOOL_RC','0')))\n")
        tool.chmod(0o755)
        release = self.kernel / "include/config/kernel.release"
        release.parent.mkdir(parents=True)
        release.write_text("7.0.0-test\n")
        self.env = dict(os.environ, objtree=str(self.kernel), DEBUG="",
                        ARGV_FILE=str(self.root / "args.json"),
                        FUSION_DRIVER_DIR=str(self.root), FIO_DRIVER_NAME="iomemory-vsl",
                        KFIO_LIB=str(SRC / "kfio/x86_64_latest_libkfio.o_shipped"))

    def run_wrapper(self, diagnostic="", rc=7, obj="main.o", extra=()):
        return subprocess.run(["bash", str(SRC / "objtool_wrapper"), "--werror", "--link",
                               *extra, str(self.root / obj)], cwd=self.root,
                              env=dict(self.env, DIAGNOSTIC=diagnostic, TOOL_RC=str(rc)),
                              text=True, capture_output=True)

    def test_preserves_werror_and_argument_boundaries(self):
        result = self.run_wrapper(rc=0, obj="object with spaces.o", extra=("--prefix=16",))
        self.assertEqual(result.returncode, 0, result.stderr)
        args = json.loads((self.root / "args.json").read_text())
        self.assertIn("--werror", args)
        self.assertEqual(args[-1], str(self.root / "object with spaces.o"))

    def test_known_text_on_first_party_object_fails(self):
        self.assertNotEqual(self.run_wrapper("main.o: unannotated intra-function call\n").returncode, 0)

    def test_mixed_fatal_diagnostic_fails(self):
        output = "iomemory-vsl.o: unannotated intra-function call\n"
        output += "fatal: cannot parse relocation table\n"
        self.assertNotEqual(self.run_wrapper(output, obj="iomemory-vsl.o").returncode, 0)

    def test_unknown_failure_fails(self):
        self.assertEqual(self.run_wrapper("fatal: broken ELF\n", rc=17).returncode, 17)

    def test_only_pinned_linked_core_diagnostic_is_accepted(self):
        obj = str(self.root / "iomemory-vsl.o")
        diagnostic = obj + ": error: objtool: .text+0x123: unannotated intra-function call\n"
        result = self.run_wrapper(diagnostic, obj="iomemory-vsl.o")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual((self.root / ".objtool-link-args").read_bytes(), b"--werror\0--link\0")
        self.env["KFIO_LIB"] = str(self.root / "unknown-core.o")
        (self.root / "unknown-core.o").write_bytes(b"unreviewed")
        self.assertNotEqual(self.run_wrapper(diagnostic, obj="iomemory-vsl.o").returncode, 0)

    def test_known_diagnostic_plus_any_unknown_line_fails(self):
        obj = str(self.root / "iomemory-vsl.o")
        diagnostic = obj + ": error: objtool: .text+0x123: unannotated intra-function call\n"
        for extra in ("fatal: relocation error\n", "unexpected diagnostic\n", "main.o: unannotated intra-function call\n"):
            with self.subTest(extra=extra):
                self.assertNotEqual(self.run_wrapper(diagnostic + extra, obj="iomemory-vsl.o").returncode, 0)


class ArtifactRouteContracts(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="iomemory-route-test-")
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.source = self.root / "source"
        self.source.mkdir()
        for name in ("Makefile", "Kbuild", "Kbuild.objects", "dkms.conf", "check_target_kernel.sh",
                     "kfio_config.sh", "objtool_wrapper", "objtool-perfile.sh"):
            shutil.copy2(SRC / name, self.source / name)
        (self.source / "kfio").mkdir()
        (self.source / "kfio/x86_64_latest_libkfio.o_shipped").symlink_to(SRC / "kfio/x86_64_latest_libkfio.o_shipped")
        config = self.source / "include/fio/port/linux/kfio_config.h"
        config.parent.mkdir(parents=True)
        config.write_text("/* mock API configuration */\n")
        self.kernel = self.root / "kernel"
        release = self.kernel / "include/config/kernel.release"
        release.parent.mkdir(parents=True)
        release.write_text("7.0.0-test\n")
        (self.kernel / "Makefile").write_text(r'''
include $(FUSION_DRIVER_DIR)/Kbuild.objects
.PHONY: modules modules_install clean
modules:
	@for object in $(FIO_PORT_OBJS); do test -f "$(M)/$$object" || printf 'compiler output\n' > "$(M)/$$object"; done
	@touch "$(M)/$(FIO_DRIVER_NAME).o"
	@objtree="$(CURDIR)" "$(objtool)" --werror --link --uaccess "$(M)/$(FIO_DRIVER_NAME).o"
	@touch "$(M)/$(FIO_DRIVER_NAME).ko"
modules_install:
	@test -f "$(M)/$(FIO_DRIVER_NAME).ko"
	@printf 'installed\n' >> "$(ROUTE_LOG)"
clean:
	@rm -f "$(M)"/*.o "$(M)"/*.ko
''')
        tool = self.kernel / "tools/objtool/objtool"
        tool.parent.mkdir(parents=True)
        tool.write_text('''#!/usr/bin/env python3
import json,os,pathlib,sys
with open(os.environ['ROUTE_LOG'],'a') as stream:
    stream.write(json.dumps(sys.argv[1:])+'\\n')
path=pathlib.Path(sys.argv[-1])
if '--link' in sys.argv and not os.environ.get('WHOLE_VALIDATION'):
    print(str(path)+': error: objtool: .text+0x123: unannotated intra-function call')
    sys.exit(1)
if '--link' not in sys.argv:
    if os.environ.get('FAIL_OBJECT') == path.name: sys.exit(23)
    data=path.read_text()
    if 'transformed' in data: sys.exit(24)
    path.write_text(data+'transformed\\n')
''')
        tool.chmod(0o755)
        self.log = self.root / "calls.log"
        self.env = dict(os.environ, ROUTE_LOG=str(self.log))
        self.env.pop("FAIL_OBJECT", None)

    def build(self, target, **environment):
        return subprocess.run(["make", "-s", target, "KERNEL_BUILD="+str(self.kernel),
                               "KERNELVER=7.0.0-test", "MODULE_VERSION=contract-test", "NCPUS=1"],
                              cwd=self.source, env=dict(self.env, **environment), text=True, capture_output=True)

    def test_every_advertised_route_requires_first_party_validation(self):
        for target in ("all", "gpl", "modules", "modules_install", "objtool_perfile"):
            with self.subTest(target=target):
                result = self.build(target, FAIL_OBJECT="main.o")
                self.assertNotEqual(result.returncode, 0, result.stdout + result.stderr)
                self.assertFalse((self.source / "iomemory-vsl.ko").exists())
                self.assertNotIn("installed", self.log.read_text())

    def test_all_linked_first_party_objects_are_checked_once_with_kernel_flags(self):
        for target in ("modules", "gpl", "modules_install"):
            result = self.build(target)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        calls = [json.loads(line) for line in self.log.read_text().splitlines() if line.startswith("[")]
        checked = [args for args in calls if "--link" not in args]
        self.assertIn("main.o", [args[-1] for args in checked])
        self.assertIn("module_param.o", [args[-1] for args in checked])
        self.assertEqual(len(checked), len(list((self.source / ".objtool-first-party").glob("*.o"))))
        for args in checked:
            self.assertIn("--werror", args)
            self.assertIn("--uaccess", args)
        self.assertTrue((self.source / "iomemory-vsl.ko").exists())

    def test_invalid_metadata_fails_without_emitting_a_module(self):
        result = subprocess.run(["make", "-s", "add_module_version", "MODULE_VERSION=invalid/version"],
                                cwd=self.source, text=True, capture_output=True)
        self.assertNotEqual(result.returncode, 0)
        self.assertFalse((self.source / "license.c").exists())

    def test_git_free_source_package_generates_declared_version_before_link(self):
        result = subprocess.run(["make", "-s", "add_module_version"], cwd=self.source,
                                text=True, capture_output=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        version = re.search(r"^PACKAGE_VERSION=(.*)$", (self.source / "dkms.conf").read_text(), re.M)[1]
        self.assertIn('MODULE_VERSION("'+version+'");', (self.source / "license.c").read_text())
        # A Kbuild timestamp change must not replace generated version metadata.
        (self.source / "Kbuild").touch()
        result = subprocess.run(["make", "-sf", "Kbuild", "license.c", "src=.",
                                 "FUSION_DRIVER_DIR=.", "FIO_DRIVER_NAME=iomemory-vsl", "KFIO_LIB=kfio/core.o"],
                                cwd=self.source, text=True, capture_output=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn('MODULE_VERSION("'+version+'");', (self.source / "license.c").read_text())

    def test_successful_whole_module_validation_needs_no_second_transformation(self):
        result = self.build("modules", WHOLE_VALIDATION="1")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        calls = [json.loads(line) for line in self.log.read_text().splitlines() if line.startswith("[")]
        self.assertTrue(calls)
        self.assertTrue(all("--link" in args for args in calls))
        self.assertTrue((self.source / "iomemory-vsl.ko").exists())

    def test_changed_kernel_validation_context_requires_clean_rebuild(self):
        self.assertEqual(self.build("modules").returncode, 0)
        tool = self.kernel / "tools/objtool/objtool"
        tool.write_text(tool.read_text() + "# changed tool\n")
        result = self.build("modules")
        self.assertNotEqual(result.returncode, 0)
        self.assertFalse((self.source / "iomemory-vsl.ko").exists())


class ProbeContracts(unittest.TestCase):
    def test_verbose_build_failure_has_identical_capability_result(self):
        text = (SRC / "kfio_config.sh").read_text()
        funcs = "\n".join(shell_function(text, name) for name in ("fio_create_makefile", "kfioc_test"))
        with tempfile.TemporaryDirectory(prefix="iomemory-probe-test-") as directory:
            root = Path(directory)
            fake = root / "make"
            fake.write_text("#!/bin/sh\necho failed-build\nexit 17\n")
            fake.chmod(0o755)
            for verbose in (0, 1):
                with self.subTest(verbose=verbose):
                    code = funcs + '\nset_kfioc_status() { printf "STATUS %s %s\\n" "$3" "$2"; }\n'
                    code += "kfioc_test 'int test;' PROBE 1\n"
                    env = dict(os.environ, PATH=str(root) + os.pathsep + os.environ["PATH"],
                               CONFIGDIR=str(root / str(verbose)), KERNELDIR=str(root),
                               FUSION_DEBUG="0", VERBOSE=str(verbose))
                    result = subprocess.run(["bash", "-eu", "-c", code], env=env,
                                            text=True, capture_output=True)
                    self.assertEqual(result.returncode, 0, result.stderr)
                    self.assertIn("STATUS exit 17", result.stdout)
                    self.assertIn("STATUS result 0", result.stdout)

    def test_add_disk_probe_distinguishes_return_types(self):
        text = shell_function((SRC / "kfio_config.sh").read_text(), "KFIOC_X_VOID_ADD_DISK")
        code = text + '\nkfioc_test() { printf "%s" "$1"; }\nKFIOC_X_VOID_ADD_DISK PROBE\n'
        source = subprocess.check_output(["bash", "-c", code], text=True)
        with tempfile.TemporaryDirectory(prefix="iomemory-api-test-") as directory:
            root = Path(directory)
            (root / "linux").mkdir()
            path = root / "probe.c"
            path.write_text(source)
            for result_type, succeeds in (("void", True), ("int", False)):
                with self.subTest(result_type=result_type):
                    (root / "linux/blkdev.h").write_text(
                        "#include <stddef.h>\nstruct gendisk;\n" + result_type + " add_disk(struct gendisk *);\n")
                    result = subprocess.run(["cc", "-Werror", "-fsyntax-only", "-I", str(root), str(path)],
                                            text=True, capture_output=True)
                    self.assertEqual(result.returncode == 0, succeeds, result.stderr)


class RetiredInstallContracts(unittest.TestCase):
    def test_efi_helper_fails_before_invoking_system_commands(self):
        with tempfile.TemporaryDirectory(prefix="iomemory-efi-test-") as directory:
            root = Path(directory)
            marker = root / "called"
            fake = root / "sudo"
            fake.write_text("#!/bin/sh\ntouch '" + str(marker) + "'\nexit 19\n")
            fake.chmod(0o755)
            result = subprocess.run(["bash", str(ROOT / "tools/efi/install-ubuntu.sh")],
                                    env=dict(os.environ, PATH=str(root)+os.pathsep+os.environ["PATH"]),
                                    text=True, capture_output=True, timeout=10)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("retired", result.stderr.lower())
            self.assertFalse(marker.exists())

    def test_legacy_dkms_refuses_before_metadata_or_system_changes(self):
        with tempfile.TemporaryDirectory(prefix="iomemory-legacy-test-") as directory:
            root = Path(directory)
            (root / "Makefile").write_text("# fixture\n")
            result = subprocess.run(["bash", str(SRC / "module_operations.sh"), "-d", "-n", "iomemory-vsl", "-v", "1"],
                                    cwd=root, text=True, capture_output=True, timeout=10)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("retired", result.stderr.lower())
            self.assertFalse((root / "license.c").exists())


if __name__ == "__main__":
    unittest.main()
