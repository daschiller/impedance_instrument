#!/bin/sh

CFG_FILE="/boot/config.txt"
CMD_FILE="/boot/cmdline.txt"
KERNEL_IMG="/boot/kernel8.img"
OVERLAY_DIR="/boot/overlays/"
MODULES="modules/"
OVERLAY="overlays/"

get_kernel_version() {
	# echo "6.1.21-v8+"
	zcat "$KERNEL_IMG" | grep -m 1 -Poa 'Linux version \K[^\s]+'
}

install_dependencies() {
	apt-get install -y --no-install-recommends raspberrypi-kernel-headers dkms
}

install_modules() {
	for module in "$MODULES"/*; do
		dkms add "$module"
	done
	dkms autoinstall -k "$(get_kernel_version)" || exit 1
}

install_overlay() {
	cd "$OVERLAY" || exit 1
	make reTerminal-overlay.dtbo || exit 1
	cp -fv reTerminal-overlay.dtbo $OVERLAY_DIR/reTerminal.dtbo || exit 1
	{
		echo "dtoverlay=reTerminal"
		echo "dtoverlay=i2c3,pins_4_5"
	} >>"$CFG_FILE"
	sed -i 's/$/ fbcon=rotate:1/g' "$CMD_FILE"
}

install_dependencies
install_modules
install_overlay
