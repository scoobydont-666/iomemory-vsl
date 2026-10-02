"""Hardware-free lifecycle regressions. DKMS is a stub, NOT a kernel build test."""
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
SUBDIR = Path('root/usr/src/iomemory-vsl-3.2.16')
DKMS_STUB = r'''#!/usr/bin/env python3
import json, os, pathlib, sys
args = sys.argv[1:]
root = pathlib.Path(os.environ['TEST_STATE'])
with (root/'calls').open('a') as f: f.write(json.dumps(args)+'\n')
assert '--force' not in args and 'remove' not in args
state_file = root/'state.json'
state = json.loads(state_file.read_text()) if state_file.exists() else {}
def value(flag, default=None):
    return args[args.index(flag)+1] if flag in args else default
name, version, kernel = value('-m'), value('-v'), value('-k')
action = args[0]
if action == 'status':
    if os.environ.get('FAIL_STATUS'): sys.exit(17)
    for ver, entries in state.items():
        if version and ver != version: continue
        prefix = name + (', ' if os.environ.get('DKMS2') else '/') + ver
        if not entries: print(prefix+': added')
        for k, result in entries.items():
            if kernel and k != kernel: continue
            print(prefix+', '+k+', x86_64: '+result)
elif action == 'add':
    assert version not in state
    source = pathlib.Path(value('--sourcetree')) / (name+'-'+version)
    assert ('PACKAGE_VERSION='+version) in (source/'dkms.conf').read_text()
    assert (source/'.source-revision').is_file()
    state[version] = {}
elif action == 'build':
    if os.environ.get('FAIL_BUILD'): sys.exit(23)
    state[version][kernel] = 'built'
elif action == 'install':
    if os.environ.get('FAIL_INSTALL'): sys.exit(24)
    state[version][kernel] = 'installed'
else: raise AssertionError(args)
state_file.write_text(json.dumps(state))
'''

@unittest.skipUnless(os.geteuid() == 0, 'installer requires root; use a disposable container')
class LifecycleTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.repo = self.root/'repo'
        self.repo.mkdir()
        for relative in ['scripts/install-dkms.sh', str(SUBDIR/'dkms.conf')]:
            dest = self.repo/relative
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(ROOT/relative, dest)
        lib = self.repo/'root/usr/lib/fio/libvsl.so'
        lib.parent.mkdir(parents=True)
        lib.write_text('fixture, not a real library\n')
        subprocess.run(['git', 'init', '-q', str(self.repo)], check=True)
        self.git('add', '.')
        self.git('-c', 'user.name=Fixture', '-c', 'user.email=fixture@example.invalid',
                 'commit', '-qm', 'fixture')
        self.bin = self.root/'bin'
        self.bin.mkdir()
        (self.bin/'dkms').write_text(DKMS_STUB)
        (self.bin/'dkms').chmod(0o755)
        self.env = dict(os.environ, PATH=str(self.bin)+':'+os.environ['PATH'],
                        TEST_STATE=str(self.root))
        self.modules = self.root/'modules'
        for kernel in ['6.12-test', '7.0-test']:
            directory = self.modules/kernel/'build'
            directory.mkdir(parents=True)
            (directory/'Makefile').touch()
        self.command = ['bash', str(self.repo/'scripts/install-dkms.sh'),
                        '--all-kernels', '--sourcetree', str(self.root/'src'),
                        '--dkmstree', str(self.root/'dkms'),
                        '--installtree', str(self.modules),
                        '--libdir', str(self.root/'lib')]

    def git(self, *args):
        return subprocess.run(['git', '-C', str(self.repo), *args], check=True,
                              capture_output=True, text=True).stdout.strip()

    def run_install(self, success=True, **env):
        result = subprocess.run(self.command, env=dict(self.env, **env),
                                capture_output=True, text=True)
        if success: self.assertEqual(result.returncode, 0, result.stderr+result.stdout)
        else: self.assertNotEqual(result.returncode, 0)
        return result

    def calls(self):
        path = self.root/'calls'
        return [json.loads(line) for line in path.read_text().splitlines()] if path.exists() else []

    def test_first_install_and_idempotent_repeat(self):
        (self.repo/SUBDIR/'dangerous-untracked.sh').write_text('not to be copied')
        self.run_install()
        self.run_install()
        actions = [c[0] for c in self.calls()]
        self.assertEqual(actions.count('add'), 1)
        self.assertEqual(actions.count('build'), 2)
        self.assertEqual(actions.count('install'), 2)
        staged = next((self.root/'src').glob('iomemory-vsl-*'))
        self.assertFalse((staged/'dangerous-untracked.sh').exists())
        self.assertEqual((staged/'.source-revision').read_text().strip(), self.git('rev-parse', 'HEAD'))
        for c in self.calls():
            if c[0] in ('build', 'install'): self.assertIn('-k', c)

    def test_dkms2_status_format(self):
        self.run_install(DKMS2='1')
        self.run_install(DKMS2='1')
        self.assertEqual(sum(c[0] == 'add' for c in self.calls()), 1)

    def test_missing_headers_preflight(self):
        (self.modules/'7.0-test/build/Makefile').unlink()
        self.assertIn('missing headers', self.run_install(False).stderr)
        self.assertEqual(self.calls(), [])

    def test_dirty_checkout_rejected(self):
        with (self.repo/SUBDIR/'dkms.conf').open('a') as f: f.write('\n# dirty\n')
        self.assertIn('tracked changes', self.run_install(False).stderr)
        self.assertEqual(self.calls(), [])

    def test_source_collision_not_overwritten(self):
        self.run_install()
        staged = next((self.root/'src').glob('iomemory-vsl-*'))
        (staged/'dkms.conf').write_text('corrupt\n')
        self.assertIn('source collision', self.run_install(False).stderr)
        self.assertEqual((staged/'dkms.conf').read_text(), 'corrupt\n')

    def test_build_failure_stops_before_install(self):
        self.assertEqual(self.run_install(False, FAIL_BUILD='1').returncode, 23)
        self.assertNotIn('install', [c[0] for c in self.calls()])

    def test_install_failure_propagates(self):
        self.assertEqual(self.run_install(False, FAIL_INSTALL='1').returncode, 24)

    def test_status_failure_propagates(self):
        self.assertEqual(self.run_install(False, FAIL_STATUS='1').returncode, 17)
        self.assertNotIn('add', [c[0] for c in self.calls()])

    def test_competing_version_is_preserved_and_rejected(self):
        (self.root/'state.json').write_text(json.dumps({'7.0.0-old': {'6.12-test': 'installed'}}))
        self.assertIn('another registration exists', self.run_install(False).stderr)
        self.assertEqual(json.loads((self.root/'state.json').read_text()),
                         {'7.0.0-old': {'6.12-test': 'installed'}})

    def test_symlink_destination_rejected(self):
        self.run_install()
        staged = next((self.root/'src').glob('iomemory-vsl-*'))
        elsewhere = self.root/'elsewhere'
        staged.rename(elsewhere)
        staged.symlink_to(elsewhere, target_is_directory=True)
        self.assertIn('symlink', self.run_install(False).stderr)


class BuildContractTests(unittest.TestCase):
    def test_config_targets_gpl_and_requested_kernel(self):
        command = ['bash', '-c', 'kernelver=7.0-target; kernel_source_dir=/test/headers; '
                   'source "$1"; printf "%s\\n" "${MAKE[0]}" "$CLEAN" "$AUTOINSTALL"',
                   'test', str(ROOT/SUBDIR/'dkms.conf')]
        result = subprocess.run(command, check=True, capture_output=True, text=True).stdout
        self.assertIn("'make' -j1 gpl", result)
        self.assertIn('MODULE_VERSION=3.2.16.2', result)
        self.assertEqual(result.count('DKMS_KERNEL_VERSION=7.0-target'), 2)
        self.assertEqual(result.count('KERNEL_BUILD=/test/headers'), 2)
        self.assertTrue(result.endswith('yes\n'))

    def test_version_generation_without_git_or_binary_patching(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory)
            shutil.copy2(ROOT/SUBDIR/'Makefile', path/'Makefile')
            shutil.copy2(ROOT/SUBDIR/'dkms.conf', path/'dkms.conf')
            (path/'kfio').mkdir()
            (path/'.source-revision').write_text('a'*40+'\n')
            binary = path/'iomemory-vsl.ko'
            binary.write_bytes(b'not-a-real-module')
            subprocess.run(['make', 'add_module_version', 'patch_module_version',
                            'DKMS_KERNEL_VERSION=7.0-target', 'MODULE_VERSION=3.2.16.1790985600.gaaaaaaaaaaaa'], cwd=path, check=True,
                           capture_output=True, text=True)
            self.assertIn('MODULE_VERSION("3.2.16.1790985600.gaaaaaaaaaaaa");', (path/'license.c').read_text())
            self.assertEqual(binary.read_bytes(), b'not-a-real-module')


if __name__ == '__main__':
    unittest.main()
