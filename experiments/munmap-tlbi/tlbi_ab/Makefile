# Out-of-tree build of tlbi_ab.ko against the xcore-stat2+ kernel tree.
# Cross-build on the x86 build host:
#   make KDIR=/home/haoze/common
# (KDIR must be the kernel source tree that produced the running kernel, so the
#  module's vermagic matches. ARCH/CROSS_COMPILE default to arm64 cross.)
KDIR ?= /home/haoze/common
ARCH ?= arm64
CROSS_COMPILE ?= aarch64-linux-gnu-

obj-m := tlbi_ab.o

all:
	$(MAKE) -C $(KDIR) M=$(CURDIR) ARCH=$(ARCH) CROSS_COMPILE=$(CROSS_COMPILE) modules

clean:
	$(MAKE) -C $(KDIR) M=$(CURDIR) ARCH=$(ARCH) CROSS_COMPILE=$(CROSS_COMPILE) clean
