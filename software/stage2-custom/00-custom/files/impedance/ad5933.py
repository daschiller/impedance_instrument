# SPDX-License-Identifier: GPL-3.0-only

# Copyright (c) 2024 David Schiller <david.schiller@jku.at>

import logging
import struct
from math import atan2, pi, sqrt
from statistics import mean, stdev

import iio
from scipy.interpolate import UnivariateSpline

from adg729 import ADG729

# maybe use an enum here
OUTPUT_VOLTAGES = ("1980", "970", "383", "198")
# mux (cal, gain), PGA gain, output voltage
RANGES = {
    1: [(0, 1), 1, 3],
    2: [(0, 2), 1, 1],
    3: [(0, 3), 5, 1],
    4: [(0, 4), 5, 1],
}
# last value in list is the nominal value of the calibration resistor
CAL_RANGES = {
    1: [(1, 1), 1, 3, 14.7],
    2: [(2, 2), 1, 1, 1e3],
    3: [(3, 3), 5, 1, 100e3],
    4: [(4, 4), 5, 1, 1e6],
}
CAL_FREQS = sorted(
    set(
        (
            *range(1, 10, 2),
            *range(10, 100, 20),
            *range(100, 1000, 100),
            # *range(300, 600, 10),  # phase anomaly in this region
            *range(300, 600, 20),  # phase anomaly in this region
            *range(1000, 3000, 100),  # gain factor ringing
            *range(3000, 10000, 500),
            *range(10000, 100000, 10000),
        )
    )
)
TIMEOUT = 600000  # 10 minutes
SAMPLES_PER_POINT = 3 - 1
SMOOTH = 0
CLOCK_FREQ = 9e6
LOWER_CLOCK_LIMIT = 22500


logging.basicConfig()
logger = logging.getLogger(__name__)


class AD5933:
    def __init__(self, cal_freqs=CAL_FREQS):
        self.cal_freqs = cal_freqs
        self.mux = ADG729()
        self.ctx = iio.Context()
        self.ctx.set_timeout(TIMEOUT)
        self.dev = self.ctx.find_device("ad5933")
        assert self.dev is not None
        # channels
        self.real = self.dev.find_channel("voltage_real")
        self.imag = self.dev.find_channel("voltage_imag")
        self.output = self.dev.find_channel("altvoltage0", is_output=True)
        self.input = self.dev.find_channel("voltage0")
        self.range = 1
        self.gain_parameters = {1: [], 2: [], 3: [], 4: []}
        self.phase_offsets = {1: [], 2: [], 3: [], 4: []}

    @property
    def temp(self):
        temp = self.dev.find_channel("temp")
        return int(temp.attrs["raw"].value) * float(temp.attrs["scale"].value) / 1000.0

    @property
    def clock_frequency(self):
        return int(self.dev.attrs["clock_frequency"].value)

    @clock_frequency.setter
    def clock_frequency(self, f):
        assert f >= LOWER_CLOCK_LIMIT
        self.dev.attrs["clock_frequency"].value = f"{int(f)}"

    @property
    def range(self):
        return self._range

    @range.setter
    def range(self, index):
        assert index in range(1, len(RANGES) + 1)
        self.mux.write(*RANGES[index][0])
        self._set_gain(RANGES[index][1])
        self._set_output_voltage(RANGES[index][2])
        self._range = index

    @property
    def cal_freqs(self):
        # ADC sample rate is 1/16 of MCLK
        adc_rate = self.clock_frequency / 16
        # divide by two due to Nyquist
        # TODO: elaborate on formulas
        return [
            f
            for f in self._cal_freqs
            if f in range(int(adc_rate / 1000), int(adc_rate / 2))
        ]

    @cal_freqs.setter
    def cal_freqs(self, freqs):
        self._cal_freqs = freqs

    def cal_range(self, index):
        assert index in range(1, len(CAL_RANGES) + 1)
        self.mux.write(*CAL_RANGES[index][0])
        self._set_gain(CAL_RANGES[index][1])
        self._set_output_voltage(CAL_RANGES[index][2])

        gain = []
        phase = []
        for f in self.cal_freqs:
            data = self._raw_sweep(f, 0, SAMPLES_PER_POINT)
            real = mean(data["real"])
            imag = mean(data["imag"])
            magnitude = sqrt(real ** 2 + imag ** 2)
            gain.append(1 / CAL_RANGES[index][3] / magnitude)
            phase.append(atan2(imag, real))
        self.gain_parameters[index] = gain
        self.phase_offsets[index] = phase
        self.range = index

    def _gain(self, frequency):
        spline = UnivariateSpline(
            self.cal_freqs,
            self.gain_parameters[self._range],
            s=SMOOTH,
            k=3,
            w=[2 / stdev(self.gain_parameters[self._range])] * len(self.cal_freqs),
        )
        return spline(frequency)

    def _phase(self, frequency):
        spline = UnivariateSpline(
            self.cal_freqs,
            self.phase_offsets[self._range],
            s=SMOOTH,
            k=3,
            w=[2 / stdev(self.phase_offsets[self._range])] * len(self.cal_freqs),
        )
        return spline(frequency)

    def cal_all_ranges(self):
        previous_range = self.range
        for _, i in enumerate(CAL_RANGES):
            self.cal_range(i)
        self.range = previous_range

    def measure(self, f=10000):
        data = self._raw_sweep(f, 0, SAMPLES_PER_POINT)
        real = mean(data["real"])
        imag = mean(data["imag"])
        magnitude = sqrt(real ** 2 + imag ** 2)
        phase = atan2(imag, real)
        return (
            1 / self._gain(f) / magnitude,
            (phase - self._phase(f)) / pi * 180,
        )

    def sweep(self, start, increment, points):
        output = []
        data = self._raw_sweep(start, increment, points)
        for i, (real, imag) in enumerate(zip(data["real"], data["imag"])):
            magnitude = sqrt(real ** 2 + imag ** 2)
            phase = atan2(imag, real)
            f = start + increment * i
            magnitude = 1 / self._gain(f) / magnitude
            phase_deg = (phase - self._phase(f)) / pi * 180
            output.append({"f": f, "magnitude": magnitude, "phase": phase_deg})
        return output

    def _raw_sweep(self, start, increment, points):
        # number of increments is limited to 9 bits
        if points not in range(512):
            logging.warning(
                f"clamping points to allowed range: {points} -> {(points:=min(points,511))}"
            )
        self.output.attrs["frequency_start"].value = f"{start:.0f}"
        self.output.attrs["frequency_increment"].value = f"{increment:.0f}"
        self.output.attrs["frequency_points"].value = f"{points:.0f}"
        self.output.attrs["settling_cycles"].value = "10"

        self.real.enabled = True
        self.imag.enabled = True
        buf = iio.Buffer(self.dev, (points + 1))
        assert buf is not None
        buf.refill()

        logger.debug(f"buf: 0x{buf.read().hex()})")
        real_data = tuple(
            data[0] for data in struct.iter_unpack("<h", self.real.read(buf))
        )
        imag_data = tuple(
            data[0] for data in struct.iter_unpack("<h", self.imag.read(buf))
        )

        buf.cancel()
        return {"real": real_data, "imag": imag_data}

    def _set_gain(self, factor):
        assert factor in (1, 5), "only gains of x1 and x5 are available"
        self.input.attrs["scale"].value = "1" if factor == 1 else "0.2"

    def _set_output_voltage(self, index):
        assert index in range(
            1, len(OUTPUT_VOLTAGES)
        ), f"index needs to be a number between 1 and {len(OUTPUT_VOLTAGES)}"
        self.output.attrs["raw"].value = OUTPUT_VOLTAGES[index - 1]


if __name__ == "__main__":
    import matplotlib.pyplot as plt
    import numpy as np

    @np.vectorize
    def Z(f, R, C):
        return 1 / np.sqrt(4 * np.pi ** 2 * f ** 2 * C ** 2 + 1 / R ** 2)

    @np.vectorize
    def phi(f, R, C):
        return -np.arctan(2 * np.pi * f * R * C) / np.pi * 180

    impedance = AD5933()

    # R = 1000
    # C = 2.7e-9
    R = 3300
    C = 0
    f_range = range(1, 100000, 10)

    plt.ion()

    def plot_Z(data):
        plt.loglog(
            [i["f"] for i in data], [i["magnitude"] for i in data], label="Z_measured"
        )
        plt.loglog(
            [i["f"] for i in data],
            [Z(i["f"], R, C) for i in data],
            label="Z_calculated",
        )
        plt.legend()
        plt.show()
        error = mean(
            [abs(i["magnitude"] - Z(i["f"], R, C)) / Z(i["f"], R, C) for i in data]
        )
        print(f"Average error in percent: {error*100:.2f}")

    def plot_phi(data):
        plt.plot(
            [i["f"] for i in data], [i["phase"] for i in data], label="phi_measured"
        )
        plt.plot(
            [i["f"] for i in data],
            [phi(i["f"], R, C) for i in data],
            label="phi_calculated",
        )
        plt.xscale("log")
        plt.legend()
        plt.show()
        error = mean([abs(i["phase"] - phi(i["f"], R, C)) for i in data])
        print(f"Average error in degrees: {error:.2f}")

    def check_gain(impedance):
        plt.plot(
            impedance.cal_freqs,
            impedance.gain_parameters[impedance.range],
            label="measured",
        )
        plt.plot(f_range, [impedance._gain(i) for i in f_range], label="fit")
        plt.legend()
        plt.show()

    def check_phase(impedance):
        plt.plot(
            impedance.cal_freqs,
            impedance.phase_offsets[impedance.range],
            label="measured",
        )
        plt.plot(f_range, [impedance._phase(i) for i in f_range], label="fit")
        plt.xscale("log")
        plt.legend()
        plt.show()

    # logger.setLevel(logging.DEBUG)
