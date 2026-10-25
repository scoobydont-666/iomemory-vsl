"""Offline contract and userspace mock-kernel tests for NUMA1/DMA32 pci.c and kmem.c fixes.

Run: python3 -m unittest discover -s tests -p 'test_*.py' -v
"""
from pathlib import Path
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
SRC_DIR = ROOT / "root/usr/src/iomemory-vsl-3.2.16"


HARNESS_C = r'''
#include <assert.h>
#include <errno.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

typedef uint8_t u8;
typedef uint16_t u16;
typedef uint32_t u32;
typedef uint64_t u64;
typedef uint64_t dma_addr_t;
typedef uint32_t gfp_t;
typedef size_t fio_size_t;
typedef uintptr_t fio_uintptr_t;
typedef int kfio_numa_node_t;
typedef void *fusion_page_t;
typedef void *fusion_user_page_t;
typedef uint32_t kfio_maa_t;
typedef int irqreturn_t;

#define noinline __attribute__((noinline))
#define __acquires(x)
#define __releases(x)
#define unlikely(x) (x)
#define C_ASSERT(x) _Static_assert(x, #x)
#define KFIO_EXPORT_SYMBOL(x)
#define FUSION_ALLOCATION_TRIPWIRE_TEST() do {} while (0)
#define FUSION_PAGE_SHIFT 12
#define FUSION_PAGE_SIZE (1UL << FUSION_PAGE_SHIFT)
#define MAX_PAGE_ORDER 10U

#define GFP_KERNEL 0x01u
#define GFP_NOIO   0x02u
#define GFP_NOWAIT 0x04u
#define __GFP_DMA32  0x10u
#define __GFP_ZERO   0x20u
#define __GFP_NOWARN 0x40u

#define DMA_BIT_MASK(n) (((n) == 64) ? ~0ULL : ((1ULL << (n)) - 1ULL))

struct device {
    int numa_node;
    u64 dma_mask;
    u64 coherent_dma_mask;
};

struct pci_dev {
    struct device dev;
    char name[32];
};

typedef struct pci_dev kfio_pci_dev_t;

struct fusion_dma_t {
    uint64_t phys_addr;
    uint64_t _private[96 / sizeof(uint64_t)];
};

struct page {
    void *vaddr;
    unsigned int order;
    int node;
    gfp_t gfp;
    int in_use;
};

static int g_mock_mask_rc = 0;
static dma_addr_t g_mock_next_dma_addr = 0x10000000ULL;
static int g_mock_fail_node_gt0 = 0;
static int g_last_coherent_alloc_node = -1;
static gfp_t g_last_coherent_gfp = 0;
static int g_coherent_free_count = 0;
static int g_pages_in_use = 0;
static int g_last_page_node = -1;

#define errprint(fmt, ...) fprintf(stderr, fmt, ##__VA_ARGS__)

static const char *pci_name(const struct pci_dev *pdev)
{
    return pdev ? pdev->name : "mock_pci";
}

static int dev_to_node(struct device *dev)
{
    return dev->numa_node;
}

static void set_dev_node(struct device *dev, int node)
{
    dev->numa_node = node;
}

static int node_online(int node)
{
    return node == 0 || node == 1;
}

static int dma_set_mask_and_coherent(struct device *dev, u64 mask)
{
    if (g_mock_mask_rc != 0)
        return g_mock_mask_rc;
    dev->dma_mask = mask;
    dev->coherent_dma_mask = mask;
    return 0;
}

static void *dma_alloc_coherent(struct device *dev, size_t size,
                                dma_addr_t *dma_handle, gfp_t gfp)
{
    void *buf = NULL;
    g_last_coherent_alloc_node = dev->numa_node;
    g_last_coherent_gfp = gfp;
    if (posix_memalign(&buf, FUSION_PAGE_SIZE, size) != 0)
        return NULL;
    memset(buf, 0, size);
    *dma_handle = g_mock_next_dma_addr;
    return buf;
}

static void dma_free_coherent(struct device *dev, size_t size,
                              void *cpu_addr, dma_addr_t dma_handle)
{
    (void)dev;
    (void)size;
    (void)dma_handle;
    free(cpu_addr);
    g_coherent_free_count++;
}

static unsigned int get_order(size_t size)
{
    unsigned int order = 0;
    size_t bytes = FUSION_PAGE_SIZE;
    while (bytes < size && order < 32) {
        bytes <<= 1;
        order++;
    }
    return order;
}

#define MAX_TRACKED_PAGES 64
static struct page g_page_table[MAX_TRACKED_PAGES];

static struct page *alloc_pages_node(int nid, gfp_t gfp_mask, unsigned int order)
{
    if (g_mock_fail_node_gt0 && nid > 0)
        return NULL;
    if (order >= MAX_PAGE_ORDER)
        return NULL;
    for (int i = 0; i < MAX_TRACKED_PAGES; i++) {
        if (!g_page_table[i].in_use) {
            size_t bytes = FUSION_PAGE_SIZE << order;
            void *mem = NULL;
            if (posix_memalign(&mem, FUSION_PAGE_SIZE, bytes) != 0)
                return NULL;
            if (gfp_mask & __GFP_ZERO)
                memset(mem, 0, bytes);
            g_page_table[i].vaddr = mem;
            g_page_table[i].order = order;
            g_page_table[i].node = nid;
            g_page_table[i].gfp = gfp_mask;
            g_page_table[i].in_use = 1;
            g_pages_in_use++;
            g_last_page_node = nid;
            return &g_page_table[i];
        }
    }
    return NULL;
}

static void *page_address(const struct page *pg)
{
    return pg ? pg->vaddr : NULL;
}

static struct page *virt_to_page(const void *addr)
{
    for (int i = 0; i < MAX_TRACKED_PAGES; i++) {
        if (g_page_table[i].in_use && g_page_table[i].vaddr == addr)
            return &g_page_table[i];
    }
    assert(0 && "virt_to_page called on unknown base address");
    return NULL;
}

static void __free_pages(struct page *pg, unsigned int order)
{
    assert(pg != NULL);
    assert(pg->in_use == 1);
    assert(pg->order == order);
    free(pg->vaddr);
    pg->vaddr = NULL;
    pg->in_use = 0;
    g_pages_in_use--;
}

/* Include exact functions under test via extracted definitions */
#include "extracted_units.inc"

int main(void)
{
    struct pci_dev pdev;
    struct fusion_dma_t dma_hdl;
    void *v;
    int rc;

    memset(&pdev, 0, sizeof(pdev));
    snprintf(pdev.name, sizeof(pdev.name), "0000:81:00.0");
    pdev.dev.numa_node = 1;

    /* 1. kfio_pci_set_dma_mask clamps 64-bit mask to 32-bit and propagates errors */
    rc = kfio_pci_set_dma_mask(&pdev, ~0ULL);
    assert(rc == 0);
    assert(pdev.dev.dma_mask == DMA_BIT_MASK(32));
    assert(pdev.dev.coherent_dma_mask == DMA_BIT_MASK(32));

    rc = kfio_pci_set_dma_mask(&pdev, DMA_BIT_MASK(28));
    assert(rc == 0);
    assert(pdev.dev.dma_mask == DMA_BIT_MASK(28));

    g_mock_mask_rc = -EIO;
    rc = kfio_pci_set_dma_mask(&pdev, DMA_BIT_MASK(32));
    assert(rc == -EIO);
    g_mock_mask_rc = 0;

    /* 2. kfio_dma_alloc_coherent uses dma_alloc_coherent, routes node 1 -> node 0, restores node 1 */
    g_mock_next_dma_addr = 0x7ff00000ULL;
    v = kfio_dma_alloc_coherent(&pdev, 0x100000U, &dma_hdl);
    assert(v != NULL);
    assert(g_last_coherent_alloc_node == 0);
    assert(pdev.dev.numa_node == 1);
    assert((g_last_coherent_gfp & __GFP_DMA32) != 0);
    assert(dma_hdl.phys_addr == 0x7ff00000ULL);
    kfio_dma_free_coherent(&pdev, 0x100000U, v, &dma_hdl);
    assert(g_coherent_free_count == 1);
    assert(dma_hdl.phys_addr == 0);

    /* 3. kfio_dma_alloc_coherent fails closed and frees if dma_addr + size - 1 > 4 GiB */
    g_mock_next_dma_addr = 0xfff80000ULL; /* + 1 MiB crosses 4 GiB */
    v = kfio_dma_alloc_coherent(&pdev, 0x100000U, &dma_hdl);
    assert(v == NULL);
    assert(g_coherent_free_count == 2);

    /* 4. __kfio_malloc / kfio_free bounds, 16B alignment, and NUMA1 fallback */
    assert(kfio_malloc(0) == NULL);
    assert(kfio_malloc(~(fio_size_t)0) == NULL);
    assert(kfio_malloc(KFIO_DMA32_MAX_BYTES + 1) == NULL);

    g_mock_fail_node_gt0 = 1;
    void *p = kfio_malloc_node(131072, 1);
    assert(p != NULL);
    assert(((uintptr_t)p & 0xFUL) == 0); /* 16-byte aligned */
    assert(g_last_page_node == 0);       /* fell back from node 1 to node 0 */
    assert(g_pages_in_use == 1);
    kfio_free(p, 131072);
    assert(g_pages_in_use == 0);

    printf("ALL_ASSERTS_PASSED\n");
    return 0;
}
'''


class Dma32AndKmemContractTests(unittest.TestCase):
    def test_pci_coherent_dma_api_contract(self):
        pci_text = (SRC_DIR / "pci.c").read_text()
        self.assertIn("dma_alloc_coherent(", pci_text)
        self.assertIn("dma_free_coherent(", pci_text)
        self.assertIn("dma_set_mask_and_coherent(", pci_text)
        self.assertNotIn("dma_map_page(", pci_text)
        self.assertNotIn("dma_unmap_page(", pci_text)

    def test_userspace_harness_executes_pci_and_kmem_invariants(self):
        pci_lines = (SRC_DIR / "pci.c").read_text().splitlines()
        kmem_lines = (SRC_DIR / "kmem.c").read_text().splitlines()

        pci_start = next(
            i
            for i, l in enumerate(pci_lines)
            if l.startswith("int kfio_pci_set_dma_mask(") and not l.endswith(";")
        )
        pci_mask_end = next(
            i
            for i, l in enumerate(pci_lines)
            if l.startswith("void kfio_pci_set_master(") and not l.endswith(";")
        )
        dma_alloc_start = next(
            i
            for i, l in enumerate(pci_lines)
            if l.startswith("void noinline *kfio_dma_alloc_coherent(")
        )
        pci_end = next(
            i for i, l in enumerate(pci_lines) if l.startswith("int kfio_dma_sync(")
        )
        kmem_start = next(
            i for i, l in enumerate(kmem_lines) if l.startswith("#define KFIO_DMA32_HDR_MAGIC")
        )
        kmem_end = next(
            i for i, l in enumerate(kmem_lines) if l.startswith("void *noinline kfio_vmalloc(")
        )

        extracted = "\n".join(
            pci_lines[pci_start:pci_mask_end]
            + [""]
            + pci_lines[dma_alloc_start:pci_end]
            + [""]
            + kmem_lines[kmem_start:kmem_end]
        )

        with tempfile.TemporaryDirectory(prefix="iomemory-dma32-test-") as tmp:
            tmp_path = Path(tmp)
            (tmp_path / "extracted_units.inc").write_text(extracted)
            (tmp_path / "harness.c").write_text(HARNESS_C)
            bin_path = tmp_path / "harness"
            subprocess.run(
                ["cc", "-std=gnu11", "-Wall", "-Wextra", "-Werror", "-O2", str(tmp_path / "harness.c"), "-o", str(bin_path)],
                check=True,
            )
            res = subprocess.run([str(bin_path)], check=True, capture_output=True, text=True)
            self.assertIn("ALL_ASSERTS_PASSED", res.stdout)


if __name__ == "__main__":
    unittest.main()
