"""Userspace regressions for extracted procfs adapter functions.

Mock kernel/core services isolate length, ownership, and error contracts. These
checks do not load a module or establish live kernel/hardware qualification.
"""
from pathlib import Path
import re
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "root/usr/src/iomemory-vsl-3.2.16"


def extract(source, name):
    match = re.search(r"(?m)^[A-Za-z_][^\n;]*\b" + re.escape(name) + r"\([^;]*?\)\s*\{", source)
    if match is None:
        raise ValueError("Missing function: " + name)
    start = match.start()
    opening = source.index("{", start)
    depth = 1
    end = opening + 1
    while depth:
        depth += (source[end] == "{") - (source[end] == "}")
        end += 1
    return source[start:end]


PRELUDE = r'''
#include <assert.h>
#include <errno.h>
#include <limits.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
typedef long fio_ssize_t;
typedef unsigned long fio_size_t;
typedef long long fio_loff_t;
#define __user
#define GFP_KERNEL 0
#define KFIO_INFO_INT32 2
#define KFIO_INFO_UINT32 3
#define KFIO_INFO_UINT64 4
#define KFIO_INFO_STRING 5
#define KFIO_INFO_WRITE 128
#define ERR_PTR(n) ((void *)(intptr_t)(n))
#define IS_ERR(p) ((uintptr_t)(p) >= (uintptr_t)-4095)
struct node { int type; long size; uint64_t saved; char text[128]; int calls; };
typedef struct node kfio_info_node_t;
typedef struct node fusion_inode;
typedef struct { void *private; } fusion_seq_file;
typedef struct { struct node *node; fusion_seq_file *private; } fusion_file;
typedef struct { int type; long size; void *data; } kfio_info_val_t;
typedef struct { unsigned magic; struct node *node; size_t valid; } kfio_info_data_t;
static int allocations, context_allocations, usercopy_fault;
static int handler_error, alloc_error, seq_open_error, starts, stops, frees, seq_committed;
static int kfio_info_linux_seq_ops;
static void *kfio_fs_inode(fusion_file *p) { return p->node; }
static void *kfio_inode_data(fusion_inode *p) { return p; }
static void *kfio_fs_private_data(fusion_file *p) { return p->private; }
static int kfio_info_node_get_type(struct node *n) { return n->type; }
static long kfio_info_node_get_size(struct node *n) { return n->size; }
static void *kfio_vmalloc(size_t n) { allocations++; void *p=malloc(n); memset(p,0xa5,n); return p; }
static void kfio_vfree(void *p,size_t n) { (void)n; allocations--; free(p); }
static void *kzalloc(size_t n,int flags) { (void)flags; context_allocations++; return calloc(1,n); }
static void kfree(void *p) { if(p) { context_allocations--; free(p); } }
static int kfio_copy_from_user(void *to,const void *from,unsigned n) {
    if(usercopy_fault) return n;
    memcpy(to,from,n); return 0;
}
#define copy_from_user kfio_copy_from_user
static size_t copy_to_user(void *to,const void *from,size_t n) {
    size_t miss = usercopy_fault > 0 ? (size_t)usercopy_fault : 0;
    if(miss > n) miss=n;
    memcpy(to,from,n-miss); return miss;
}
static int kfio_copy_to_user(void *to,const void *from,unsigned n) { return (int)copy_to_user(to,from,n); }
/* Kernel simple_read_from_buffer contract; the production adapter delegates to it. */
static long simple_read_from_buffer(void *to,size_t count,fio_loff_t *pos,const void *from,size_t available) {
    size_t remaining;
    if(*pos<0) return -EINVAL;
    if((uint64_t)*pos>=available || !count) return 0;
    if(count>available-(size_t)*pos) count=available-(size_t)*pos;
    remaining=copy_to_user(to,(const char *)from+*pos,count);
    if(remaining==count) return -EFAULT;
    count-=remaining; *pos+=(fio_loff_t)count; return (long)count;
}
static unsigned long kfio_strtoul(const char *s,char **e,int b) { return strtoul(s,e,b); }
static unsigned long long kfio_strtoull(const char *s,char **e,int b) { return strtoull(s,e,b); }
static long kfio_strtol(const char *s,char **e,int b) { return strtol(s,e,b); }
static int kstrtoull(const char *s,unsigned base,unsigned long long *v) {
    char *end; unsigned long long x;
    if(*s=='-' || (*s!='+' && (*s<'0'||*s>'9'))) return -EINVAL;
    errno=0; x=strtoull(s,&end,base);
    if(errno==ERANGE) return -ERANGE;
    if(end==s || (*end && strcmp(end,"\n"))) return -EINVAL;
    *v=x; return 0;
}
static int kstrtouint(const char *s,unsigned base,unsigned int *v) {
    unsigned long long x; int rc=kstrtoull(s,base,&x);
    if(rc) return rc;
    if(x>UINT_MAX) return -ERANGE;
    *v=(unsigned)x; return 0;
}
static int kstrtoint(const char *s,unsigned base,int *v) {
    char *end; long long x;
    if(*s!='+' && *s!='-' && (*s<'0'||*s>'9')) return -EINVAL;
    errno=0; x=strtoll(s,&end,base);
    if(errno==ERANGE || x<INT_MIN || x>INT_MAX) return -ERANGE;
    if(end==s || (*end && strcmp(end,"\n"))) return -EINVAL;
    *v=(int)x; return 0;
}
static int kfio_info_generic_type_handler(struct node *n,int cmd,void *old,kfio_info_val_t *v) {
    (void)cmd; (void)old;
    if(handler_error) return handler_error;
    n->calls++;
    if(v->type==KFIO_INFO_UINT32) { assert(v->size==4); n->saved=*(uint32_t*)v->data; }
    else if(v->type==KFIO_INFO_UINT64) { assert(v->size==8); n->saved=*(unsigned long long*)v->data; }
    else if(v->type==KFIO_INFO_INT32) { assert(v->size==4); n->saved=(uint64_t)*(int*)v->data; }
    else { assert(v->size==n->size); memcpy(n->text,v->data,(size_t)v->size); }
    return 0;
}
static void *kfio_fseq_private(fusion_seq_file *s) { return s->private; }
static void kfio_fseq_set_private(fusion_seq_file *s,void *p) { s->private=p; }
static size_t kfio_seq_get_buf(fusion_seq_file *s,char **buf) { (void)s; static char b[128]; *buf=b; return sizeof(b); }
static int kfio_info_alloc_data_handle(struct node *n,void *buf,size_t len,kfio_info_data_t **h) {
    (void)buf; (void)len;
    if(alloc_error) return alloc_error;
    *h=calloc(1,sizeof(**h)); (*h)->node=n; (*h)->magic=0xaabbccdd; return 0;
}
static struct node *kfio_info_data_node(kfio_info_data_t *h) { assert(h->magic==0xaabbccdd); return h->node; }
static void kfio_info_free_data_handle(kfio_info_data_t *h) { assert(h->magic==0xaabbccdd); h->magic=0; frees++; free(h); }
static void *kfio_info_seq_init(struct node *n,fio_loff_t *p,kfio_info_data_t *h) { assert(h->node==n); (void)p; starts++; return n; }
static void *kfio_info_seq_next(struct node *n,void *cookie,fio_loff_t *p) { assert(cookie==n); ++*p; return NULL; }
static void kfio_info_seq_stop(struct node *n,void *cookie) { assert(cookie==n); stops++; }
static int kfio_info_seq_show(struct node *n,void *cookie,kfio_info_data_t *h) { assert(cookie==n&&h->node==n); h->valid+=5; return 0; }
static size_t kfio_info_data_size_valid(kfio_info_data_t *h) { return h->valid; }
static void kfio_seq_commit(fusion_seq_file *s,int bytes) { (void)s; seq_committed+=bytes; }
static int kfio_seq_open(fusion_file *f,void *ops) { (void)ops; if(seq_open_error) return seq_open_error; f->private=calloc(1,sizeof(*f->private)); return 0; }
static int kfio_seq_release(fusion_inode *n,fusion_file *f) { (void)n; free(f->private); f->private=NULL; return 0; }
'''

CASES = r'''
int main(int argc,char **argv) {
    assert(argc==2);
    struct node node={.type=KFIO_INFO_UINT32,.size=4};
    fusion_file file={.node=&node};
    fio_loff_t pos=0;
    if(!strcmp(argv[1],"read_bounds")) {
        char backing[32]="1234----ADJACENT", out[16]={0}; pos=8;
        assert(fio_proc_read_buffer(backing,4,out,8,&pos)==0);
        assert(pos==8 && out[0]==0);
        pos=4; assert(fio_proc_read_buffer(backing,4,out,8,&pos)==0);
        pos=-1; assert(fio_proc_read_buffer(backing,4,out,8,&pos)==-EINVAL);
        pos=0; assert(fio_proc_read_buffer(backing,-1,out,8,&pos)==-EINVAL);
    } else if(!strcmp(argv[1],"read_copy_fault")) {
        char out[8]={0}; usercopy_fault=4;
        assert(fio_proc_read_buffer("1234",4,out,4,&pos)==-EFAULT && pos==0);
        usercopy_fault=2;
        assert(fio_proc_read_buffer("1234",4,out,4,&pos)==2 && pos==2 && !memcmp(out,"12",2));
    } else if(!strcmp(argv[1],"write_range")) {
        assert(kfio_info_os_type_write(&file,"4294967296\n",11,&pos)==-ERANGE);
        assert(pos==0 && node.calls==0);
        assert(kfio_info_os_type_write(&file,"4294967295\n",11,&pos)==11 && node.saved==UINT32_MAX);
        node.type=KFIO_INFO_INT32; pos=0;
        assert(kfio_info_os_type_write(&file,"2147483648",10,&pos)==-ERANGE && pos==0);
        assert(kfio_info_os_type_write(&file,"-2147483648",11,&pos)==11 && (int)node.saved==INT_MIN);
        node.type=KFIO_INFO_UINT64; node.size=8; pos=0;
        assert(kfio_info_os_type_write(&file,"18446744073709551616",20,&pos)==-ERANGE && pos==0);
        assert(kfio_info_os_type_write(&file,"18446744073709551615",20,&pos)==20 && node.saved==UINT64_MAX);
    } else if(!strcmp(argv[1],"write_invalid")) {
        const char *bad[]={"1x","-1","","1\n\n","+"," 1"};
        for(size_t i=0;i<sizeof(bad)/sizeof(*bad);i++) {
            assert(kfio_info_os_type_write(&file,bad[i],strlen(bad[i]),&pos)==-EINVAL);
            assert(node.calls==0 && pos==0);
        }
        char embedded[4]={'1',0,'2','3'};
        assert(kfio_info_os_type_write(&file,embedded,sizeof(embedded),&pos)==-EINVAL);
        char full[32]; memset(full,'1',sizeof(full));
        assert(kfio_info_os_type_write(&file,full,sizeof(full),&pos)==-EINVAL);
        usercopy_fault=1; assert(kfio_info_os_type_write(&file,"1",1,&pos)==-EFAULT && pos==0);
        usercopy_fault=0; handler_error=-EPERM;
        assert(kfio_info_os_type_write(&file,"1",1,&pos)==-EPERM && pos==0);
    } else if(!strcmp(argv[1],"string_cleanup")) {
        char bytes[65]; memset(bytes,'A',sizeof(bytes)); node.type=KFIO_INFO_STRING; node.size=64;
        assert(kfio_info_os_type_write(&file,bytes,65,&pos)==-EINVAL);
        assert(allocations==0 && pos==0 && node.calls==0);
        assert(kfio_info_os_type_write(&file,bytes,64,&pos)==-EINVAL);
        assert(allocations==0 && pos==0 && node.calls==0);
        bytes[63]=0;
        assert(kfio_info_os_type_write(&file,bytes,64,&pos)==64 && allocations==0);
        pos=0; usercopy_fault=1;
        assert(kfio_info_os_type_write(&file,bytes,3,&pos)==-EFAULT && allocations==0 && pos==0);
    } else if(!strcmp(argv[1],"string_padding")) {
        node.type=KFIO_INFO_STRING; node.size=64;
        assert(kfio_info_os_type_write(&file,"abc",3,&pos)==3 && pos==3);
        assert(!memcmp(node.text,"abc",3));
        for(int i=3;i<64;i++) assert(node.text[i]==0);
        assert(allocations==0);
    } else if(!strcmp(argv[1],"sequence_failure")) {
        assert(kfio_info_seqf_open(&node,&file)==0);
        alloc_error=-ENOMEM;
        void *cookie=kfio_info_linux_seq_start(file.private,&pos);
        assert(cookie==ERR_PTR(-ENOMEM));
        kfio_info_linux_seq_stop(file.private,cookie);
        assert(starts==0 && stops==0 && frees==0);
        assert(kfio_info_seqf_release(&node,&file)==0 && context_allocations==0);
    } else if(!strcmp(argv[1],"sequence_lifecycle")) {
        assert(kfio_info_seqf_open(&node,&file)==0);
        for(int i=0;i<2;i++) {
            void *cookie=kfio_info_linux_seq_start(file.private,&pos);
            assert(cookie==&node);
            assert(kfio_info_linux_seq_show(file.private,cookie)==0);
            assert(kfio_info_linux_seq_next(file.private,cookie,&pos)==NULL);
            kfio_info_linux_seq_stop(file.private,cookie);
        }
        assert(starts==2 && stops==2 && frees==2 && seq_committed==10);
        assert(kfio_info_seqf_release(&node,&file)==0 && context_allocations==0);
        seq_open_error=-ENOMEM;
        assert(kfio_info_seqf_open(&node,&file)==-ENOMEM && context_allocations==0);
    } else abort();
    return 0;
}
'''


class ProcContracts(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        cls.addClassCleanup(cls.tmp.cleanup)
        source = (SRC / "kinfo.c").read_text()
        units = []
        marker = "struct kfio_info_seq_context"
        if marker in source:
            first = source.index(marker)
            last = source.index("};", first) + 2
            units.append(source[first:last])
        names = ["fio_proc_read_buffer", "kfio_info_os_type_write",
                 "kfio_info_linux_seq_start", "kfio_info_linux_seq_next",
                 "kfio_info_linux_seq_stop", "kfio_info_linux_seq_show",
                 "kfio_info_seqf_open"]
        units.extend(extract(source, name) for name in names)
        if "kfio_info_seqf_release(" in source:
            units.append(extract(source, "kfio_info_seqf_release"))
        else:
            units.append("#define kfio_info_seqf_release kfio_seq_release")
        path = Path(cls.tmp.name)
        (path / "proc.c").write_text(PRELUDE + "\n".join(units) + CASES)
        cls.exe = path / "proc"
        result = subprocess.run(["cc", "-std=gnu11", "-Wall", "-Wextra",
                                 "-Wno-unused-function", str(path / "proc.c"),
                                 "-o", str(cls.exe)], capture_output=True, text=True)
        if result.returncode:
            raise AssertionError(result.stderr)

    def run_case(self, case):
        result = subprocess.run([str(self.exe), case], capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_read_bounds(self): self.run_case("read_bounds")
    def test_read_copy_fault(self): self.run_case("read_copy_fault")
    def test_write_ranges(self): self.run_case("write_range")
    def test_write_invalid_input_and_errors(self): self.run_case("write_invalid")
    def test_string_cleanup(self): self.run_case("string_cleanup")
    def test_string_padding(self): self.run_case("string_padding")
    def test_sequence_allocation_failure(self): self.run_case("sequence_failure")
    def test_sequence_lifecycle(self): self.run_case("sequence_lifecycle")


if __name__ == "__main__":
    unittest.main()
