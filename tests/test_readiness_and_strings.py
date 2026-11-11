"""Readiness ownership, control-device failures, and bounded string ABI tests."""
from pathlib import Path
import subprocess
import tempfile
import unittest
from test_proc_contracts import extract

SRC = Path(__file__).resolve().parents[1] / "root/usr/src/iomemory-vsl-3.2.16"

PREFIX = r'''
#include <assert.h>
#include <errno.h>
#include <limits.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/mman.h>
#include <unistd.h>
#include <sys/stat.h>
#define UFIO_DEVICE_FILE_MAX_LEN 128
#define UFIO_CONTROL_DEVICE_PATH "/dev/"
#define LOOKUP_PARENT 1
#define LOOKUP_FOLLOW 2
#define READ_ONCE(x) (x)
#define infprint(...) do {} while(0)
#define errprint(...) do {} while(0)
typedef size_t fio_size_t;
struct inode { unsigned i_mode; };
struct dentry { struct inode *inode; };
struct path { struct dentry *dentry; };
static struct inode inode;
static struct dentry dent={.inode=&inode};
static int fio_dev_wait_timeout_secs=1;
static int remaining_misses,path_error,path_calls,refs,sleeps;
static int kern_path(const char *name,int flags,struct path *p) {
    assert(!strcmp(name,"/dev/fct0"));
    assert(flags==LOOKUP_FOLLOW);
    path_calls++;
    if(path_error) return path_error;
    if(remaining_misses-- > 0) return -ENOENT;
    p->dentry=&dent; refs++; return 0;
}
static struct inode *d_inode(struct dentry *d) { return d->inode; }
static void path_put(struct path *p) { assert(p->dentry==&dent && refs==1); refs--; }
static void msleep(unsigned ms) { assert(ms==100); sleeps++; }
'''
CASES = r'''
int main(int argc,char **argv) {
    assert(argc==2); inode.i_mode=S_IFCHR;
    if(!strcmp(argv[1],"exists")) {
        remaining_misses=2;
        assert(fio_wait_for_dev("fct0")==0);
        assert(path_calls==3 && sleeps==2 && refs==0);
        inode.i_mode=S_IFBLK;
        assert(fio_wait_for_dev("fct0")==0 && refs==0);
    } else if(!strcmp(argv[1],"timeout")) {
        remaining_misses=20;
        assert(fio_wait_for_dev("fct0")==-ETIMEDOUT);
        assert(sleeps==10 && path_calls==11 && refs==0);
    } else if(!strcmp(argv[1],"invalid")) {
        fio_dev_wait_timeout_secs=-1;
        assert(fio_wait_for_dev("fct0")==-EINVAL && path_calls==0);
        fio_dev_wait_timeout_secs=INT_MAX;
        assert(fio_wait_for_dev("fct0")==-EINVAL && path_calls==0);
        fio_dev_wait_timeout_secs=1;
        char huge[512]; memset(huge,'a',sizeof(huge)-1); huge[sizeof(huge)-1]=0;
        assert(fio_wait_for_dev(huge)==-ENAMETOOLONG && path_calls==0);
        inode.i_mode=S_IFREG;
        assert(fio_wait_for_dev("fct0")==-ENODEV && refs==0);
        inode.i_mode=S_IFCHR; path_error=-EACCES;
        assert(fio_wait_for_dev("fct0")==-EACCES && refs==0);
    } else if(!strcmp(argv[1],"strings")) {
        char out[16];
        memset(out,0xa5,sizeof(out));
        assert(kfio_strncpy(out,"ab",8)==out);
        assert(!memcmp(out,"ab\0\0\0\0\0\0",8) && (unsigned char)out[8]==0xa5);
        kfio_strncpy(out,"abcdefghij",4); assert(!memcmp(out,"abcd",4) && out[4]==0);
        long page=sysconf(_SC_PAGESIZE);
        char *map=mmap(NULL,page*2,PROT_READ|PROT_WRITE,MAP_PRIVATE|MAP_ANONYMOUS,-1,0);
        assert(map!=MAP_FAILED && mprotect(map+page,page,PROT_NONE)==0);
        memset(map+page-4,'Z',4);
        kfio_strncpy(out,map+page-4,4); assert(!memcmp(out,"ZZZZ",4));
        assert(kfio_strncpy(out,map+page,0)==out);
        assert(munmap(map,page*2)==0);
    } else abort();
    return 0;
}
'''
CDEV_PREFIX = r'''
#include <assert.h>
#include <errno.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#define errprint(...) do {} while(0)
#define infprint(...) do {} while(0)
struct miscdevice { int live; };
struct fusion_nand_device { struct miscdevice misc; };
static int register_error,wait_error,waits,deregisters;
static void *fusion_nand_get_miscdev(struct fusion_nand_device *n) { return &n->misc; }
static char *fusion_nand_get_dev_name(struct fusion_nand_device *n) { (void)n; return "fct0"; }
static const char *fusion_nand_get_bus_name(struct fusion_nand_device *n) { (void)n; return "test"; }
static int fusion_nand_get_devnum(struct fusion_nand_device *n) { (void)n; return 0; }
static void misc_dev_init(struct miscdevice *m,char *n) { (void)n; m->live=0; }
static int misc_register(struct miscdevice *m) { if(register_error) return register_error; m->live=1; return 0; }
static void misc_deregister(struct miscdevice *m) { assert(m->live); m->live=0; deregisters++; }
static int fio_wait_for_dev(const char *name) { assert(!strcmp(name,"fct0")); waits++; return wait_error; }
'''
CDEV_CASES = r'''
int main(int argc,char **argv) {
    assert(argc==2); struct fusion_nand_device n={0};
    if(!strcmp(argv[1],"registration")) {
        register_error=-ENOMEM;
        assert(fusion_create_control_device(&n)==-ENOMEM && waits==0 && deregisters==0);
    } else if(!strcmp(argv[1],"readiness")) {
        wait_error=-ETIMEDOUT;
        assert(fusion_create_control_device(&n)==0 && waits==0 && deregisters==0 && n.misc.live);
        assert(fusion_destroy_control_device(&n)==0 && deregisters==1);
    } else if(!strcmp(argv[1],"success")) {
        assert(fusion_create_control_device(&n)==0 && waits==0 && n.misc.live);
        assert(fusion_destroy_control_device(&n)==0 && deregisters==1 && !n.misc.live);
    } else abort();
    return 0;
}
'''


def compile_fixture(case, text):
    case.tmp = tempfile.TemporaryDirectory()
    case.addClassCleanup(case.tmp.cleanup)
    path = Path(case.tmp.name)
    (path / "fixture.c").write_text(text)
    case.exe = path / "fixture"
    result = subprocess.run(["cc", "-std=gnu11", "-Wall", "-Wextra",
                             "-Wno-unused-function", str(path / "fixture.c"),
                             "-o", str(case.exe)], capture_output=True, text=True)
    if result.returncode:
        raise AssertionError(result.stderr)


class ReadinessAndStrings(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        units = extract((SRC / "kfio.c").read_text(), "fio_wait_for_dev")
        units += extract((SRC / "kfio_common.c").read_text(), "kfio_strncpy")
        compile_fixture(cls, PREFIX + units + CASES)

    def run_case(self, case):
        result = subprocess.run([str(self.exe), case], capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_existing_device_and_path_release(self): self.run_case("exists")
    def test_missing_device_timeout(self): self.run_case("timeout")
    def test_invalid_readiness_inputs(self): self.run_case("invalid")
    def test_bounded_string_abi(self): self.run_case("strings")


class ControlDeviceLifecycle(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        source = (SRC / "cdev.c").read_text()
        units = extract(source, "fusion_create_control_device") + extract(source, "fusion_destroy_control_device")
        compile_fixture(cls, CDEV_PREFIX + units + CDEV_CASES)

    def run_case(self, case):
        result = subprocess.run([str(self.exe), case], capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_failed_registration_does_not_wait(self): self.run_case("registration")
    def test_registration_does_not_require_dev_mount(self): self.run_case("readiness")
    def test_success_and_destroy(self): self.run_case("success")


if __name__ == "__main__":
    unittest.main()
