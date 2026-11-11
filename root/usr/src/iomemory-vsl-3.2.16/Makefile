# KERNELRELEASE is set by the kernel build system.  This is used
# as a test to know if the build is being driven by the kernel.
ifneq ($(KERNELRELEASE),)
# Kernel build

# Older kernel scripts/Makefile.build only process Makefile so
# we include the Kbuild file here.  Newer kernel scripts/Makefile.build
# include Kbuild directly and never process Makefile (this file).
include $(FUSION_DRIVER_DIR)/Kbuild

else

ifneq ($(CROSS_COMPILE),)
FIOCC=$(CROSS_COMPILE)gcc
else
FIOCC=$(CC)
endif
$(info    FIOCC is $(FIOCC))

FIO_DRIVER_NAME ?= $(shell cat dkms.conf | grep BUILT_MODULE_NAME | awk -F= '{ print $$2 }')
FIO_DRIVER_SUBDIR ?= extra/fio
FUSION_DEBUG ?= 0
FIO_SCSI_DEVICE ?= 0

ifneq ($(DKMS_KERNEL_VERSION),)
KERNELVER = $(DKMS_KERNEL_VERSION)
else
KERNELVER ?= $(shell uname -r)
endif
KERNEL_BUILD = /lib/modules/$(KERNELVER)/build
CFLAGS = -I$(shell pwd)/include -DBUILDING_MODULE -DLINUX_IO_SCHED -Wall

# Older systems (Debian 6) have the kernel headers in a different directory than the kernel build directory.
# Start in this source directory, and fix it up in the config shell script if it isn't right.
KERNEL_SRC = /lib/modules/$(KERNELVER)/source

# Set PORT_NO_WERROR=0 to compile without -Werror compilation flag
ifneq ($(PORT_NO_WERROR),1)
    CFLAGS += -Werror
endif

# Set FUSION_DEBUG=0 to compile without debugging symbols
ifeq ($(FUSION_DEBUG),1)
    CFLAGS += -g -ggdb
endif
# Target should be a mix of compiler version, platform and cpu this will allow
# us to build multiple targets in the same tree without overlapping objects
# and libs.  We will need to build multiple objects where kernel ifdefs
# differ.
FIOARCH ?= $(shell uname -m)
CCMAJOR ?= $(shell echo __GNUC__ | $(FIOCC) -E -xc - | tail -n 1)
CCMINOR ?= $(shell echo __GNUC_MINOR__ | $(FIOCC) -E -xc - | tail -n 1)
CCVER=$(CCMAJOR)$(CCMINOR)
LAST_CCVER := $(shell ls -1 kfio | sed -n 's/.*_cc\([0-9][0-9]*\)_.*/\1/p' | tail -1)
# Get the tag and push it in here too.... if not too long...
# A source package has no Git metadata; its declared package version remains
# available. Package builders and DKMS pass their exact version explicitly.
MODULE_VERSION ?= $(shell git rev-parse --short HEAD 2>/dev/null || sed -n 's/^PACKAGE_VERSION=//p' dkms.conf)
export MODULE_VERSION

TARGET ?= $(FIOARCH)_cc$(CCMAJOR)$(CCMINOR)

KFIO_LIB ?= kfio/$(TARGET)_libkfio.o
LAST_KFIO_LIB := x86_64_latest_libkfio.o_shipped
KFIO_LIB_CMD ?= kfio/.$(TARGET)_libkfio.o.cmd

NCPUS:=$(shell grep -c ^processor /proc/cpuinfo)

# All supported entry points converge on the same validated module artifact.
# Wrapper prerequisites run serially; the kernel submake supplies parallelism.
.NOTPARALLEL:
.PHONY: all gpl modules modules_install objtool_perfile fake_license
all gpl objtool_perfile: modules

include Kbuild.objects
OBJTOOL := $(KERNEL_BUILD)/tools/objtool/objtool
KREL_MAJOR = $(shell cut -d. -f1 $(KERNEL_BUILD)/include/config/kernel.release 2>/dev/null)

# The historic name is retained only to refuse metadata rewriting explicitly.
fake_license:
	@echo 'fake_license is retired; module metadata does not license the proprietary core' >&2
	@exit 1

.PHONY: check_n_fix_kfio_ccver
check_n_fix_kfio_ccver:
	if [ ! -f "${KFIO_LIB}" ];then \
		cp kfio/${LAST_KFIO_LIB} ${KFIO_LIB}; \
	fi
	touch "$(KFIO_LIB_CMD)"


clean modules_clean:
	$(MAKE) \
		-j$(NCPUS) \
		-C $(KERNEL_BUILD) \
		FIO_DRIVER_NAME=$(FIO_DRIVER_NAME) \
		FUSION_DRIVER_DIR=$(shell pwd) \
		M=$(shell pwd) \
		FIO_CFLAGS="$(CFLAGS)" \
		KFIO_LIB=$(KFIO_LIB) \
		clean
	rm -rf include/fio/port/linux/kfio_config.h kfio_config .objtool-first-party
	rm -f .objtool-link-args .objtool-link-needs-perfile .objtool-relink-required

include/fio/port/linux/kfio_config.h: kfio_config.sh
	./$< -a $(FIOARCH) -o $@ -k $(KERNEL_BUILD) -p -d $(CURDIR)/kfio_config -l $(FUSION_DEBUG) -s $(KERNEL_SRC)

.PHONY: check_target_kernel
check_target_kernel:
	@ret="$$(./check_target_kernel.sh "$(KERNELVER)" "$(KERNEL_BUILD)")" ; \
	if [ -n "$$ret" ] ; then \
		echo "" ; \
		echo "Change found in target kernel: $$ret" ; \
		echo "Running clean before building driver" ; \
		echo "" ; \
		$(MAKE) clean ; \
	fi

.PHONY: add_module_version patch_module_version
# Every route generates metadata before linking. Never patch a linked/signed
# module or an opaque core object. GPL remains the historical compatibility tag;
# it is not a statement about the license of the proprietary core (see docs).
add_module_version:
	@printf '%s\n' "$${MODULE_VERSION}" | grep -Eq '^[a-zA-Z0-9][a-zA-Z0-9_.-]{0,63}$$'
	@printf '#include "linux/module.h"\nMODULE_LICENSE("GPL");\nMODULE_VERSION("%s");\n' "$${MODULE_VERSION}" > license.c.tmp
	@cmp -s license.c.tmp license.c || mv -f license.c.tmp license.c
	@rm -f license.c.tmp

patch_module_version: add_module_version

.PHONY: dkms
dkms:
	bash ./dkms-install.sh "$(KERNELVER)" "$(KERNEL_BUILD)"

.PHONY: dpkg
dpkg:
	# patch fio_version, fio_short_version in debian/fio_values
	cd $(shell git rev-parse --show-toplevel) && \
			$(MAKE) dpkg

.PHONY: dpkg
rpm:
	# patch fio_version, fio_short_version in debian/fio_values
	cd $(shell git rev-parse --show-toplevel) && \
			$(MAKE) rpm

KERNEL_MAKE = $(MAKE) -j$(NCPUS) -C "$(KERNEL_BUILD)" \
	FIO_DRIVER_NAME="$(FIO_DRIVER_NAME)" FUSION_DRIVER_DIR="$(CURDIR)" \
	M="$(CURDIR)" FIO_CFLAGS="$(CFLAGS)" FIO_SCSI_DEVICE="$(FIO_SCSI_DEVICE)" \
	INSTALL_MOD_DIR="$(FIO_DRIVER_SUBDIR)" INSTALL_MOD_PATH="$(INSTALL_ROOT)" \
	KFIO_LIB="$(KFIO_LIB)" objtool="$(CURDIR)/objtool_wrapper"

.PHONY: prepare_module
prepare_module: check_target_kernel check_n_fix_kfio_ccver include/fio/port/linux/kfio_config.h add_module_version

modules:
	@set -eu; \
	trap 'rm -f "$(FIO_DRIVER_NAME).ko"' EXIT HUP INT TERM; \
	$(MAKE) prepare_module; \
	$(KERNEL_MAKE) modules; \
	bash ./objtool-perfile.sh "$(OBJTOOL)" "$(KREL_MAJOR)" $(FIO_PORT_OBJS); \
	if test -f .objtool-relink-required; then \
	    rm -f "$(FIO_DRIVER_NAME).o" "$(FIO_DRIVER_NAME).ko" "$(FIO_DRIVER_NAME).mod.o"; \
	    $(KERNEL_MAKE) modules; \
	    rm -f .objtool-relink-required; \
	fi; \
	trap - EXIT HUP INT TERM

modules_install: modules
	$(KERNEL_MAKE) modules_install

endif

# 4.3.7.1205 bryce@a7e621e6fb50 -tag=7bd0632
# 3.2.16.1731 pinnacles@4870ad45b7ea
