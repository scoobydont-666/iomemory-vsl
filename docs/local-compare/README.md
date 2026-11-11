# Local comparison snapshot: loaded build vs main (13145f4)

Branch: `local/loaded-build-compare-20261111`. Base: `13145f4abf6caa575c1dcb149925bef7a90e7f1f`
(= `origin/main` of scoobydont-666/iomemory-vsl, read from a fresh clone on 2026-11-11).
Host references below use `REDACTED-HOST`. All "measured" values come from read-only commands on that host
on 2026-11-11 (UTC, ~18:35-19:30Z). "Derived" means inferred from commit messages or code, not from a run.

## 1. Relationship to main

**Answer: the driver tree is the same as main. The loaded module is not built from main.**

- Host repo HEAD (detached) = `13145f4...`, `git status --porcelain` shows 0 tracked modifications. Equal commit hash
  means equal tracked content. Measured.
- This branch = main at 13145f4 plus one commit that adds the files listed in section 7 (`load-fio-driver.sh`,
  `docs/local-compare/**`). No file under `root/` or `Makefile` is changed by this branch.
- Host DKMS source `/usr/src/iomemory-vsl-1794116140.13145f4abf6c` vs repo `root/usr/src/iomemory-vsl-3.2.16/` at
  13145f4 (sha256 of every file, measured):
  - 125 files byte-identical.
  - `dkms.conf` differs: repo `PACKAGE_VERSION=3.2.16.2`, host `PACKAGE_VERSION=1794116140.13145f4abf6c`
    (the DKMS-stamped version). Otherwise identical. Copy kept at `installed-dkms/dkms.conf.installed`.
  - Host-only file `.dkms-source-revision` (content `13145f4abf6caa575c1dcb149925bef7a90e7f1f`). Kept at
    `installed-dkms/dkms-source-revision`.
  - Repo files missing on host: none.
- **Loaded module is NOT the 13145f4 build** (measured):
  - `/sys/module/iomemory_vsl/srcversion` = `A707FCA26416451F13ADC03`; `/sys/module/iomemory_vsl/version` = `6.17.0-40-ca4c075-3.2.16`.
  - DKMS-installed module for 13145f4 (`/lib/modules/7.0.0-28-generic/updates/dkms/iomemory-vsl.ko.zst`):
    srcversion `279D601848406282AAECD69`, version `1794116140.13145f4abf6c`.
  - Untracked repo-root build `root/usr/src/iomemory-vsl-3.2.16/iomemory-vsl.ko` (mtime 2026-11-08 14:02): srcversion
    `35B7CB4F0D266A4502E28CE`, version `7.0.0-28-13145f4-3.2.16`.
  - A worktree build `.ko` at `fio-k7` (mtime 2026-08-05 05:32): srcversion `A707FCA26416451F13ADC03`, version
    `6.17.0-40-ca4c075-3.2.16`. **This matches the loaded module.**
  - The loaded module has no `dma32_clamp` parameter in sysfs. That parameter is added by 13145f4 (`feat(task-143775)`).
  - `load-fio-driver.sh` (section 7) insmods the repo-root `.ko` (srcversion 35B7...), which is not the module that
    is currently loaded.
- Commit `ca4c075` (author "Hermes CLI (pane:1)", 2026-08-05, subject `fix(task-15303): run objtool per-file so kernel 7.x modules boot`)
  is the source revision in the loaded module's version string. It exists only in the host's reflog (no ref, no remote).
  Its `git show | git patch-id --stable` = `500efa3d32c0165a433a31136e1d7ae8daeae28b`, the same as main's `eb33cb2`.
  So the loaded build's objtool change is the same diff as main's `eb33cb2`. The rest of its tree is not the same as
  13145f4: `pci.c` sha256 `03ef4e0b...` vs main `d67bb724...`; `kmem.c` sha256 `3fa693c6...` vs main `045c22b0...`
  (measured on both sides, same content hashed with `git show <rev>:<path> | sha256sum`).

### How to reconstruct the source of the loaded module

The loaded module's version string names commit `ca4c075`. That commit is not on any GitHub branch, so it is provided
as a patch rather than pushed (its author metadata is redacted). To obtain the exact tree:

1. Check out `d171d8b` (the parent of `ca4c075`; it is in the history of the GitHub branch `feat/numa1-dma32-on-k7`).
2. Apply `docs/local-compare/patches/reflog-only-task15303-objtool/0001-ca4c075.patch`.

The GitHub branch `feat/numa1-dma32-on-k7` (tip `ec10ef2`) differs from that tree only in
`root/usr/src/iomemory-vsl-3.2.16/objtool_wrapper` (38 insertions, 2 deletions, measured with `git diff --stat ca4c075 ec10ef2`).
Commit-message trailers naming tooling were removed from the exported patches; the diffs are unchanged.

### Upstream relationship (measured)

- RemixVSL/iomemory-vsl `main` = `843024a41898f7315cb1dbef37250f5a09aef061` (fetched to `refs/review/remixvsl-main`).
- Fork point: `982f7164f97c40e13cc637cfcf9624c7f3ce8dfa` (`Merge pull request #156`, 2026-05-21), the merge-base of
  13145f4 and upstream main.
- Fork-only commits (`982f716..13145f4`), in order:
  `cf8f3d8`, `6cd7867`, `eb33cb2`, `dd0c13b`, `4cd8647`, `8d798ba`, `3d2b32a` (merge of PR #4), `13145f4`.
- Upstream commits not in the fork: 6 (`6b6b150`, `92fc6f9`, `83b110d`, `363db6f`, `e11293b`, `843024a`).
- Host-local tags `v4.20.0`-`v4.20.4`, `v5.6.0`, `v5.10.0`, `v5.12.0`, `v5.12.1` are on the host only in the local
  object store. RemixVSL publishes 9 tags matching `v4.20`/`v5.` (count matched; names not compared one by one).
  Their history (for example `e384cd2`, `df066e4`) is not an ancestor of upstream main. They are not fork changes.

## 2. Local changes relative to upstream (derived from commit messages and code)

Lines below are derived from the commit messages in the fork (public history).

- `cf8f3d8` dkms: stage committed source, kernel-independent version, DKMS metadata generated without git, keep existing
  installs on failure, avoid remove-all/force-install. Adds `DKMS.md`, `.github/workflows/dkms.yml`, `tests/test_dkms.py`,
  `docs/upstream/*`.
- `6cd7867` NUMA/DMA32 attach fix (task-10911): force 32-bit DMA mask and DMA32 coherent rings in `pci.c`; `kmem.c`
  allocates EB-scan buffers with `alloc_pages_node(... | __GFP_DMA32)` so NUMA1 ioScale2 cards (DMA32 zone only on node 0)
  can attach. Reason stated: `fio-attach` returned EINVAL on 6.17 when coherent rings landed above 4 GB.
- `eb33cb2` objtool per-file pass on kernel >= 7 (`objtool_perfile` target in `Makefile`). Reason: kernel 7.x runs objtool
  once on the linked module, and the proprietary libkfio blob aborts that pass, so jump-label sites are not converted and
  boot panics in `jump_label_init`.
- `dd0c13b` `objtool_wrapper` no longer ends in `exit 0`. Tolerates only `unannotated intra-function call` from the libkfio
  blob; any other objtool error is fatal (derived from the wrapper diff and the commit message).
- `4cd8647` per-file objtool only for kernel >= 7 (kernels <= 6.x already run objtool per object); per-file loop no
  longer ignores status. Reason: relink failure in dkms CI on 6.8.0-149.
- `8d798ba` untrack `root/usr/src/iomemory-vsl-3.2.16/check_target_kernel.conf` (rewritten at every build; dirtied the tree).
- `13145f4` `dma32_clamp` module parameter, default 1 (keeps the NUMA1 fix). 0 uses the hardware 64-bit mask. Reason
  given: with `iommu=pt` the clamp sent all I/O through swiotlb bounce buffers and soft-locked a CPU on first write.
- Build-time change not in a commit: `Makefile:118` runs `sed -i 's/Proprietary/GPL/g' Kbuild` (measured in build log).


## 3. Core objects and libraries

### 3a. libkfio objects in the tree at 13145f4 (measured, sha256 of `root/usr/src/iomemory-vsl-3.2.16/kfio/`)

| file | bytes | sha256 |
|---|---|---|
| `x86_64_cc41_libkfio.o_shipped` | 1542872 | bcdf34e10dd812388e013a356485f0094480ea4ad6c2fb2d1460ba38dc86e18a |
| `x86_64_cc43_libkfio.o_shipped` | 1597416 | a2ceeb4892c6d68675d45beb7dab291ce3dfb7d1c30ed9473e5aef9297f0e3c3 |
| `x86_64_cc44_libkfio.o_shipped` | 1580312 | 49d53a0112b0f9421e922d69672935bbd476bca90175a0e6be7c9d3ebe87c3ed |
| `x86_64_cc48_libkfio.o_shipped` | 1592592 | b8a7e8416f931aa4c905e553ed9a062f84b19eeb13d19e266cc5c72e02289258 |
| `x86_64_cc49_libkfio.o_shipped` | 1588536 | 63c7a2fe12a7156624b5b730b1c124ddf16e8efb765e96ac885a98fe7df3ec0c |
| `x86_64_cc53_libkfio.o_shipped` | 1634944 | f9360d63fc096a8da7648e25c57267aed2a7f4cfbd7cb377a37d9e0e463bff36 |
| `x86_64_cc54_libkfio.o_shipped` | 1636464 | 4af71450b1ee0dccedde98f1f35e435ebed1ab9ccf1c944807184257f4c99bab |
| `x86_64_cc63_libkfio.o_shipped` | 1611544 | 61ee1425207b317c9c327c7c9080ab201fdd01625a6138d893abd63d42021a4d |
| `x86_64_latest_libkfio.o_shipped` | 1611544 | 61ee1425207b317c9c327c7c9080ab201fdd01625a6138d893abd63d42021a4d |

`cc63` and `latest` are the same bytes.

### 3b. Which object this build selects (derived from Makefile + measured build log)

- `Makefile:58` `TARGET ?= $(FIOARCH)_cc$(CCMAJOR)$(CCMINOR)`; host gcc 13.3 gives `x86_64_cc133`.
- `Makefile:60-62`: `KFIO_LIB = kfio/x86_64_cc133_libkfio.o`, `LAST_KFIO_LIB = x86_64_latest_libkfio.o_shipped`.
- `Makefile:122-123` copies `latest_libkfio.o_shipped` to the `cc133` name when that file is absent. Build log lines 10-11 show this copy.
- No `x86_64_cc133` shipped object exists in the tree. The object built is therefore **`x86_64_latest_libkfio.o_shipped`
  (sha256 61ee1425...)**. Host copy `kfio/x86_64_cc133_libkfio.o` (in the source tree, untracked) has the same sha256.
- Host backups (untracked, not built): `kfio/x86_64_latest_libkfio.o_shipped.orig` = 61ee1425... (same);
  `kfio/x86_64_latest_libkfio.o_shipped.pre_midprom_patch` sha256 `12fdca4208904bd7313e648d5a412c8caf4678f1de1d49e745e1606278225ccd`
  (differs; not in repo; not used by the build).

### 3c. libvsl.so

- Exists in the repo: `root/usr/lib/fio/libvsl.so`, 1056336 bytes, sha256 `0a57f8e2090841019c7e2cf1a6b5bb5ca61ba5a89be6c7cdac5236d68e7ee14d`.
- Host `/usr/lib/fio/libvsl.so`: same sha256 (measured). Owned by no package (`dpkg -S`: no path found). Also present in the
  host's `fio-k7` worktree (same size 1056336; hash not taken).
- Replacing source: **none found.** `git grep -i libvsl` at 13145f4 only hits packaging files (`DKMS.md`, `debian/*`,
  `fio-driver.spec`, `module_operations.sh`, `dkms-install.sh`, `tests/test_dkms.py`). No `.c`/`.h` builds `libvsl.so`.
- `libkfio` is linked into the module, not into `libvsl.so` (`Kbuild:47`).

## 4. License and release evidence (quoted, not interpreted)

Files in the repo (sha256):

- `root/usr/share/doc/iomemory-vsl/License` `9e7915915dce0456ef9ba8920defd3736856ce92d7a7ea02157122e74028ea38`
  first line: `END-USER LICENSE AGREEMENT (9.15.14)`; party named: `Fusion-io, Inc., a wholly-owned subsidiary of SanDisk Corporation`.
- `root/usr/share/doc/iomemory-vsl/NOTICE.iomemory-vsl` `8fc37945f0c5b95fe5dc6de5765f8297a3b8f9b95ad0e157eced41b4e0c6a113`
  first lines: `Fusion-io driver, utilities, and vsl library` / `Copyright (c) 2010-2014 Fusion-io, Inc.  (acquired by SanDisk Corp. 2014)`.
- `root/usr/share/doc/fio/NOTICE.libvsl` `fdaeac4ecc9339ef32a2f718cef6f142d9037c51770a88afdc3514a816b36020`
  first lines: `SanDisk Fusion driver, utilities, and vsl library` / `Copyright (c) 2010-2017 Western Digital Corporation or its affiliates.`
- Both NOTICE files say: "For a copy of source code for libraries that we distribute under the GNU Lesser General Public
  License (LGPL) or GNU GENERAL PUBLIC LICENSE VERSION 2, please send a request to SanDisk Corp."
- File-name search at 13145f4 for `LICENSE|COPYING|NOTICE` returns only the three files above. `SPDX-License` appears in 0 files. The EULA section 4 says: "If the Open Source Software
  licenses include a license that provides for the availability of source code (e.g., the GNU General Public License) and
  the corresponding source code is not included with the Product, check Fusion-io's product support pages..."
- Declared module license: `modinfo`: `license: GPL`. Source of it: `Kbuild:11-12` generates `license.c` containing
  `MODULE_LICENSE("GPL")`. `.gitignore` ignores `**/license.c`, so the file is not tracked. Build also rewrites
  `Kbuild` with `sed -i 's/Proprietary/GPL/g'` (`Makefile:118`).
- First-party `.c`/`.h` headers: 102 of them carry `Copyright (c) ... Fusion-io, Inc. / SanDisk / Western Digital` headers with
  BSD-style redistribution text (e.g. `pci.c`: "Redistribution and use in source and binary forms, with or without
  modification, are permitted provided that the following conditions are met"). None has an SPDX tag. Only one file
  contains `MODULE_LICENSE` in source: none. `root/usr/src/.../main.c:245` says "MODULE_LICENSE is found in license.c - which is auto-generated".
- Shipped objects: `strings` on `x86_64_cc63_libkfio.o_shipped` shows symbol names only (`fusion_do_ll_request`, ...). No
  license string was found in the blob in a first pass.
- `kfio/README.md` (repo) says: "This directory contains object libraries that are proprietary and fill the 'gaps' in
  the open source part of the driver code."
- Vendor and source links in README files (quoted URLs):
  - `README.md:23` `https://github.com/RemixVSL/iomemory-vsl4`
  - `README.md:106` `https://github.com/RemixVSL/iomemory-vsl`
  - `README.md:135` `https://github.com/RemixVSL/vsl_downloads`
  - `README.md:4` `https://github.com/snuf/iomemory-docs`
  - No vendor (SanDisk / Western Digital) source-release URL appears in the repo docs. NOTICE gives a postal address and
    phone number for source requests; not reproduced here.

## 5. Build and runtime (host, measured)

- Distribution: `NAME="Ubuntu"`, `VERSION="24.04.5 LTS (Noble Numbat)"`.
- Kernel: `uname -r` = `7.0.0-28-generic`.
- Compiler: `gcc (Ubuntu 13.3.0-6ubuntu2~24.04.1) 13.3.0`. Build log: "the compiler differs from the one used to build the kernel"
  (kernel built by `x86_64-linux-gnu-gcc-13`, same version string).
- `dkms.conf` MAKE line (13145f4 and installed copy identical on this line):
  `MAKE="'make' -j1 gpl DKMS_KERNEL_VERSION='${kernelver}' KERNEL_BUILD='${kernel_source_dir}' MODULE_VERSION='${PACKAGE_VERSION}' FIO_DKMS_BUILD=1"`
- DKMS: `dkms status` = `iomemory-vsl/1794116140.13145f4abf6c, 7.0.0-28-generic, x86_64: installed`.
- `modinfo iomemory-vsl` (DKMS module file): filename `/lib/modules/7.0.0-28-generic/updates/dkms/iomemory-vsl.ko.zst`;
  version `1794116140.13145f4abf6c`; srcversion `279D601848406282AAECD69`; vermagic `7.0.0-28-generic SMP preempt mod_unload modversions`;
  license `GPL`; 49 `parm:` lines, including `dma32_clamp:Clamp device DMA addressing to 32 bits: 1 = clamp (default, NUMA1 attach fix), 0 = use the full mask the hardware supports (int)`.
  The module is signed by a local key (fingerprint omitted).
- Loaded module: `lsmod` shows `iomemory_vsl`, used by 4. `/sys/module/iomemory_vsl/srcversion` = `A707FCA26416451F13ADC03`
  = srcversion of the `fio-k7` worktree build (section 1). **Loaded srcversion does not equal modinfo srcversion of the DKMS module.**
- Build log (DKMS, the one shipped as `build-make.log`): header `DKMS (dkms-3.4.1) make.log for iomemory-vsl/1794116140.13145f4abf6c
  for kernel 7.0.0-28-generic (x86_64)`, build date `Sun Nov 8 01:59:32 PM UTC 2026`, `# exit code: 0`, `# elapsed time: 00:00:12`.
  Recorded tolerated error: `iomemory-vsl.o: error: objtool: kfio_info_create_dir+0xae (.text+0xc96e): unannotated intra-function call`
  followed by `objtool_wrapper: tolerated known libkfio blob limitation (task-15303)`. This is the one tolerated objtool failure (section 2).
- Build command (from the log header): `make -j1 gpl DKMS_KERNEL_VERSION=7.0.0-28-generic KERNEL_BUILD=/lib/modules/7.0.0-28-generic/build MODULE_VERSION=1794116140.13145f4abf6c FIO_DKMS_BUILD=1`
  via `dkms build/install`. Also `dkms.conf`'s MAKE line.
- Driver load used on the host: `load-fio-driver.sh` (section 7) `insmod`s the repo-root `.ko`. Not what is running now.
- `fio-status -a` (sanitized, `fio-status-a.sanitized.txt`, collected with `sudo -n`, read-only): 4 adapters, all
  `Fusion-io 825GB ioScale2, Product Number:F11-003-825G-CS-0001`, PCI `1aed:2001`, `Firmware v7.1.17, rev 116786 Public`,
  driver `3.2.16 build 1731`, all attached (fct0-fct3, PCI 21:00.0, 22:00.0, a1:00.0, 81:00.0 measured).

## 6. Firmware (no images in this branch)

Directory `/opt/remixvsl-firmware` = clone of `https://github.com/RemixVSL/vsl_downloads.git`, HEAD `0bca66ffc7a94d73db688012cb2bb73ab689d99d`
(2024-01-16). Tracked: `mk_vsl3_firmware.sh`, `mk_vsl4_firmware.sh`, `vsl3/*`, `vsl4/*` (split parts).

| file | bytes | sha256 | origin |
|---|---|---|---|
| `fusion_3.2.16-20180821.fff` | 26489258 | 9ef9010ca93b8dfa1659c4462099cbfffa98b2cfdbbae650cb0e5b87f8c423d6 | untracked output of `mk_vsl3_firmware.sh` from tracked `vsl3/fusion_3.2.16-20180821.fff.tgz.part{aa..af}` |
| `fusion_dell_nosmp.fff` | 26489268 | 223ef73eb105cb60dec17bcaf855645047fac830380ddc74eac953b5ace63065 | **not established**: no tracked part set in `vsl3/` or `vsl4/` matches this name |

- `mk_vsl3_firmware.sh` sha256 `48a13d55ebd30ddeeea050113706b3e03788f85b9cb42cf345e41b14db5424f4`;
  `mk_vsl4_firmware.sh` sha256 `3202669cbd127e1efe86c1c5d61b392e5b83e046408c63740a693a8e089f1604`.
- Version the card reports (fio-status): `Firmware v7.1.17, rev 116786 Public`.
- String search (`grep -a`) finds `7.1.17` 16 times and `3.2.16.1731` 2 times in **both** `.fff` files. This is a
  string match, not a parse of the firmware header. Which file the card runs is not established.
- Update notes: none recorded on the host.

## 7. Files in this branch, and what was not added

Added (all in the one snapshot commit):
- `load-fio-driver.sh` (693 bytes, sha256 `bd8da94fc419a26672be9c272e398721c6b61a237bc92bd4ffe81df4909e7a30`). Host-only
  script at repo root. Read in full; no hostname, IP, user or serial in it. **Note: with the argument `format` it runs
  `fio-format /dev/fct0 -y -f -s 2500G`, which erases the card. With `attach` it runs `fio-attach`.** Keep it out of automation
  without review.
- `installed-dkms/dkms.conf.installed` (the DKMS-stamped conf that differs from main; see section 1).
- `installed-dkms/dkms-source-revision` (13145f4 marker).
- `build-make.log` (DKMS make.log, sanitized: no hostnames, IPs, user names, serials; scan for the host name, the user name, IPv4 addresses and home paths = 0 hits).
- `fio-status-a.sanitized.txt` (serials replaced with `REDACTED-SERIAL-1..4`, VSU UUIDs with `REDACTED-UUID-1..4`).
- `patches/reflog-only-numa1-dma32/0001..0004` (commits `1226c3e`, `b9b4603`, `3a2fd72`, `58941b7`) and
  `patches/reflog-only-task15303-objtool/0001..0003` (commits `ca4c075`, `6b00e51`, `60b5e71`); see section 8.

Not added, and why:
- Build artefacts on host (75 untracked entries in the host repo): 33 `.cmd`, 29 `.o` (incl. `kfio/x86_64_cc133_libkfio.o`),
  5 `.ko`/`.mod*`/`Module.symvers`/`modules.order`, `include/fio/port/linux/kfio_config.h` (generated), `kfio_config/`
  (268 generated probe files), 1 `load-fio-driver.sh` (added, above).
- Backups on host, not needed to build (5): `pci.c.orig`, `pci.c.64bit_orig`, `pci.c.bak-dmapatch`,
  `kfio/x86_64_latest_libkfio.o_shipped.orig`, `kfio/x86_64_latest_libkfio.o_shipped.pre_midprom_patch`.
- The repo-root `iomemory-vsl.ko` and the DKMS `.ko.zst` (binaries). The `libvsl.so` binary is already tracked at 13145f4.
- Firmware `.fff` images (section 6).
- Module signing key and its fingerprint.

## 8. Unpushed host state (measured)

- Host local branches (`main`, `feat/numa1-dma32-on-k7`, `fix/task-11000-fio-numa1-dma32-attach`,
  `share/fio-numa1-dma32-upstream`): every commit they reach is on a remote (`git log --not --remotes` empty for each).
  Nothing to export from branches.
- Host reflog-only commits (reachable from `--reflog`, not from any remote, not on any branch): 7 commits, listed in
  `patches/`. Patch-id check against main's commits (`git show <c> | git patch-id --stable`):
  - `ca4c075` = main `eb33cb2` (`500efa3d...`); `6b00e51` and `60b5e71` = main `dd0c13b` (`99973b6f...`). Same diffs, different commits.
  - `1226c3e`, `b9b4603`, `3a2fd72`, `58941b7` (NUMA1 DMA32 series, June 2026) are not patch-identical to main's
    `6cd7867` (`d145219f...`). Their `pci.c`/`kmem.c` content differs from main (section 1).
- The 7 patches were made with `git format-patch -1 --stdout <sha>` on the host (no writes on the host). Parents:
  `1226c3e` <- `333a629`; `b9b4603` and `3a2fd72` <- `1226c3e`; `58941b7` <- `1ac925a` (not exported; apply after
  `1ac925a`). `ca4c075` <- `d171d8b` (not exported); `6b00e51` <- `ca4c075`; `60b5e71` <- `dba4001` (not exported).
  Patches are for review and were not pushed. Author emails replaced with `REDACTED-EMAIL`.

## 9. Not collected

- `/var/lib/dkms/iomemory-vsl/1794116140.13145f4abf6c/build/` (the DKMS build tree) no longer exists; only logs and the module.
- Source of commit `ca4c075` (the loaded module's revision) beyond its patch; its full tree is only in the host reflog.
- A build log for the loaded `fio-k7` module (`6.17.0-40-ca4c075-3.2.16`): none found.
- `dmesg` and module parameter values beyond the `/sys` list.
- libvsl.so source: none exists in the repo or on the host.
- Vendor source-release package for the GPL/LGPL components listed in NOTICE: not fetched.
- Firmware version parse of the `.fff` files: string match only; the firmware the card runs is not established.
- `fio-format`, `fio-attach`, `fio-detach`, `fio-update-iodrive`, module load or unload: not run. Read-only commands only, with
  `sudo -n` used for `fio-status -a`.
