# Stage-0 capability probes (build natively on the target board).
all: isar0 kvm_el2_probe guest.bin

isar0: isar0.c
	gcc -O2 -o $@ $<

kvm_el2_probe: kvm_el2_probe.c
	gcc -O2 -o $@ $<

guest.bin: guest.S
	as guest.S -o guest.o && objcopy -O binary guest.o guest.bin

clean:
	rm -f isar0 kvm_el2_probe guest.o guest.bin
