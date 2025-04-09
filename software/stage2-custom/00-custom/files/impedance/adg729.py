# SPDX-License-Identifier: GPL-3.0-only

# Copyright (c) 2024 David Schiller <david.schiller@jku.at>

from time import sleep

from smbus import SMBus

ADG729_ADDR = 0x44
# equivalent to /dev/i2c-1
RASPI_BUS = 1


class ADG729:
    def __init__(self, bus=RASPI_BUS, addr=ADG729_ADDR):
        self.bus = SMBus(bus)
        self.addr = addr

    def _read(self):
        data = self.bus.read_byte(self.addr)
        # little-endian format
        return [bool(data & (1 << i)) for i in range(8)]

    def read(self):
        states = self._read()
        try:
            switch_a = states[0:4].index(True) + 1
        except ValueError:
            switch_a = False
        try:
            switch_b = states[4:8].index(True) + 1
        except ValueError:
            switch_b = False

        return switch_a, switch_b

    def write(self, a=None, b=None):
        assert a is None or a in range(5)
        assert b is None or b in range(5)

        data = self.bus.read_byte(self.addr)

        if a is not None:
            if a > 0:
                a -= 1
                data = (data & 0xF0) | (1 << a)
            else:
                data = data & 0xF0

        if b is not None:
            if b > 0:
                b -= 1
                data = (1 << b + 4) | (data & 0x0F)
            else:
                data = data & 0x0F

        self.bus.write_byte(self.addr, data)
        sleep(0.01)


if __name__ == "__main__":
    mux = ADG729()
    print(mux.read())
