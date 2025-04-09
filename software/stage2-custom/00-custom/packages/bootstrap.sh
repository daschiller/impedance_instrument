#!/bin/sh

sudo chown -Rc wood /sys/bus/iio/devices/iio:device0/
sudo chown wood /dev/iio:device0

# use /etc/modules
sudo modprobe i2c-dev
