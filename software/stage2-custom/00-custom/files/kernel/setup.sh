#!/bin/sh

CFG_FILE="/boot/config.txt"
KERNEL_IMG="/boot/kernel8.img"
OVERLAY_DIR="/boot/overlays/"
MODULES="modules/"
OVERLAYS="overlays/"

get_kernel_version() {
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

install_overlays() {
	for overlay in "$OVERLAYS"/*.dtbo; do
		cp -fv "$overlay" $OVERLAY_DIR/ || exit 1
	done
	{
		echo "dtoverlay=impedance-board"
	} >>"$CFG_FILE"
}

install_dependencies
install_modules
install_overlays
