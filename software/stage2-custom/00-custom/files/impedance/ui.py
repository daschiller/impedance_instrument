# SPDX-License-Identifier: GPL-3.0-only

# Copyright (c) 2024 David Schiller <david.schiller@jku.at>

import logging
import os
import re
import subprocess
import time
from queue import Queue
from textwrap import dedent
from threading import Timer
from time import sleep
from traceback import format_exception

from matplotlib import style

from matplotlib.backends.backend_qt5agg import FigureCanvas
from matplotlib.figure import Figure
from PySide2 import QtCore, QtGui, QtWidgets

from ad5933 import AD5933
from export import DataLogger
from mcp9600 import MCP9600

logging.basicConfig()
logger = logging.getLogger(__name__)

BLOCKDEV = "/dev/sda1"
PLOT_PHASE = True
PLOT_TEMPERATURE = True
TCOUPLE_FILTER = 2
CONTINUOUS_INTERVAL = 1
EXPORT_INDEX = 3


class Params:
    clock = {"rate": None}
    sweep = {"start": 10000, "increment": 1000, "points": 90}


class SweepWidget(QtWidgets.QWidget):
    def __init__(self, impedance: AD5933, data_logger: DataLogger):
        super().__init__()
        self.impedance = impedance
        self.data_logger = data_logger
        self.params = Params()
        style.use("bmh")
        self.figure_canvas = FigureCanvas(Figure(tight_layout=False, dpi=180))
        self.figure_canvas.setStyleSheet("background-color: transparent;")
        self.figure_canvas.figure.patch.set_facecolor("none")
        self.cal_button = QtWidgets.QPushButton("Calibrate current range")
        self.meas_button = QtWidgets.QPushButton("Measure")
        self.meas_button.setAutoDefault(True)
        self.scale_check = QtWidgets.QCheckBox(
            "Auto-scale",
        )
        self.scale_check.setChecked(True)
        self.log_check = QtWidgets.QCheckBox("Log y-scale")
        self.log_check.setChecked(False)
        self.ymin_text = QtWidgets.QLabel("y-axis min:")
        self.ymin_text.setAlignment(QtCore.Qt.AlignRight | QtCore.Qt.AlignVCenter)
        self.ymin_box = QtWidgets.QSpinBox()
        self.ymin_box.setEnabled(False)
        self.ymin_box.setRange(0, 2 ** 31 - 1)
        self.ymax_text = QtWidgets.QLabel("y-axis max:")
        self.ymax_text.setAlignment(QtCore.Qt.AlignRight | QtCore.Qt.AlignVCenter)
        self.ymax_box = QtWidgets.QSpinBox()
        self.ymax_box.setEnabled(False)
        self.ymax_box.setRange(0, 2 ** 31 - 1)

        self.vbox = QtWidgets.QVBoxLayout()
        self.check_hbox = QtWidgets.QHBoxLayout()
        self.check_hbox.addWidget(self.scale_check)
        self.check_hbox.addWidget(self.log_check)
        self.check_hbox.addWidget(self.ymin_text)
        self.check_hbox.addWidget(self.ymin_box)
        self.check_hbox.addWidget(self.ymax_text)
        self.check_hbox.addWidget(self.ymax_box)
        self.hbox = QtWidgets.QHBoxLayout()
        self.hbox.addWidget(self.cal_button)
        self.hbox.addWidget(self.meas_button)
        self.vbox.addLayout(self.check_hbox)
        self.vbox.addWidget(self.figure_canvas)
        self.vbox.addLayout(self.hbox)
        self.setLayout(self.vbox)

        self.cal_button.clicked.connect(self.calibrate)
        self.meas_button.clicked.connect(self.measure)
        self.scale_check.stateChanged.connect(self.toggle_range)

    @QtCore.Slot()
    def toggle_range(self, value):
        self.ymin_box.setEnabled(not value)
        self.ymax_box.setEnabled(not value)

    @QtCore.Slot()
    def measure(self):
        if not self.impedance.gain_parameters[self.impedance.range]:
            QtWidgets.QMessageBox.critical(
                self,
                "Error",
                "Selected range is not calibrated.",
            )
            logger.warning("not calibrated")
            return
        logger.debug(f"starting sweep: {self.params.sweep}")
        data = self.impedance.sweep(
            self.params.sweep["start"],
            self.params.sweep["increment"],
            self.params.sweep["points"],
        )
        logger.debug("sweep finished")
        self.data_logger.append_sweep(data)
        fig = self.figure_canvas.figure
        fig.clear()
        ax = fig.subplots()
        ax.plot([i["f"] for i in data], [i["magnitude"] for i in data], label="|Z|")
        ax.set_xlabel("f / Hz", labelpad=0, fontsize="medium")
        ax.set_ylabel("|Z| / Ω", labelpad=0, fontsize="medium")
        ax.set_xscale("log")
        ax.margins(y=1)
        ax.set_ylim(bottom=0, auto=True)
        if self.log_check.checkState():
            ax.set_yscale("log")
        if not self.scale_check.checkState():
            ax.set_ylim(self.ymin_box.value(), self.ymax_box.value())

        legend_args = {
            "loc": "upper right",
            "bbox_to_anchor": (0.875, 0.95),
            "facecolor": "white",
            "framealpha": 1,
        }
        if PLOT_PHASE:
            ax2 = ax.twinx()
            ax2.grid(visible=False)
            ax2.set_ylabel("φ / °")
            ax2.plot(
                [i["f"] for i in data],
                [i["phase"] for i in data],
                label="φ",
                color="C1",
            )
            fig.legend(**legend_args)
        else:
            ax.legend()

        self.figure_canvas.draw()

    @QtCore.Slot()
    def calibrate(self):
        logger.debug("starting calibration")
        self.impedance.clock_frequency = self.params.clock["rate"]
        self.impedance.cal_range(self.impedance.range)
        logger.debug("calibration finished")


class ContinuousWidget(QtWidgets.QWidget):
    def __init__(self, impedance: AD5933, thermo: MCP9600, data_logger: DataLogger):
        super().__init__()
        self.impedance = impedance
        self.thermo = thermo
        self.data_logger = data_logger
        self.params = Params()
        self.running = False
        style.use("bmh")
        self.figure_canvas = FigureCanvas(Figure(tight_layout=False, dpi=180))
        self.figure_canvas.setStyleSheet("background-color: transparent;")
        self.figure_canvas.figure.patch.set_facecolor("none")
        self.cal_button = QtWidgets.QPushButton("Calibrate current range")
        self.start_button = QtWidgets.QPushButton("Start / Stop")
        self.start_button.setAutoDefault(True)
        self.scale_check = QtWidgets.QCheckBox(
            "Auto-scale",
        )
        self.scale_check.setChecked(True)
        self.log_check = QtWidgets.QCheckBox("Log y-scale")
        self.log_check.setChecked(False)
        self.ymin_text = QtWidgets.QLabel("y-axis min:")
        self.ymin_text.setAlignment(QtCore.Qt.AlignRight | QtCore.Qt.AlignVCenter)
        self.ymin_box = QtWidgets.QSpinBox()
        self.ymin_box.setEnabled(False)
        self.ymin_box.setRange(0, 2 ** 31 - 1)
        self.ymax_text = QtWidgets.QLabel("y-axis max:")
        self.ymax_text.setAlignment(QtCore.Qt.AlignRight | QtCore.Qt.AlignVCenter)
        self.ymax_box = QtWidgets.QSpinBox()
        self.ymax_box.setEnabled(False)
        self.ymax_box.setRange(0, 2 ** 31 - 1)

        self.vbox = QtWidgets.QVBoxLayout()
        self.check_hbox = QtWidgets.QHBoxLayout()
        self.check_hbox.addWidget(self.scale_check)
        self.check_hbox.addWidget(self.log_check)
        self.check_hbox.addWidget(self.ymin_text)
        self.check_hbox.addWidget(self.ymin_box)
        self.check_hbox.addWidget(self.ymax_text)
        self.check_hbox.addWidget(self.ymax_box)
        self.hbox = QtWidgets.QHBoxLayout()
        self.hbox.addWidget(self.cal_button)
        self.hbox.addWidget(self.start_button)
        self.vbox.addLayout(self.check_hbox)
        self.vbox.addWidget(self.figure_canvas)
        self.vbox.addLayout(self.hbox)
        self.setLayout(self.vbox)

        self.cal_button.clicked.connect(self.calibrate)
        self.start_button.clicked.connect(self.start_stop)
        self.scale_check.stateChanged.connect(self.toggle_range)

    @QtCore.Slot()
    def toggle_range(self, value):
        self.ymin_box.setEnabled(not value)
        self.ymax_box.setEnabled(not value)

    class _Measure(QtCore.QRunnable):
        def __init__(self, continuous, ax, ax2):
            super().__init__()
            self.ax = ax
            self.ax2 = ax2
            self.continuous = continuous
            self.figure_canvas = continuous.figure_canvas
            self.impedance = continuous.impedance
            self.thermo = continuous.thermo
            self.data_logger = continuous.data_logger
            self.params = Params()

        def run(self):
            logger.debug("starting measurement thread")
            queue = Queue()
            t0 = time.monotonic()
            t, Z, phi, T = [], [], [], []

            def redraw(Z_line, T_artist):
                t_, Z_, phi_, T_ = queue.get(timeout=30)
                t.append(t_)
                Z.append(Z_)
                T.append(T_)
                phi.append(phi_)
                Z_line.set_data([(t - t0) / 60 for t in t], Z)
                self.ax.relim()
                self.ax.autoscale_view()
                if PLOT_TEMPERATURE:
                    T_artist.set_data([(t - t0) / 60 for t in t], T)
                    self.ax2.relim()
                    self.ax2.autoscale_view()
                else:
                    T_artist.set_text(
                        f"T = {T_:6.2f} ℃",
                    )
                try:
                    self.figure_canvas.draw()
                except RuntimeError:
                    # suppress the following on SIGINT:
                    # "Internal C++ object (FigureCanvasQTAgg) already deleted."
                    pass

            def acquire():
                t = time.monotonic()
                T = self.thermo.temp
                magnitude, phase = self.impedance.measure(self.params.sweep["start"])
                queue.put((t, magnitude, phase, T), timeout=5)

            (Z_line,) = self.ax.plot((), label="|Z|", color="C0")
            if PLOT_TEMPERATURE:
                (T_artist,) = self.ax2.plot((), label="T", color="C1")
            else:
                T_artist = self.ax.text(
                    *(0.8, 0.9),
                    "",
                    transform=self.ax.transAxes,
                )
            # first acquiration
            acquire()
            redraw(Z_line, T_artist)
            while self.continuous.running:
                # schedule another acquiration in t_remaining
                t_remaining = max(0, t[-1] + CONTINUOUS_INTERVAL - time.monotonic())
                Timer(t_remaining, acquire).start()
                redraw(Z_line, T_artist)
            self.data_logger.append_continuous(
                [
                    {
                        "f": self.params.sweep["start"],
                        "t": round(t - t0, 3),
                        "magnitude": Z,
                        "phase": phi,
                        "T": T,
                    }
                    for t, Z, phi, T in zip(t, Z, phi, T)
                ]
            )
            logger.debug("stopping measurement thread")

    @QtCore.Slot()
    def start_stop(self):
        if not self.impedance.gain_parameters[self.impedance.range]:
            QtWidgets.QMessageBox.critical(
                self,
                "Error",
                "Selected range is not calibrated.",
            )
            logger.warning("not calibrated")
            return
        if not self.running:
            logger.debug(
                f"starting continuous measurement: {self.params.sweep['start']} Hz"
            )
            fig = self.figure_canvas.figure
            fig.clear()
            fig.suptitle(f"Frequency: {self.params.sweep['start']} Hz")
            ax = fig.subplots()
            if PLOT_TEMPERATURE:
                ax2 = ax.twinx()
                ax2.set_ylabel("T / ℃", labelpad=2, fontsize="medium")
                ax2.grid(visible=False)
                ax2.set_ylim(bottom=0, auto=True)
            else:
                ax2 = None
            ax.set_xlabel("t / min", labelpad=1, fontsize="medium")
            ax.set_ylabel("|Z| / Ω", labelpad=2, fontsize="medium")
            ax.margins(y=1)
            ax.set_xlim(left=0, auto=True)
            ax.set_ylim(bottom=0, auto=True)
            if self.log_check.checkState():
                ax.set_yscale("log")
            if not self.scale_check.checkState():
                ax.set_ylim(self.ymin_box.value(), self.ymax_box.value())
            thread_pool = QtCore.QThreadPool.globalInstance()
            runnable = self._Measure(self, ax, ax2)
            thread_pool.start(runnable)
            self.running = True

        else:
            logger.debug("stopping continuous measurement")
            self.running = False

    @QtCore.Slot()
    def calibrate(self):
        logger.debug("starting calibration")
        self.impedance.clock_frequency = self.params.clock["rate"]
        self.impedance.cal_range(self.impedance.range)
        logger.debug("calibration finished")

    def closeEvent(self, event):
        self.running = False
        event.accept()


class RangeWidget(QtWidgets.QWidget):
    def __init__(self, impedance: AD5933):
        super().__init__()
        self.params = Params()
        self.impedance = impedance
        self.range_text = QtWidgets.QLabel("Measurement range:")
        self.range_dropdown = QtWidgets.QComboBox()
        self.range_dropdown.addItems(["1", "2", "3", "4"])
        self.clock_text = QtWidgets.QLabel("Clock frequency (takes effect upon next calibration):")
        self.clock_box = QtWidgets.QSpinBox()
        self.clock_box.setRange(22500, 9e6)
        self.range_description = QtWidgets.QLabel(
            dedent(
                """\
            Usable impedance range
            (diminished accuracy beyond upper limits, only rough estimates):
            #1: 15 Ω - 675 Ω
            #2: 1000 Ω - 45 kΩ
            #3: 100 kΩ - 450 kΩ
            #4: > 1 MΩ\
            """
            )
        )
        self.range_description.setFont(QtGui.QFont("sans", 9))

        self.layout = QtWidgets.QVBoxLayout()
        self.form_layout = QtWidgets.QFormLayout()
        self.form_layout.addRow(self.range_text, self.range_dropdown)
        self.form_layout.addRow(self.clock_text, self.clock_box)
        self.layout.addLayout(self.form_layout)
        self.layout.addWidget(self.range_description)
        self.setLayout(self.layout)

        self.params.clock["rate"] = self.impedance.clock_frequency
        self.clock_box.setValue(self.params.clock["rate"])
        self.range_dropdown.textActivated.connect(self.select_range)
        self.clock_box.valueChanged.connect(self.set_clock)

    @QtCore.Slot()
    def select_range(self, range_no):
        self.impedance.range = int(range_no)
        logger.debug(f"set range to {range_no}")

    @QtCore.Slot()
    def set_clock(self, clock):
        self.params.clock["rate"] = clock
        logger.debug(f"set clock to {clock}")

    @QtCore.Slot()
    def update(self, index):
        self.range_dropdown.setCurrentIndex = self.impedance.range - 1


class SweepSettingsWidget(QtWidgets.QWidget):
    def __init__(self, impedance: AD5933):
        super().__init__()
        self.params = Params()
        self.impedance = impedance
        self.start_text = QtWidgets.QLabel("Start frequency (Hz):")
        self.start_box = QtWidgets.QSpinBox()
        self.start_box.setRange(1, 100000)
        self.increment_text = QtWidgets.QLabel("Frequency increment (Hz):")
        self.increment_box = QtWidgets.QSpinBox()
        self.increment_box.setRange(1, 100000)
        self.points_text = QtWidgets.QLabel("Number of points in sweep:")
        self.points_box = QtWidgets.QSpinBox()
        self.points_box.setRange(1, 511)

        self.layout = QtWidgets.QFormLayout()
        self.layout.addRow(self.start_text, self.start_box)
        self.layout.addRow(self.increment_text, self.increment_box)
        self.layout.addRow(self.points_text, self.points_box)

        self.setLayout(self.layout)

        self.start_box.setValue(self.params.sweep["start"])
        self.increment_box.setValue(self.params.sweep["increment"])
        self.points_box.setValue(self.params.sweep["points"])
        self.start_box.valueChanged.connect(self.set_start)
        self.increment_box.valueChanged.connect(self.set_increment)
        self.points_box.valueChanged.connect(self.set_points)

    @QtCore.Slot()
    def set_start(self, value):
        self.params.sweep["start"] = value

    @QtCore.Slot()
    def set_increment(self, value):
        self.params.sweep["increment"] = value

    @QtCore.Slot()
    def set_points(self, value):
        self.params.sweep["points"] = value


class SetupWidget(QtWidgets.QWidget):
    def __init__(self, impedance: AD5933):
        super().__init__()
        self.impedance = impedance
        self.range_group = QtWidgets.QGroupBox("Range")
        self.sweep_group = QtWidgets.QGroupBox(
            "Sweep settings (start frequency also applies to continuous mode)"
        )
        self.range_widget = RangeWidget(impedance)
        self.sweep_widget = SweepSettingsWidget(impedance)

        self.vbox = QtWidgets.QVBoxLayout()
        self.range_group.setLayout(self.range_widget.layout)
        self.sweep_group.setLayout(self.sweep_widget.layout)
        self.vbox.addWidget(self.range_group)
        self.vbox.addWidget(self.sweep_group)
        self.setLayout(self.vbox)


class CustomFileDialog(QtWidgets.QFileDialog):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.setDefaultSuffix("csv")
        self.setAcceptMode(QtWidgets.QFileDialog.AcceptSave)
        for button in self.findChildren(QtWidgets.QPushButton):
            button.clicked.disconnect()
            if button.text() == "&Save":
                button.clicked.connect(self.save)

    def save(self):
        if self.selectedFiles():
            return self.selectedFiles()[0]


class ExportWidget(QtWidgets.QWidget):
    def __init__(self, impedance: AD5933, data_logger: DataLogger):
        super().__init__()
        self.impedance = impedance
        self.data_logger = data_logger
        self.preview_box = QtWidgets.QTextEdit()
        self.preview_box.setReadOnly(True)
        try:
            if os.environ["QT_QPA_PLATFORM"] == "eglfs":
                self.preview_box.setTextInteractionFlags(QtCore.Qt.NoTextInteraction)
                self.preview_box.setFont(QtGui.QFont("monospace", 6))
            else:
                self.preview_box.setFont(QtGui.QFont("monospace"))
        except KeyError:
            self.preview_box.setFont(QtGui.QFont("monospace"))

        self.clear_button = QtWidgets.QPushButton("Clear measurements")
        self.file_button = QtWidgets.QPushButton(
            "Toggle between file dialog and preview"
        )
        self.mount_button = QtWidgets.QPushButton("Mount / Unmount USB drive")
        self._check_mounted()
        self.file_picker = QtWidgets.QFileDialog(
            caption="Export to CSV",
            directory=os.path.expanduser("~/data"),
            filter="*.csv",
        )
        self.file_picker.setDefaultSuffix("csv")
        self.file_picker.setAcceptMode(QtWidgets.QFileDialog.AcceptSave)
        self.file_picker.setVisible(False)

        self.vbox = QtWidgets.QVBoxLayout()
        self.vbox.addWidget(self.clear_button)
        self.vbox.addWidget(self.preview_box)
        self.vbox.addWidget(self.file_picker)
        self.vbox.addWidget(self.file_button)
        self.vbox.addWidget(self.mount_button)
        self.setLayout(self.vbox)

        self.clear_button.clicked.connect(self.clear_measurements)
        self.file_button.clicked.connect(self.show_hide_dialog)
        self.mount_button.clicked.connect(self.mount_unmount)
        self.file_picker.fileSelected.connect(self.save)

    @QtCore.Slot()
    def update(self, index):
        # TODO: make this more elegant
        if index == EXPORT_INDEX:
            self.preview_box.setText(self.data_logger.export_to_string())

    @QtCore.Slot()
    def clear_measurements(self):
        self.data_logger.clear()
        # TODO: make this more elegant
        self.update(EXPORT_INDEX)

    @QtCore.Slot()
    def show_hide_dialog(self):
        dialog_hidden = self.file_picker.isHidden()
        self.file_picker.setVisible(dialog_hidden)
        self.preview_box.setVisible(not dialog_hidden)

    @QtCore.Slot()
    def mount_unmount(self):
        if not self._check_mounted():
            out = subprocess.run(
                ["udisksctl", "mount", "-b", BLOCKDEV], capture_output=True, text=True
            )
            if out.returncode == 0:
                path = re.search(r"at (\S+)", out.stdout).group(1)
                self.file_picker.setDirectory(path)
                logger.debug(f"udisksctl: {out.stdout[:-1]}")
        else:
            out = subprocess.run(
                ["udisksctl", "unmount", "-b", BLOCKDEV], capture_output=True, text=True
            )
            if out.returncode == 0:
                self.file_picker.setDirectory(os.path.expanduser("~/data"))
                logger.debug(f"udisksctl: {out.stdout[:-1]}")
        self._check_mounted()

    def _check_mounted(self):
        if subprocess.run(["findmnt", BLOCKDEV], capture_output=True).returncode != 0:
            self.mount_button.setText("Mount USB drive")
            return False
        else:
            self.mount_button.setText("Unmount USB drive")
            return True

    @QtCore.Slot()
    def save(self, filename):
        logger.debug(f"exporting to {filename}")
        self.data_logger.export_to_file(filename)
        self.show_hide_dialog()


class DebugWidget(QtWidgets.QWidget):
    def __init__(self, impedance: AD5933):
        super().__init__()
        self.impedance = impedance
        self.text_box = QtWidgets.QTextEdit()
        self.text_box.setReadOnly(True)
        try:
            if os.environ["QT_QPA_PLATFORM"] == "eglfs":
                self.text_box.setTextInteractionFlags(QtCore.Qt.NoTextInteraction)
                self.text_box.setFont(QtGui.QFont("monospace", 6))
            else:
                self.text_box.setFont(QtGui.QFont("monospace"))
        except KeyError:
            self.text_box.setFont(QtGui.QFont("monospace"))

        self.layout = QtWidgets.QVBoxLayout()
        self.layout.addWidget(self.text_box)
        self.setLayout(self.layout)

    @QtCore.Slot()
    def update(self, index):
        # TODO: make this more elegant
        if index == 3:
            command = dedent(
                r"""\
            show(){
                local _NAME="$*"
                echo "$_NAME"
                for _ in $(seq "${#_NAME}"); do
                   printf '%s' =
                done
                printf '\n'
                eval "$@"
                printf '\n'
            }
            commands(){
                show systemctl status impedance
                show uptime
                show ip address show dev wlan0
                show /sbin/iwconfig wlan0
                show journalctl -b -n 10 -p warning
            }
            if command -v aha >/dev/null; then
                SYSTEMD_COLORS=1 commands | aha -n -x | sed 'a <br/>'
            else
                commands
            fi
            """
            )
            out = subprocess.run("sh", capture_output=True, text=True, input=command)
            if out.stderr:
                logger.debug(f"shell stderr: {out.stderr}")
            self.text_box.setHtml(out.stdout)


class MainWidget(QtWidgets.QTabWidget):
    def __init__(self):
        super().__init__()
        self.impedance = AD5933()
        self.thermo = MCP9600()
        # for _ in range(5):
        #     try:
        #         self.thermo.enable_filter(TCOUPLE_FILTER)
        #         logger.debug(f"setting thermocouple filter to level {TCOUPLE_FILTER}")
        #         break
        #     except OSError:
        #         sleep(1)
        self.data_logger = DataLogger()
        self.sweep = SweepWidget(self.impedance, self.data_logger)
        self.continuous = ContinuousWidget(
            self.impedance, self.thermo, self.data_logger
        )
        self.setup = SetupWidget(self.impedance)
        self.export = ExportWidget(self.impedance, self.data_logger)
        self.debug = DebugWidget(self.impedance)
        self.sweep_shortcut = QtWidgets.QShortcut("F1", self)
        self.continuous_shortcut = QtWidgets.QShortcut("F2", self)
        self.setup_shortcut = QtWidgets.QShortcut("F3", self)
        self.trigger_shortcut = QtWidgets.QShortcut("F4", self)

        self.addTab(self.sweep, "Sweep")
        self.addTab(self.continuous, "Continuous")
        self.addTab(self.setup, "Setup")
        self.addTab(self.export, "Export")
        self.addTab(self.debug, "Debug")

        self.sweep_shortcut.activated.connect(self.sweep_pressed)
        self.continuous_shortcut.activated.connect(self.continuous_pressed)
        self.setup_shortcut.activated.connect(self.setup_pressed)
        self.trigger_shortcut.activated.connect(self.trigger_pressed)
        self.currentChanged.connect(self.setup.range_widget.update)
        self.currentChanged.connect(self.debug.update)
        self.currentChanged.connect(self.export.update)

    @QtCore.Slot()
    def sweep_pressed(self):
        self.setCurrentWidget(self.sweep)

    @QtCore.Slot()
    def continuous_pressed(self):
        self.setCurrentWidget(self.continuous)

    @QtCore.Slot()
    def setup_pressed(self):
        self.setCurrentWidget(self.setup)

    @QtCore.Slot()
    def trigger_pressed(self):
        if self.currentWidget() is self.sweep:
            self.sweep.meas_button.animateClick(0)
        elif self.currentWidget() is self.continuous:
            self.continuous.start_button.animateClick(1000)

    def closeEvent(self, event):
        logger.debug("closing ...")
        self.continuous.close()
        event.accept()


if __name__ == "__main__":
    import signal
    import sys

    logger.setLevel(logging.DEBUG)
    logger.debug("starting Qt")
    app = QtWidgets.QApplication(sys.argv)
    window = QtWidgets.QWidget()
    try:
        widget = MainWidget()

        def exit_handler(signum, frame):
            widget.close()

        signal.signal(signal.SIGINT, exit_handler)
        signal.signal(signal.SIGTERM, exit_handler)

        widget.show()
        widget.setWindowTitle("i3Sense impedance measurement GUI")

        # periodically return to Python interpreter from event loop
        timer = QtCore.QTimer()
        timer.timeout.connect(lambda: None)
        timer.start(100)

        sys.exit(app.exec_())
    except BaseException as e:
        if isinstance(e, SystemExit):
            raise
        QtWidgets.QMessageBox.critical(
            window,
            "Critical error",
            "".join(format_exception(type(e), e, e.__traceback__)[-2:]),
        )
        sys.exit(1)
