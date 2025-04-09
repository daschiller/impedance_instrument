#!/bin/bash -e

install -m 755 files/start-gui "${ROOTFS_DIR}/usr/local/bin"
cp -ar files/impedance/ "${ROOTFS_DIR}/usr/local/src"
install -d -m 755 -o 1000 -g 1000 "${ROOTFS_DIR}/home/${FIRST_USER_NAME}/data"
install -m 644 files/configs/10-udisks.pkla "${ROOTFS_DIR}/etc/polkit-1/localauthority/50-local.d"
install -m 644 files/configs/99-iio.rules "${ROOTFS_DIR}/etc/udev/rules.d"
install -m 644 files/configs/impedance.service "${ROOTFS_DIR}/etc/systemd/system"
cp -r files/kernel "${ROOTFS_DIR}/tmp/"

install -m 644 files/autossh/autossh.service "${ROOTFS_DIR}/etc/systemd/system"
install -d -m 755 -o 1000 -g 1000 "${ROOTFS_DIR}/home/${FIRST_USER_NAME}/bin"
install -m 755 -o 1000 -g 1000 files/autossh/setup-reverse-ssh "${ROOTFS_DIR}/home/${FIRST_USER_NAME}/bin"

install -m 644 packages/*.deb "${ROOTFS_DIR}/tmp"

on_chroot <<EOF
rm -rf /root/.cache

apt-get purge -y --autoremove rsyslog triggerhappy
cd /tmp && apt-get install -y --no-install-recommends ./*.deb && rm *.deb
apt-get autopurge -y
EOF

on_chroot <<EOF
sed -i "s/{USER}/${FIRST_USER_NAME}/" /etc/systemd/system/impedance.service
systemctl enable impedance

echo "i2c-dev" >> /etc/modules
EOF

on_chroot <<EOF
cd /tmp/kernel
./setup.sh || exit 1
cd .. && rm -rf kernel

# disable getty and VT cursor
systemctl disable getty@tty1.service
sed -i 's/$/ loglevel=3 vt.global_cursor_default=0/' /boot/cmdline.txt
# DIRTY HACK: 'firstboot' would remove 'quiet'
sed -Ei 's|(sed -i "s/ quiet//g" /boot/cmdline.txt)|#\1\n  :|' /usr/lib/raspberrypi-sys-mods/firstboot
EOF

if [ -n "$PROVISION_SSH_KEYS" ]; then
	cp -ar files/ssh/ "${ROOTFS_DIR}/home/${FIRST_USER_NAME}/.ssh"
	rm "${ROOTFS_DIR}/home/${FIRST_USER_NAME}/bin/setup-reverse-ssh"

	on_chroot <<-EOF
		chown -R ${FIRST_USER_NAME}: /home/${FIRST_USER_NAME}/.ssh
		sed -i "s/{PORT}/${REVERSE_SSH_PORT}/" /etc/systemd/system/autossh.service
		sed -i "s/{USER}/${FIRST_USER_NAME}/" /etc/systemd/system/autossh.service
		systemctl enable autossh
	EOF
fi
