#!/bin/bash -e

cp -r files/reterminal "${ROOTFS_DIR}/tmp/"

on_chroot << EOF
cd /tmp/reterminal
./setup.sh || exit 1
cd .. && rm -rf reterminal

# fix removal of dkms modules
# https://github.com/dell/dkms/issues/37
sed -i 's/dkms remove/dkms unbuild/' /etc/kernel/prerm.d/dkms
EOF
