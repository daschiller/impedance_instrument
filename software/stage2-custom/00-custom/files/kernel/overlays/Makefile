OVERLAY_DIR := /boot/overlays

%.dtbo: %.dts
	dtc -I dts -O dtb $< -o $@

all: impedance-board.dtbo

.PHONY: install clean

install: impedance-board.dtbo
	install $< $(OVERLAY_DIR)

clean:
	rm -f *.dtbo
