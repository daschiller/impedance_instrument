# SPDX-License-Identifier: GPL-3.0-only

# Copyright (c) 2024 David Schiller <david.schiller@jku.at>

import csv
import io
import logging
import os

logging.basicConfig()
logger = logging.getLogger(__name__)

SWEEP = 0
CONTINUOUS = 1


class DataLogger:
    def __init__(self):
        self.index = 0
        self.data = []
        self.mode = None

    def clear(self):
        self.index = 0
        self.data.clear()

    def append_sweep(self, sweep_data):
        if self.mode != SWEEP:
            logger.debug("switching modes - clearing data logger")
            self.clear()
            self.mode = SWEEP
        for point in sweep_data:
            point["index"] = self.index
        self.data.append(sweep_data)
        self.index += 1

    def append_continuous(self, continuous_data):
        if self.mode != CONTINUOUS:
            logger.debug("switching modes - clearing data logger")
            self.clear()
            self.mode = CONTINUOUS
        for point in continuous_data:
            point["index"] = self.index
        self.data.append(continuous_data)
        self.index += 1

    def export_to_file(self, filename):
        with open(filename, "w") as fh:
            self._csv(fh)
            os.fsync(fh.fileno())

    def export_to_string(self):
        with io.StringIO() as buf:
            self._csv(buf)
            # limit to first 10000 values for performance reasons
            text = buf.getvalue()[:10000]

        return text

    def _csv(self, fh):
        if self.mode == SWEEP:
            fields = ("index", "f", "magnitude", "phase")
        elif self.mode == CONTINUOUS:
            fields = ("index", "f", "t", "magnitude", "phase", "T")
        if self.data:
            writer = csv.DictWriter(fh, fieldnames=fields)
            writer.writeheader()
            for series in self.data:
                for point in series:
                    writer.writerow(point)
