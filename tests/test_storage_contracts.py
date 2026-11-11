"""Execute extracted production storage adapters with deterministic kernel mocks.

These checks prove adapter contracts; real DMA, kernel locking and power-loss
qualification still require isolated hardware. No device or module is used.
"""
from pathlib import Path
import os
import re
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
SRC = Path(os.environ.get("IOMEMORY_TEST_SOURCE", ROOT / "root/usr/src/iomemory-vsl-3.2.16"))


def function(source, name):
    match = re.search(r"^[\w *]+\b" + name + r"\([^;]*?\)\s*\{", source, re.M)
    if not match:
        raise AssertionError(f"Production function not found: {name}")
    end = source.index("{", match.start()) + 1
    depth = 1
    while depth:
        depth += (source[end] == "{") - (source[end] == "}")
        end += 1
    return source[match.start():end]


def run_c(test, code):
    with tempfile.TemporaryDirectory(prefix="iomemory-storage-") as tmp:
        src, exe = Path(tmp) / "test.c", Path(tmp) / "test"
        src.write_text(code)
        sanitizer = os.environ.get("IOMEMORY_TEST_SANITIZERS")
        extra = [f"-fsanitize={sanitizer}", "-g"] if sanitizer else []
        build = subprocess.run(["cc", *extra, "-std=gnu11", "-Wall", "-Wextra", "-Werror",
                                "-Wno-unused-parameter", "-Wno-unused-function",
                                "-Wno-unused-variable", "-Wno-unused-but-set-variable",
                                "-Wno-sign-compare", str(src), "-o", str(exe)],
                               capture_output=True, text=True)
        test.assertEqual(build.returncode, 0, build.stderr)
        environment = dict(os.environ)
        if sanitizer:
            environment.setdefault("ASAN_OPTIONS", "detect_leaks=0")
        result = subprocess.run([str(exe)], capture_output=True, text=True,
                                timeout=10, env=environment)
        test.assertEqual(result.returncode, 0, result.stdout + result.stderr)


SG_PREFIX = r'''
#include <stdint.h>
#include <stddef.h>
#include <stdlib.h>
#include <stdio.h>
#include <string.h>
#include <errno.h>
#include <assert.h>
struct device { int unused; };
struct pci_dev { struct device dev; };
struct linux_sgentry { char *dummy; };
struct scatterlist { unsigned char *page; uint32_t offset, length; uint64_t address; uint32_t dma_length; };
struct linux_sgl {
 uint32_t max_entries, num_entries, num_mapped, sgl_size;
 struct pci_dev *pci_dev; int pci_dir;
 struct linux_sgentry *sge; struct scatterlist *sl;
};
struct kfio_dma_map {
 uint32_t map_offset, map_length, sge_count, sge_skip, sge_trunc;
 struct linux_sgentry *sge_first, *sge_last; struct linux_sgl *lsg;
};
typedef struct linux_sgl kfio_sg_list_t;
typedef struct kfio_dma_map kfio_dma_map_t;
typedef void *kfio_sgl_iter_t;
typedef struct { uint64_t addr; uint32_t len; } kfio_sgl_phys_t;
#define IODRIVE_DMA_DIR_READ 1
#define IODRIVE_DMA_DIR_WRITE 2
#define DMA_FROM_DEVICE 1
#define DMA_TO_DEVICE 2
#define FUSION_PAGE_SIZE 4096U
#define MIN(a,b) ((a)<(b)?(a):(b))
#define sg_page(sg) ((sg)->page)
#define sg_dma_address(sg) ((sg)->address)
#define sg_dma_len(sg) ((sg)->dma_length)
#define sge_to_sl(lsg,sge) ((lsg)->sl+((sge)-(lsg)->sge))
#define preempt_disable() ((void)0)
#define preempt_enable() ((void)0)
#define kmap_atomic(p) (p)
#define kunmap_atomic(p) ((void)0)
#define kfio_memcpy memcpy
#define kfio_memset memset
#define kassert(x) assert(x)
static int map_result, unmaps, original_unmap_count;
static int dma_map_sg(struct device *d,struct scatterlist *s,unsigned n,int dir) { return map_result; }
static void dma_unmap_sg(struct device *d,struct scatterlist *s,unsigned n,int dir) { unmaps++; original_unmap_count=n; }
int kfio_sgl_dma_unmap(kfio_sg_list_t *sgl);
'''


class StorageContracts(unittest.TestCase):
    def test_dma_coalescing_and_slice(self):
        source = (SRC / "kscatter.c").read_text()
        names = ["kfio_sgl_dma_map", "kfio_sgl_dma_unmap", "kfio_sgl_phys_first",
                 "kfio_sgl_phys_next", "kfio_sgl_dma_slice", "kfio_dma_map_first", "kfio_dma_map_next"]
        run_c(self, SG_PREFIX + "\n".join(function(source, n) for n in names) + r'''
int main(void) {
 struct pci_dev p={0}; struct linux_sgentry entries[3]={0};
 struct scatterlist sl[3]={{.length=100,.dma_length=200,.address=0x1000},
                         {.length=100,.dma_length=100,.address=0x3000},
                         {.length=100}};
 struct linux_sgl s={.max_entries=3,.num_entries=3,.sgl_size=300,.pci_dev=&p,.sge=entries,.sl=sl};
 struct kfio_dma_map map={0}; kfio_sgl_phys_t seg={0}; void *it;
 map_result=2;
 assert(kfio_sgl_dma_map(&s,&map,IODRIVE_DMA_DIR_READ)==2);
 assert(unmaps==0 && map.sge_count==2 && map.map_length==300);
 it=kfio_sgl_phys_first(&s,&seg); assert(it && seg.addr==0x1000 && seg.len==200);
 it=kfio_sgl_phys_next(&s,it,&seg); assert(it && seg.addr==0x3000 && seg.len==100);
 assert(!kfio_sgl_phys_next(&s,it,&seg));
 assert(kfio_sgl_dma_slice(&s,&map,150,100)==0);
 it=kfio_dma_map_first(&map,&seg); assert(it && seg.addr==0x1096 && seg.len==50);
 it=kfio_dma_map_next(&map,it,&seg); assert(it && seg.addr==0x3000 && seg.len==50);
 assert(!kfio_dma_map_next(&map,it,&seg));
 assert(kfio_sgl_dma_slice(&s,&map,300,0)==0);
 assert(map.sge_count==0 && !kfio_dma_map_first(&map,&seg));
 assert(kfio_sgl_dma_slice(&s,&map,301,0)==-EINVAL);
 assert(kfio_sgl_dma_slice(&s,&map,299,2)==-EINVAL);
 assert(kfio_sgl_dma_slice(&s,&map,UINT32_MAX,2)==-EINVAL);
 kfio_sgl_dma_unmap(&s);
 assert(unmaps==1 && original_unmap_count==3 && s.num_mapped==0);
 map_result=0;
 assert(kfio_sgl_dma_map(&s,&map,IODRIVE_DMA_DIR_READ)<0);
 assert(unmaps==1 && !map.sge_count && !map.sge_first);
 return 0;
}
''')

    def test_copy_offsets_boundaries_and_empty_lists(self):
        source = (SRC / "kscatter.c").read_text()
        run_c(self, SG_PREFIX + function(source, "kfio_sgl_copy_data") + r'''
int main(void) {
 unsigned char input[4096], output[4096];
 for (unsigned i=0;i<sizeof(input);i++) input[i]=(unsigned char)(i%251);
 memset(output,0,sizeof(output));
 struct scatterlist srcvec[2]={{.page=input,.offset=20,.length=100},{.page=input,.offset=200,.length=70}};
 struct scatterlist dstvec[3]={{.page=output,.offset=300,.length=25},{.page=output,.offset=600,.length=100},{.page=output,.offset=1000,.length=45}};
 struct linux_sgl src={.num_entries=2,.sgl_size=170,.sl=srcvec};
 struct linux_sgl dst={.num_entries=3,.sgl_size=170,.sl=dstvec};
 assert(kfio_sgl_copy_data(&dst,&src,170)==0);
 assert(!memcmp(output+300,input+20,25));
 assert(!memcmp(output+600,input+45,75));
 assert(!memcmp(output+675,input+200,25));
 assert(!memcmp(output+1000,input+225,45));
 assert(output[299]==0 && output[325]==0 && output[1045]==0);
 assert(kfio_sgl_copy_data(&dst,&src,171)==-EFAULT);
 struct linux_sgl empty={0};
 assert(kfio_sgl_copy_data(&empty,&empty,0)==0);
 assert(kfio_sgl_copy_data(&empty,&src,1)==-EFAULT);
 src.num_entries=1; /* Reject inconsistent capacity instead of overrunning. */
 assert(kfio_sgl_copy_data(&dst,&src,170)==-EFAULT);
 srcvec[0].length=0; src.num_entries=2; src.sgl_size=70;
 assert(kfio_sgl_copy_data(&dst,&src,70)==0);
 return 0;
}
''')


BLOCK_PREFIX = r'''
#include <assert.h>
#include <errno.h>
#include <stdbool.h>
#include <stdint.h>
#include <stdlib.h>
#include <string.h>
#define REQ_OP_MASK 0xffU
#define REQ_OP_READ 0U
#define REQ_OP_WRITE 1U
#define REQ_OP_FLUSH 2U
#define REQ_OP_DISCARD 3U
#define REQ_SYNC (1U<<11)
#define REQ_FUA (1U<<16)
#define REQ_PREFLUSH (1U<<17)
#define KBIO_CMD_READ 1
#define KBIO_CMD_WRITE 2
#define KBIO_CMD_DISCARD 3
#define KBIO_CMD_FLUSH 4
#define KBIO_FLG_SYNC 1
#define KBIO_FLG_DUMP 64
#define READ 0
#define WRITE 1
#define KERNEL_SECTOR_SIZE 512U
#define IODRIVE_DMA_DIR_INVALID -1
#define IODRIVE_DMA_DIR_READ 1
#define IODRIVE_DMA_DIR_WRITE 2
#define engprint(...) do {} while(0)
#define unlikely(x) (x)
#define bio_op(b) ((b)->bi_opf & REQ_OP_MASK)
#define bio_data_dir(b) ((b)->bi_opf & 1)
#define BI_SIZE(b) ((b)->bi_iter.bi_size)
#define BI_SECTOR(b) ((b)->bi_iter.bi_sector)
#define kassert(x) assert(x)
#define GFP_ATOMIC 0
#define errno_to_blk_status(x) (x)
struct bio { uint32_t bi_opf; unsigned long bi_flags; struct { uint32_t bi_size; uint64_t bi_sector;} bi_iter; struct bio *bi_next; int bi_status, completions; };
struct kfio_disk { void *dev; uint32_t sector_mask; };
struct request_queue { void *queuedata; unsigned long queue_flags; struct { unsigned int features; } limits; };
typedef uintptr_t fio_uintptr_t;
typedef struct kfio_bio kfio_bio_t;
struct kfio_bio { uint32_t fbio_flags; uint64_t fbio_size, fbio_offset; int fbio_cmd, fbio_cpu; void *fbio_sgl,*fbio_dmap,*fbio_dev; void (*fbio_completor)(kfio_bio_t *,uint64_t,int); fio_uintptr_t fbio_parameter; };
static int alloc_count, alloc_fail_at, frees, dma_fail, maps, unmaps, submits, sync_completion, sync_error_at, ctx_fail;
static kfio_bio_t *pending;
static int submitted_commands[16];
static kfio_bio_t *kfio_bio_alloc(void *dev) {
 if (++alloc_count == alloc_fail_at) return NULL;
 kfio_bio_t *f=calloc(1,sizeof(*f)); f->fbio_dev=dev; return f;
}
#define kfio_bio_try_alloc kfio_bio_alloc
static void kfio_bio_free(kfio_bio_t *f) { frees++; free(f); }
static void *kzalloc(size_t n,int flags) { return ctx_fail ? NULL : calloc(1,n); }
#define kfree free
static void kfio_set_comp_cpu(kfio_bio_t *f,struct bio *b) {}
static int kfio_sgl_map_bio(void *s,struct bio *b) { return 0; }
static int kfio_sgl_dma_map(void *s,void *d,int dir) { if (dma_fail) return -EIO; maps++;return 1; }
static int kfio_sgl_dma_unmap(void *s) { unmaps++;return 0; }
static void bio_endio(struct bio *b) { b->completions++; }
static void kfio_dump_fbio(kfio_bio_t *f) {}
static void kfio_dump_bio(const char *s,struct bio *b) {}
#define FIO_DRIVER_NAME "test"
static int kfio_bio_submit(kfio_bio_t *f) {
 submitted_commands[submits++]=f->fbio_cmd;
 if (sync_completion) {
  int error=(submits==sync_error_at) ? -EIO : 0;
  f->fbio_completor(f,f->fbio_size,error); kfio_bio_free(f); return error;
 }
 assert(pending==NULL); pending=f; return 0;
}
static void finish(int error) {
 kfio_bio_t *f=pending; assert(f); pending=NULL;
 f->fbio_completor(f,f->fbio_size,error);
 kfio_bio_free(f);
}
#define BLK_FEAT_WRITE_CACHE (1u<<0)
#define BLK_FEAT_ROTATIONAL (1u<<2)
#define BLK_FEAT_ADD_RANDOM (1u<<3)
static void blk_queue_flag_set(unsigned i,struct request_queue *q) { q->queue_flags|=(1ul<<i); }
static void blk_queue_flag_clear(unsigned i,struct request_queue *q) { q->queue_flags&=~(1ul<<i); }
'''


class BlockContracts(unittest.TestCase):
    def test_flags_features_and_completion(self):
        source = (SRC / "kblock.c").read_text()
        names = ["fbio_need_dma_map", "kfio_bio_is_discard", "__kfio_bio_sync",
                 "__kfio_bio_complete", "kfio_bio_completor", "kfio_map_to_fbio"]
        features = source[source.index("#ifdef QUEUE_FLAG_WC"):source.index("    *diskp = dp;")]
        flags = next(line for line in source.splitlines() if line.startswith("#define bio_flags"))
        run_c(self, BLOCK_PREFIX + flags + "\n" + "\n".join(function(source,n) for n in names) +
              "\nstatic void apply_features(struct request_queue *rq) {\n" + features + "}\n" + r'''
int main(void) {
 struct kfio_disk d={0}; struct request_queue q={.queuedata=&d};
 apply_features(&q); assert(q.limits.features & BLK_FEAT_WRITE_CACHE); assert(q.queue_flags==0);
 struct bio b={.bi_opf=REQ_OP_WRITE|REQ_SYNC,.bi_iter={.bi_size=512}};
 assert(__kfio_bio_sync(&b));
 kfio_bio_t *f=kfio_map_to_fbio(&q,&b); assert(f && f->fbio_cmd==KBIO_CMD_WRITE && (f->fbio_flags&KBIO_FLG_SYNC)); kfio_bio_free(f);
 b.bi_opf=REQ_OP_FLUSH; b.bi_iter.bi_size=0;
 f=kfio_map_to_fbio(&q,&b); assert(f && f->fbio_cmd==KBIO_CMD_FLUSH); kfio_bio_free(f);
 b.bi_opf=REQ_OP_WRITE|REQ_PREFLUSH;
 f=kfio_map_to_fbio(&q,&b); assert(f && f->fbio_cmd==KBIO_CMD_FLUSH); kfio_bio_free(f);
 b.bi_opf=77; assert(!kfio_map_to_fbio(&q,&b));
 return 0;
}
''')

    def test_ordering_failure_ownership_and_merge_boundaries(self):
        source = (SRC / "kblock.c").read_text()
        names = ["fbio_need_dma_map", "kfio_bio_is_discard", "__kfio_bio_sync",
                 "__kfio_bio_complete", "kfio_bio_completor", "kfio_kbio_add_bio", "kfio_map_to_fbio"]
        flags = next(line for line in source.splitlines() if line.startswith("#define bio_flags"))
        ordered = source[source.index("struct kfio_ordered_io\n{"):source.index("static void kfio_kickoff_plugged_io")]
        run_c(self, BLOCK_PREFIX + flags + "\n" + "\n".join(function(source,n) for n in names) + ordered + r'''
static void reset(void) {
 assert(!pending); alloc_count=alloc_fail_at=frees=dma_fail=maps=unmaps=submits=0;
 sync_completion=sync_error_at=ctx_fail=0; memset(submitted_commands,0,sizeof(submitted_commands));
}
int main(void) {
 struct kfio_disk d={0}; struct request_queue q={.queuedata=&d};
 for (unsigned flags=0;flags<4;flags++) {
  reset();
  struct bio b={.bi_opf=REQ_OP_WRITE|((flags&1)?REQ_PREFLUSH:0)|((flags&2)?REQ_FUA:0),.bi_iter={.bi_size=512}};
  kfio_bio_t *f=kfio_convert_bio(&q,&b); assert(f); kfio_bio_submit(f);
  assert(b.completions==0);
  if(flags&1) { assert(pending->fbio_cmd==KBIO_CMD_FLUSH); finish(0); assert(b.completions==0); }
  assert(pending->fbio_cmd==KBIO_CMD_WRITE); finish(0);
  if(flags&2) { assert(b.completions==0 && pending->fbio_cmd==KBIO_CMD_FLUSH); finish(0); }
  assert(b.completions==1 && b.bi_status==0 && !pending && maps==1 && unmaps==1);
  assert(frees==alloc_count);
 }
 for (int fail_stage=1;fail_stage<=3;fail_stage++) {
  reset();
  struct bio b={.bi_opf=REQ_OP_WRITE|REQ_PREFLUSH|REQ_FUA,.bi_iter={.bi_size=512}};
  kfio_bio_t *f=kfio_convert_bio(&q,&b); assert(f); kfio_bio_submit(f);
  for(int stage=1;stage<=fail_stage;stage++) finish(stage==fail_stage ? -EIO:0);
  assert(b.completions==1 && b.bi_status==-EIO && !pending);
  assert(frees==alloc_count && maps==1 && unmaps==1 && submits==fail_stage);
 }
 /* Submission may call completion inline: no submitted object may be touched afterward. */
 for (int fail_stage=0;fail_stage<=3;fail_stage++) {
  reset(); sync_completion=1;sync_error_at=fail_stage;
  struct bio b={.bi_opf=REQ_OP_WRITE|REQ_PREFLUSH|REQ_FUA,.bi_iter={.bi_size=512}};
  kfio_bio_t *f=kfio_convert_bio(&q,&b); assert(f); kfio_bio_submit(f);
  assert(b.completions==1 && b.bi_status==(fail_stage?-EIO:0));
  assert(frees==alloc_count && maps==1 && unmaps==1);
 }
 for(int allocation=2;allocation<=3;allocation++) {
  reset();alloc_fail_at=allocation;
  struct bio b={.bi_opf=REQ_OP_WRITE|REQ_PREFLUSH|REQ_FUA,.bi_iter={.bi_size=512}};
  assert(!kfio_convert_bio(&q,&b));
  assert(b.completions==0 && frees==alloc_count-1 && maps==1 && unmaps==1);
 }
 reset();ctx_fail=1;
 struct bio b={.bi_opf=REQ_OP_WRITE|REQ_FUA,.bi_iter={.bi_size=512}};
 assert(!kfio_convert_bio(&q,&b)); assert(frees==alloc_count && maps==1 && unmaps==1);
 reset();
 struct bio one={.bi_opf=REQ_OP_WRITE,.bi_iter={.bi_size=512}};
 struct bio two={.bi_opf=REQ_OP_WRITE,.bi_iter={.bi_size=512,.bi_sector=1}};
 kfio_bio_t *f=kfio_map_to_fbio(&q,&one); assert(f);
 two.bi_opf|=REQ_FUA; assert(kfio_kbio_add_bio(f,&two,4096)==1);
 two.bi_opf=REQ_OP_WRITE|REQ_SYNC; assert(kfio_kbio_add_bio(f,&two,4096)==1);
 two.bi_opf=REQ_OP_WRITE; assert(kfio_kbio_add_bio(f,&two,4096)==0);
 one.bi_next=&two; dma_fail=1; kfio_fbio_map_submit(f);
 assert(one.completions==1 && two.completions==1 && one.bi_status==-EIO && two.bi_status==-EIO);
 assert(submits==0 && frees==alloc_count);
 return 0;
}
''')


LIFECYCLE_PREFIX = r'''
#include <assert.h>
#include <errno.h>
#include <stdbool.h>
#include <stdint.h>
#include <stddef.h>
#include <stdlib.h>
#include <stdio.h>
#include <string.h>
#include <limits.h>
#define KERNEL_SECTOR_SIZE 512U
#define SECTOR_SHIFT 9
#define USE_QUEUE_NONE 0
#define USE_QUEUE_RQ 3
#define NUMA_NO_NODE -1
#define KFIOC_X_HAS_MAKE_REQUEST_FN 0
#define KFIOC_X_BLK_ALLOC_DISK_EXISTS 1
#define KFIOC_X_BLK_ALLOC_DISK_HAS_QUEUE_LIMITS 0
#define KFIO_DISABLE_GENHD_FL_EXT_DEVT 1
#define FIO_NUM_MINORS 16
#define QUEUE_FLAG_DYING 3
#define BLK_FEAT_WRITE_CACHE (1U<<0)
#define BLK_FEAT_ROTATIONAL (1U<<2)
#define BLK_FEAT_ADD_RANDOM (1U<<3)
#define SET_QUEUE_FLAG_DISCARD ((void)0)
#define PAGE_SIZE 4096U
#define round_down(x,y) ((x)&~((y)-1))
#define IS_ERR(p) ((uintptr_t)(p)>=(uintptr_t)-4095)
#define IS_ERR_OR_NULL(p) (!(p)||IS_ERR(p))
#define ERR_PTR(e) ((void *)(intptr_t)(e))
#define PTR_ERR(p) ((int)(intptr_t)(p))
#define atomic_set(p,n) (*(p)=(n))
#define INIT_LIST_HEAD(p) (*(p)=0)
#define fusion_atomic_list_init(p) (*(p)=0)
#define fusion_condvar_init(p,n) (*(p)=0)
#define fusion_cv_lock_init(p,n) (*(p)=0)
#define fusion_condvar_destroy(p) ((void)0)
#define fusion_cv_lock_destroy(p) ((void)0)
#define fusion_cv_lock_irq(p) ((void)0)
#define fusion_cv_unlock_irq(p) ((void)0)
#define fusion_condvar_broadcast(p) ((void)0)
#define fusion_condvar_wait(p,l) abort()
#define container_of(p,t,m) ((t *)((char *)(p)-offsetof(t,m)))
#define THIS_MODULE ((void *)1)
#define infprint(...) ((void)0)
#define destroy_type_normal 0
#define BI_SIZE(b) ((b)->size)
typedef int kfio_numa_node_t;
typedef int kfio_pci_dev_t;
typedef int fusion_spinlock_t;
typedef int destroy_type_t;
struct fio_device {int unused;};
struct bio {struct bio *bi_next; unsigned size; int completions;};
struct request_queue {void *queuedata; unsigned queue_lock; unsigned long queue_flags;
 struct {unsigned io_min,io_opt,max_hw_sectors,max_segments,max_segment_size,logical_block_size,physical_block_size,max_sectors,max_discard_sectors,discard_granularity,features;} limits;};
struct block_device_operations {void *owner;};
struct gendisk {struct request_queue *queue;int major,first_minor,minors,flags;struct block_device_operations *fops;void *private_data;char disk_name[32];uint64_t capacity;};
struct kfio_disk {struct fio_device *dev;struct gendisk *gd;struct request_queue *rq;kfio_pci_dev_t *pdev;fusion_spinlock_t *queue_lock;int last_dispatch_rw;uint32_t sector_mask,maxiosize;int state_cv,state_lk,comp_list,lock_pending,retry_list;bool registered;struct bio *bio_head,*bio_tail;};
typedef struct kfio_disk kfio_disk_t;
struct fusion_work_struct {void (*fn)(struct fusion_work_struct *);};
typedef struct fusion_work_struct fusion_work_struct_t;
static int use_workqueue, enable_discard, fio_dev_optimal_blk_size=4096;
static int allocations,frees,disk_puts,deletes,lock_depth,add_error,add_calls;
static struct gendisk *disk_result;
static struct block_device_operations fio_bdev_ops;
static void *kfio_malloc_node(size_t n,int node) {allocations++;return calloc(1,n);}
static void kfio_free(void *p,size_t n) {frees++;free(p);}
static struct gendisk *alloc_disk_result(void) {return disk_result;}
#define BLK_ALLOC_DISK alloc_disk_result();
#define BLK_ALLOC_QUEUE dp->gd->queue;
static void test_safe_plugging(void) {}
static void set_capacity(struct gendisk *g,uint64_t size) {assert(!IS_ERR_OR_NULL(g));g->capacity=size;}
static void del_gendisk(struct gendisk *g) {assert(!IS_ERR_OR_NULL(g));deletes++;}
static void put_disk(struct gendisk *g) {assert(!IS_ERR_OR_NULL(g));disk_puts++;}
static void set_bit(unsigned bit,unsigned long *flags) {*flags|=1UL<<bit;}
#define spin_lock_irqsave(l,f) do {(f)=1; assert(!lock_depth);lock_depth++;} while(0)
#define spin_unlock_irqrestore(l,f) do {assert((f)==1 && lock_depth==1);lock_depth--;} while(0)
static void __kfio_bio_complete(struct bio *b,uint32_t bytes,int error) {assert(!lock_depth);assert(error==-EIO);b->completions++;}
static const char *fio_device_get_bus_name(struct fio_device *d) {return "test";}
static void fusion_init_work(fusion_work_struct_t *w,void (*fn)(fusion_work_struct_t *)) {w->fn=fn;}
static void fusion_schedule_work(fusion_work_struct_t *w) {w->fn(w);}
static void fusion_destroy_work(fusion_work_struct_t *w) {}
#if KFIOC_X_VOID_ADD_DISK
static void add_disk(struct gendisk *g) {add_calls++;}
#else
static int add_disk(struct gendisk *g) {add_calls++;return add_error;}
#endif
static struct request_queue *kfio_alloc_queue(struct kfio_disk *,kfio_numa_node_t);
void kfio_destroy_disk(kfio_disk_t *,destroy_type_t);
'''


class LifecycleContracts(unittest.TestCase):
    def test_allocation_lock_and_publication_ownership(self):
        source = (SRC / "kblock.c").read_text()
        meta = (SRC / "include/kblock_meta.h").read_text()
        param = source[source.index("struct kfio_blk_add_disk_param\n{"):source.index("/*\n * @brief Run add-disk")]
        funcs = "\n".join(function(source,n) for n in ["kfio_alloc_queue", "kfio_create_disk", "kfio_blk_add_disk", "kfio_expose_disk", "kfio_destroy_disk"])
        for void_api in (0,1):
            with self.subTest(void_api=void_api):
                run_c(self, f"#define KFIOC_X_VOID_ADD_DISK {void_api}\n" + LIFECYCLE_PREFIX + function(meta,"kfio_add_disk") + param + funcs + r'''
int main(void) {
 struct request_queue q={.limits={.max_sectors=1024}};
 struct gendisk gd={.queue=&q}; struct fio_device dev={0}; fusion_spinlock_t lock=5;
 struct kfio_disk *d=NULL;
 use_workqueue=3;
 assert(kfio_create_disk(&dev,NULL,512,128,128,&lock,&d,0)==-EINVAL && !d && !allocations);
 use_workqueue=0;
 disk_result=NULL;
 assert(kfio_create_disk(&dev,NULL,512,128,128,&lock,&d,0)==-ENOMEM && !d && frees==1 && !disk_puts);
 disk_result=ERR_PTR(-EIO);
 assert(kfio_create_disk(&dev,NULL,512,128,128,&lock,&d,0)==-EIO && !d && frees==2 && !disk_puts);
 disk_result=&gd; gd.queue=NULL;
 assert(kfio_create_disk(&dev,NULL,512,128,128,&lock,&d,0)==-ENOMEM && !d && frees==3 && disk_puts==1 && !deletes);
 gd.queue=ERR_PTR(-EIO);
 assert(kfio_create_disk(&dev,NULL,512,128,128,&lock,&d,0)==-EIO && !d && frees==4 && disk_puts==2 && !deletes);
 gd.queue=&q;
 assert(kfio_create_disk(&dev,NULL,512,128,128,&lock,&d,0)==0 && d && d->queue_lock==&lock);
 assert(q.queuedata==d && (q.limits.features&BLK_FEAT_WRITE_CACHE) && !d->registered);
#if !KFIOC_X_VOID_ADD_DISK
 add_error=-EIO;
 assert(kfio_expose_disk(d,"fio",1,0,100,512,128)==-EIO && !d->registered);
 kfio_destroy_disk(d,destroy_type_normal); assert(!deletes && disk_puts==3);
 assert(kfio_create_disk(&dev,NULL,512,128,128,&lock,&d,0)==0);
#endif
 add_error=0;
 assert(kfio_expose_disk(d,"abcdefghijklmnopqrstuvwxyz0123456789",1,0,100,512,128)==0 && d->registered);
 assert(gd.disk_name[31]==0);
 struct bio a={.size=512},b={.size=512};a.bi_next=&b;d->bio_head=&a;d->bio_tail=&b;
 kfio_destroy_disk(d,destroy_type_normal);
 assert(a.completions==1 && b.completions==1 && !a.bi_next && !b.bi_next && !lock_depth);
 assert(deletes==1 && allocations==frees);
 return 0;
}
''')



class MetadataContracts(unittest.TestCase):
    def test_host_only_allocation_provenance(self):
        source = (SRC / "kscatter.c").read_text()
        names = ["kfio_sgl_alloc_nvec", "kfio_sgl_dma_unmap", "kfio_sgl_destroy", "kfio_dma_map_alloc", "kfio_dma_map_free"]
        run_c(self, SG_PREFIX + r'''
#define GFP_NOIO 1
#define GFP_ATOMIC 2
#define MAX_NUMNODES 4
#define NUMA_NO_NODE -1
#define node_online(n) ((n)==0 || (n)==1)
typedef struct pci_dev kfio_pci_dev_t;
typedef int kfio_numa_node_t;
static int allocation_node, allocation_flags, allocations, releases;
static void *kzalloc_node(size_t size,int flags,int node) {
 allocation_node=node; allocation_flags=flags;
 if(size>1024*1024) return NULL;
 allocations++;return calloc(1,size);
}
static void kfree(void *p) {if(p) {releases++;free(p);}}
static void sg_init_table(struct scatterlist *p,int n) {memset(p,0,n*sizeof(*p));}
''' + "\n".join(function(source,n) for n in names) + r'''
int main(void) {
 struct pci_dev pci={0}; kfio_sg_list_t *s=(void *)1;
 assert(kfio_sgl_alloc_nvec(&pci,0,&s,0)==-EINVAL && !s && !allocations);
 assert(kfio_sgl_alloc_nvec(&pci,0,&s,-1)==-EINVAL && !s);
 assert(kfio_sgl_alloc_nvec(&pci,1,&s,8)==0 && s && allocation_node==1 && allocation_flags==GFP_NOIO);
 assert(s->num_entries==0 && s->num_mapped==0 && s->max_entries==8);
 kfio_sgl_destroy(s); assert(allocations==releases);
 assert(kfio_sgl_alloc_nvec(&pci,3,&s,8)==0 && allocation_node==NUMA_NO_NODE);
 kfio_sgl_destroy(s);
 kfio_dma_map_t *m=kfio_dma_map_alloc(0,1); assert(m && allocation_flags==GFP_ATOMIC && allocation_node==1 && !m->sge_first && !m->map_length);
 kfio_dma_map_free(m);
 m=kfio_dma_map_alloc(1,MAX_NUMNODES); assert(m && allocation_flags==GFP_NOIO && allocation_node==NUMA_NO_NODE);
 kfio_dma_map_free(m);kfio_dma_map_free(NULL);
 assert(allocations==releases);
 return 0;
}
''')

if __name__ == "__main__":
    unittest.main()
