# SPDX-License-Identifier: GPL-3.0-only

# Copyright (c) 2024 David Schiller <david.schiller@jku.at>

import struct
from fcntl import ioctl

from smbus import SMBus

MCP9600_ADDR = 0x60
HOT_JUNC_REG = 0x00
# i2c-dev ioctl command for selecting slave address
I2C_SLAVE = 0x0703
# equivalent to /dev/i2c-1
RASPI_BUS = 1


class MCP9600:
    def __init__(self, bus=RASPI_BUS, addr=MCP9600_ADDR):
        self.fd = open(f"/dev/i2c-{RASPI_BUS}", "r+b", buffering=0)
        ioctl(self.fd, I2C_SLAVE, addr)
        # set register pointer to hot junction register
        # self.fd.write(b"\x00")

    def enable_filter(self, level):
        # set register pointer to sensor configuration sensor
        # and write filter value
        self.fd.write(b"\x05" + level.to_bytes(1, "big"))
        # set register pointer to hot junction register
        self.fd.write(b"\x00")

    @property
    def temp(self):
        return struct.unpack(">h", self.fd.read(2))[0] / 16


class _MCP9600:
    def __init__(self, bus=RASPI_BUS, addr=MCP9600_ADDR):
        self.bus = SMBus(bus)
        self.addr = addr

    def _read(self, reg, size):
        return self.bus.read_i2c_block_data(self.addr, reg, size)

    @property
    def temp(self):
        data = self._read(HOT_JUNC_REG, 2)
        temp = struct.unpack(">h", bytes(data))[0] / 16

        return temp


if __name__ == "__main__":
    therm = MCP9600()
    print(therm.temp)
