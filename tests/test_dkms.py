"""Offline lifecycle/command-contract tests; no real DKMS, module or device I/O.

Run: python3 -m unittest discover -s tests -p 'test_dkms.py' -v
The fake DKMS backend runs the real Makefile's version-generation targets in
an isolated, Git-free build copy. It does NOT compile/load the full driver.
"""
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
REL = Path("root/usr/src/iomemory-vsl-3.2.16")
FAKE_DKMS = r'''#!/usr/bin/env python3
import json, os, pathlib, shutil, subprocess, sys
args = sys.argv[1:]
action = args[0]
def arg(key):
    return args[args.index(key)+1]
root = pathlib.Path(os.environ['TEST_ROOT'])
with (root/'calls.jsonl').open('a') as f:
    f.write(json.dumps(args)+'\n')
if os.environ.get('FAIL_ACTION') == action:
    sys.exit(17)
name, version = arg('-m'), arg('-v')
source = pathlib.Path(arg('--sourcetree')) / (name+'-'+version)
state = pathlib.Path(arg('--dkmstree')) / name / version
kernel = arg('-k') if '-k' in args else None
if action == 'status':
    if kernel and (state/(kernel+'.installed')).exists():
        print(f'{name}/{version}, {kernel}, x86_64: installed')
    elif not kernel and state.exists():
        print(f'{name}/{version}: added')
elif action == 'add':
    assert source.is_dir() and not state.exists()
    state.mkdir(parents=True)
elif action == 'build':
    assert state.exists() and pathlib.Path(arg('--kernelsourcedir')).is_dir()
    build = state / ('build-'+kernel)
    if build.exists(): shutil.rmtree(build)
    shutil.copytree(source, build, symlinks=True)
    assert not (build/'.git').exists()
    env = dict(os.environ, kernelver=kernel, kernel_source_dir=arg('--kernelsourcedir'))
    config = subprocess.check_output(['bash', '-c', '. ./dkms.conf; printf "%s\\n" "$PACKAGE_VERSION" "$MAKE" "$CLEAN" "$AUTOINSTALL"'], cwd=build, env=env, text=True).splitlines()
    assert config[0] == version and config[3] == 'yes', config
    assert ' gpl ' in config[1] and kernel in config[1] and kernel in config[2], config
    subprocess.run(['make', '-s', 'add_module_version', 'patch_module_version',
                    'FIO_DKMS_BUILD=1', 'MODULE_VERSION='+version], cwd=build, check=True)
    assert f'MODULE_VERSION("{version}");' in (build/'license.c').read_text()
    (state/(kernel+'.built')).write_text(version)
elif action == 'install':
    assert (state/(kernel+'.built')).exists()
    assert '--force' not in args
    (state/(kernel+'.installed')).write_text(version)
else:
    raise AssertionError('unexpected/destructive DKMS command: '+repr(args))
'''

class DkmsLifecycle(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='iomemory-test-')
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.repo = self.root/'checkout'
        self.src = self.repo/REL
        self.src.mkdir(parents=True)
        for name in ('dkms.conf', 'dkms-install.sh', 'Makefile'):
            shutil.copy2(ROOT/REL/name, self.src/name)
        (self.src/'Kbuild').write_text('# test fixture, not a kernel build\n')
        (self.src/'kfio').mkdir()
        (self.src/'kfio/blob.o_shipped').write_text('fixture\n')
        (self.src/'kfio/latest.o_shipped').symlink_to('blob.o_shipped')
        lib = self.repo/'root/usr/lib/fio/libvsl.so'
        lib.parent.mkdir(parents=True)
        lib.write_bytes(b'test library\n')
        self.git('init', '-q')
        self.git('config', 'user.name', 'DKMS test')
        self.git('config', 'user.email', 'dkms-test@example.invalid')
        self.commit()
        bin_dir = self.root/'bin'
        bin_dir.mkdir()
        fake = bin_dir/'dkms'
        fake.write_text(FAKE_DKMS)
        fake.chmod(0o755)
        self.headers = self.root/'headers'
        self.headers.mkdir()
        (self.headers/'Makefile').write_text('# target headers fixture\n')
        self.env = dict(os.environ, PATH=str(bin_dir)+os.pathsep+os.environ['PATH'],
                        TEST_ROOT=str(self.root), DKMS_SOURCE_TREE=str(self.root/'sources'),
                        DKMS_STATE_TREE=str(self.root/'state'), DKMS_LIB_DIR=str(self.root/'lib'))
        self.env.pop('DKMS_VERSION', None)
        self.env.pop('FAIL_ACTION', None)

    def git(self, *args):
        return subprocess.check_output(['git', *args], cwd=self.repo, text=True).strip()

    def commit(self):
        self.git('add', '.')
        self.git('commit', '-qm', 'fixture')

    def run_install(self, kernel='6.12.0-target', ok=True, **env):
        result = subprocess.run(['bash', str(self.src/'dkms-install.sh'), kernel, str(self.headers)],
                                cwd=self.repo, env=dict(self.env, **env), text=True,
                                stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
        if ok:
            self.assertEqual(result.returncode, 0, result.stdout)
        else:
            self.assertNotEqual(result.returncode, 0, result.stdout)
        return result

    def calls(self):
        p = self.root/'calls.jsonl'
        return [json.loads(x) for x in p.read_text().splitlines()] if p.exists() else []

    def source(self):
        return next((self.root/'sources').glob('iomemory-vsl-*'))

    def test_registration_build_install_and_source_provenance(self):
        self.run_install()
        self.assertEqual([x[0] for x in self.calls()], ['status','add','status','build','install','status'])
        self.assertEqual((self.source()/'.dkms-source-revision').read_text().strip(), self.git('rev-parse','HEAD'))
        self.assertEqual((self.root/'lib/libvsl.so').read_bytes(), b'test library\n')

    def test_repeat_does_not_add_again_remove_or_force(self):
        self.run_install()
        self.run_install()
        self.assertEqual(sum(x[0]=='add' for x in self.calls()), 1)
        self.assertEqual(sum(x[0]=='build' for x in self.calls()), 1)
        self.assertEqual(sum(x[0]=='install' for x in self.calls()), 1)
        self.assertFalse(any(x[0]=='remove' or '--force' in x for x in self.calls()))

    def test_same_source_version_for_different_kernel(self):
        self.run_install('6.12.0-first')
        version_dir = self.source()
        self.run_install('6.13.0-next')
        self.assertEqual(self.source(), version_dir)
        self.assertEqual(len(list((self.root/'sources').glob('iomemory-vsl-*'))), 1)
        self.assertEqual(len(list((self.root/'state').rglob('*.installed'))), 2)

    def test_build_failure_preserves_existing_kernel(self):
        self.run_install('6.12.0-first')
        installed = next((self.root/'state').rglob('*.installed'))
        self.run_install('6.13.0-next', ok=False, FAIL_ACTION='build')
        self.assertTrue(installed.exists())
        self.assertEqual(sum(x[0]=='install' for x in self.calls()), 1)

    def test_failure_of_status_propagates(self):
        self.run_install(ok=False, FAIL_ACTION='status')
        self.assertEqual([x[0] for x in self.calls()], ['status'])

    def test_failure_of_add_propagates(self):
        self.run_install(ok=False, FAIL_ACTION='add')
        self.assertNotIn('build', [x[0] for x in self.calls()])

    def test_failure_of_install_propagates(self):
        self.run_install(ok=False, FAIL_ACTION='install')
        self.assertFalse((self.root/'lib/libvsl.so').exists())

    def test_missing_target_headers_fails_before_registration(self):
        (self.headers/'Makefile').unlink()
        self.run_install(ok=False)
        self.assertEqual(self.calls(), [])

    def test_tracked_dirty_source_is_rejected(self):
        with (self.src/'Makefile').open('a') as f: f.write('# dirty\n')
        self.run_install(ok=False)
        self.assertEqual(self.calls(), [])

    def test_untracked_files_are_not_staged(self):
        (self.src/'untracked-private-note').write_text('must not copy\n')
        self.run_install()
        self.assertFalse((self.source()/'untracked-private-note').exists())

    def test_changed_registered_source_is_not_overwritten(self):
        self.run_install()
        (self.source()/'Makefile').write_text('tampered\n')
        count = len(self.calls())
        self.run_install(ok=False)
        self.assertEqual(len(self.calls()), count)
        self.assertEqual((self.source()/'Makefile').read_text(), 'tampered\n')

    def test_explicit_version_collision_is_rejected(self):
        self.run_install(DKMS_VERSION='test.1')
        (self.src/'Kbuild').write_text('# different source\n')
        self.commit()
        self.run_install(ok=False, DKMS_VERSION='test.1')

    def test_invalid_version_and_kernel_are_rejected(self):
        self.run_install(ok=False, DKMS_VERSION='../outside')
        self.run_install('../outside', ok=False)
        self.assertEqual(self.calls(), [])

    def test_relative_install_root_is_rejected(self):
        self.run_install(ok=False, DKMS_SOURCE_TREE='relative')
        self.assertEqual(self.calls(), [])

    def test_external_source_link_is_rejected(self):
        (self.src/'external').symlink_to('/etc/hosts')
        self.commit()
        self.run_install(ok=False)
        self.assertEqual(self.calls(), [])

    def test_git_free_version_targets_and_config(self):
        self.run_install()
        builds = list((self.root/'state').rglob('build-*'))
        self.assertEqual(len(builds), 1)
        self.assertFalse((builds[0]/'.git').exists())
        self.assertIn('MODULE_VERSION(', (builds[0]/'license.c').read_text())

    def test_top_level_dkms_does_not_clean_running_kernel(self):
        text = (ROOT/'Makefile').read_text()
        self.assertIn('\ndkms:\n', text)
        self.assertNotIn('\ndkms: clean', text)

if __name__ == '__main__':
    unittest.main()
