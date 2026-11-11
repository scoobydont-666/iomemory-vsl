# iomemory-vsl: legacy VSL3 Linux compatibility driver

This fork maintains the Linux adapter around the legacy Fusion-io VSL3 core.
The reviewed GitHub snapshot contains the core and `libvsl.so` as opaque binaries;
that snapshot is not a complete source implementation of the storage stack. See
[binary assurance](docs/binary-assurance.md) and the
[security modernization record](docs/security-modernization-2026-11-11.md).

The driver is unsupported by its original vendor and can affect persistent
storage. Use a reviewed immutable revision and qualify the exact kernel, card,
firmware, DMA/IOMMU configuration, and recovery path before deployment.

## Support and release status

There is no blanket support promise for every Linux 5.x, 6.x, or 7.x kernel.
The historical pre-review CI built and installed against Ubuntu
`6.8.0-149-generic` and `7.0.0-42-generic`; it did not load the module or validate
storage integrity. New source revisions require their own results.
[Qualification](docs/qualification.md) defines the evidence needed for a release.
`main` is a development branch, not an immutable qualified release.

This driver targets VSL3-generation hardware. VSL4 uses a different driver and
is maintained separately at [RemixVSL/iomemory-vsl4](https://github.com/RemixVSL/iomemory-vsl4).
Identify the card and OEM variant before choosing a driver; the upstream
[part-number matrix](https://docs.google.com/spreadsheets/d/e/2PACX-1vQMd40liekOCeftUYQx6GeofHgjU5SSDT-jHWid03JCfswQxHAhVee3rW-04baqKg1qN2fp7wEzuFm6/pubhtml)
is a reference, not a qualification result for this fork.

## Build and installation

Install Git, Python 3, your distribution's build tools, DKMS, and matching
headers for each intended kernel. Follow [DKMS.md](DKMS.md) for source identity,
repeat installation, autoinstall, signing, initramfs, and rollback checks.
Clone this fork and explicitly select the reviewed revision:

```sh
git clone https://github.com/scoobydont-666/iomemory-vsl.git
cd iomemory-vsl
git checkout --detach REVIEWED_COMMIT_SHA
python3 tools/verify_binary_artifacts.py
python3 -m unittest discover -s tests -p 'test_*.py' -v
sudo make dkms KERNELVER=YOUR_TARGET_KERNEL_RELEASE
```

Replace both placeholders with the revision and installed target kernel being
qualified. DKMS builds and installs a module for kernel updates; it does not
prove module loading, attachment, persistence, or boot recovery. The maintained
installer retains older versions and does not issue device-format, erase,
module-load/unload, bootloader, or reboot commands.

Manual and package builds use the same validated module path:

```sh
make module KERNELVER=YOUR_TARGET_KERNEL_RELEASE
# Distribution packaging, with matching build dependencies installed:
make dpkg
# or:
make rpm
```

A successful command only establishes the checks that actually ran. Packaging
routes require their own artifact/install qualification. Legacy
`module_operations.sh -d` and the historical EFI installer are retired; use the
maintained DKMS route. Historical [TrueNAS notes](TrueNAS.md) require separate
validation against this fork and the target operating system.

## DMA and IOMMU policy

`dma32_clamp=1` remains the default, load-time policy for PCI DMA masks and
coherent allocations. It preserves the compatibility workaround for hardware
requiring 32-bit device-visible DMA addresses. `dma32_clamp=0` permits the core's
requested mask; it does not relax the opaque core's generic allocation policy.
Host-only scatter/gather metadata uses ordinary slab allocation.

Keep IOMMU policy under the host's normal security and qualification process.
There is no generic instruction to add `iommu=pt`: passthrough changes DMA
isolation and cannot repair driver mapping/length/completion errors. Exercise
translated IOMMU and the intended clamp setting on each supported platform.
The coherent allocator preserves device NUMA topology and delegates zone
fallback to the kernel DMA API.

## Sure erase maintenance mode

`sure_erase_mode` is load-only and accepts zero or one. Value one disables
automatic attachment during initialization. Use it only in a controlled offline
maintenance procedure with the correct card and utilities. The legacy core's
length-based usercopy workaround remains a compatibility limitation; Linux
usercopy protections remain active. This repository does not qualify firmware
erase behavior or authorize destructive commands.

## Verification

Offline regression tests exercise production function bodies in bounded
userspace fixtures and run installation/build helpers against controlled
backends. GitHub Actions separately performs real kernel-header builds and DKMS
lifecycle checks on ephemeral hosted runners. Neither lane accesses storage
hardware. See [the qualification matrix](docs/qualification.md) for required
fault, persistence, concurrency, signing, and reboot tests.

# Utils
The utilities to query and manage the drive(s) can be found in the [vsl_downloads](https://github.com/RemixVSL/vsl_downloads) repo.

After installing the utilities and using `fio-status -a` something as follows should be printed:
```
Found 1 ioMemory device in this system
Driver version: 3.2.16 build 1731

Adapter: Single Controller Adapter
	Fusion-io ioDrive2 1.205TB, Product Number:F00-001-1T20-CS-0001, SN:1241D0259, FIO SN:1241D0259
	ioDrive2 Adapter Controller, PN:PA004137009
	External Power: NOT connected
	PCIe Bus voltage: avg 12.02V
	PCIe Bus current: avg 0.77A
	PCIe Bus power: avg 9.21W
	PCIe Power limit threshold: 24.75W
	PCIe slot available power: unavailable
	Connected ioMemory modules:
	  fct0:	Product Number:F00-001-1T20-CS-0001, SN:1241D0259

fct0	Attached
	ioDrive2 Adapter Controller, Product Number:F00-001-1T20-CS-0001, SN:1241D0259
	ioDrive2 Adapter Controller, PN:PA004137009
	SMP(AVR) Versions: App Version: 1.0.29.0, Boot Version: 0.0.8.1
	Located in slot 0 Center of ioDrive2 Adapter Controller SN:1241D0259
	Powerloss protection: protected
	PCI:00:04.0, Slot Number:3
	Vendor:1aed, Device:2001, Sub vendor:1aed, Sub device:2001
	Firmware v7.1.15, rev 110356 Public
	UEFI Option ROM v3.2.6, rev 1212 Enabled
	1205.00 GBytes device size
	Format: v500, 2353515625 sectors of 512 bytes
	PCIe slot available power: unavailable
	PCIe negotiated link: 4 lanes at 5.0 Gt/sec each, 2000.00 MBytes/sec total
	Internal temperature: 64.47 degC, max 64.97 degC
	Internal voltage: avg 1.02V, max 1.02V
	Aux voltage: avg 2.49V, max 2.49V
	Reserve space status: Healthy; Reserves: 100.00%, warn at 10.00%
	Active media: 100.00%
	Rated PBW: 17.00 PB, 99.46% remaining
	Lifetime data volumes:
	   Physical bytes written: 92,553,058,889,120
	   Physical bytes read   : 82,741,942,333,288
	RAM usage:
	   Current: 389,636,800 bytes
	   Peak   : 389,636,800 bytes
	Contained VSUs:
	  fioa:	ID:0, UUID:0f402a7e-9948-7a4f-a2d0-7b0cb4d1ecda

fioa	State: Online, Type: block device
	ID:0, UUID:0f402a7e-9948-7a4f-a2d0-7b0cb4d1ecda
	1205.00 GBytes device size
	Format: 2353515625 sectors of 512 bytes
```
Where `dmesg` contains the actual driver version tag of the running driver
```
vagrant@fio:~/iomemory-vsl/root/usr/src/iomemory-vsl-3.2.16$ dmesg | grep "ioDrive driver"
[    3.122269] <6>fioinf ioDrive driver 5.11.10-b29020f-3.2.16.1731        loading...
```
## TrueNAS Support
See [this document](https://github.com/RemixVSL/iomemory-vsl/blob/main/TrueNAS.md) for information on how to install on TrueNAS. These steps were developed by a community contribution, and aren't generally tested with new versions of RemixVSL or TrueNAS.

# How to Get Help
For security-sensitive findings, follow [SECURITY.md](SECURITY.md). For ordinary
compatibility questions, use this fork's Discussions or issue tracker when enabled.
The upstream community is available at https://discord.gg/VxDvVy3EdS; identify the
fork and exact commit when asking for help. Repository features may be disabled.

# Acknowledgements
The support and maintenance of this driver is made possible by the people that actively contribute or contributed to its code base or by supporting the project in other ways.

| Name | Discord |  |
|---|---|---|
| Demetrius Cassidy | @Tourman | Long nights of cleaning the codebase, setting up the Discord channel and guiding people through firmware upgrades |
| Vince Fleming |  | Donating a 1.2TB IoDrive2 for debugging problems |

Obviously all the regulars on the Discord channel, notably @bplein, @AcquaCow and @Tear.

Oh yes and the folks that were at <b>Fusion IO</b> for creating this product that was way ahead of its time and delivering the integration shim sources with the driver core.

## Resources
Tools and resources often used to figure out what changed, and why things are not working as they are supposed to.
| Source | |
| --- | --- |
| [Elixir](https://elixir.bootlin.com/linux/latest/source) | Making the Linux source code browsable and easy to compare changes over time | 
| [ZOL](https://zfsonlinux.org/) |  A source of inspiration for changes in the block layers of the linux kernel that we get to deal with | 
| [LKML](https://lkml.org/) | Sometimes the first or last resort to figure out why something changed in the kernel, or where |
| [The Nvidia Forum](https://forums.developer.nvidia.com/c/gpu-unix-graphics/linux/148) | Because they are hot to trot they encounter problems before we do, so we get to ride on their coat tails.... sometimes....though  often not | 
| [Ghidra](https://ghidra-sre.org/) | The Ghidra project from the NSA that allows a look under the covers to figure out things inside non-sourcy libs|


## Notes
Installing the fio-util, fio-common, fio-preinstall and fio-sysvinit are recommended.
When moving from source 2.3.11 to source 3.2.10 the firmware HAS TO BE UPDATED to 3.2.10.20150212. For the move to 3.2.15, and 3.2.16 from 3.2.10 we've not seen any issues.

## Firmware
Select firmware by the exact card model/OEM identity and the vendor compatibility
information available for that device. Record the running firmware in qualification
evidence. A newer version number alone is not evidence of compatibility; firmware
changes require their own tested maintenance and recovery procedure.
