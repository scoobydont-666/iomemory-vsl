"""Extracted module lifecycle and readiness error-path regressions."""
from pathlib import Path
import subprocess
import tempfile
import unittest
from test_proc_contracts import extract

SRC = Path(__file__).resolve().parents[1] / "root/usr/src/iomemory-vsl-3.2.16"

MAIN_PREFIX = r'''
#include <assert.h>
#include <errno.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#define __init
#define __exit
#define FUSION_STATIC_KERNEL 0
#define USE_QUEUE_NONE 0
#define USE_QUEUE_WQ 1
#define USE_QUEUE_SINGLE 2
#define USE_QUEUE_RQ 3
#define FIO_DRIVER_NAME "test"
#define infprint(...) do {} while(0)
#define errprint(...) do {} while(0)
static int use_workqueue,sure_erase_mode,auto_attach=1,iodrive_load_eb_map=1;
static int _dbgset;
static int fail_at,held[9],calls,waits,sysrq,cleanup_order[8],cleanups;
static const char *ifio_strerror(int rc) { (void)rc; return "test"; }
static int acquire(int n) { calls++; if(fail_at==n) return -ENOMEM; assert(!held[n]); held[n]=1; return 0; }
static void release(int n) { assert(held[n]); held[n]=0; cleanup_order[cleanups++]=n; }
static int kfio_checkstructs(void) { calls++; return fail_at==1 ? -EINVAL : 0; }
static int init_fio_dev(void) { return acquire(2); }
static int init_fio_iodrive(void) { return acquire(3); }
static int init_fio_obj(void) { return acquire(4); }
static int init_fio_blk(void) { return acquire(5); }
static int kfio_init_storage_interface(void) { return acquire(6); }
static int kfio_pci_register_driver(void) { return acquire(7) ? -EIO : 1; }
static int dbgs_create_flags_dir(void *p) { (void)p; return acquire(8); }
static void cleanup_fio_dev(void) { release(2); }
static void cleanup_fio_iodrive(void) { release(3); }
static void cleanup_fio_obj(void) { release(4); }
static void cleanup_fio_blk(void) { release(5); }
static void kfio_teardown_storage_interface(void) { release(6); }
static void kfio_pci_unregister_driver(void) { release(7); }
static void dbgs_delete_flags_dir(void *p) { (void)p; release(8); }
static void fio_auto_attach_wait(void) { waits++; }
static void kfio_iodrive_sysrq_keys(void) { assert(!sysrq); sysrq=1; }
static void kfio_iodrive_unreg_sysrq_keys(void) { assert(sysrq); sysrq=0; }
'''
MAIN_CASES = r'''
int main(int argc,char **argv) {
    assert(argc==2);
    if(!strcmp(argv[1],"failures")) {
        for(fail_at=1;fail_at<=8;fail_at++) {
            calls=waits=sysrq=cleanups=0;
            memset(held,0,sizeof(held));
            int rc=init_fio_driver();
            assert(rc<0);
            for(int i=2;i<=8;i++) assert(!held[i]);
            assert(!sysrq);
            if(fail_at<=7) assert(waits==0);
        }
    } else if(!strcmp(argv[1],"parameters")) {
        sure_erase_mode=2; assert(init_fio_driver()==-EINVAL && calls==0);
        sure_erase_mode=-1; assert(init_fio_driver()==-EINVAL && calls==0);
        sure_erase_mode=0; use_workqueue=3; assert(init_fio_driver()==-EINVAL && calls==0);
        use_workqueue=-1; assert(init_fio_driver()==-EINVAL && calls==0);
    } else if(!strcmp(argv[1],"success")) {
        sure_erase_mode=1;
        assert(init_fio_driver()==0);
        assert(auto_attach==0 && waits==1 && sysrq==1);
        for(int i=2;i<=8;i++) assert(held[i]);
        exit_fio_driver();
        for(int i=2;i<=8;i++) assert(!held[i]);
        assert(!sysrq && cleanups==7);
        for(int i=0;i<7;i++) assert(cleanup_order[i]==8-i);
    } else abort();
    return 0;
}
'''


class KernelLifecycle(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        cls.addClassCleanup(cls.tmp.cleanup)
        source = (SRC / "main.c").read_text()
        units = []
        if "static void fio_do_exit(" in source:
            units.append(extract(source, "fio_do_exit"))
        units.extend(extract(source, name) for name in
                     ["fio_do_init", "init_fio_driver", "exit_fio_driver"])
        path = Path(cls.tmp.name)
        (path / "main.c").write_text(MAIN_PREFIX + "\n".join(units) + MAIN_CASES)
        cls.exe = path / "main"
        result = subprocess.run(["cc", "-std=gnu11", "-Wall", "-Wextra",
                                 "-Wno-unused-function", str(path / "main.c"),
                                 "-o", str(cls.exe)], capture_output=True, text=True)
        if result.returncode:
            raise AssertionError(result.stderr)

    def run_case(self, case):
        result = subprocess.run([str(self.exe), case], capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_each_initialization_failure(self): self.run_case("failures")
    def test_invalid_parameters(self): self.run_case("parameters")
    def test_success_and_reverse_cleanup(self): self.run_case("success")


if __name__ == "__main__":
    unittest.main()
