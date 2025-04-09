---
title: Impedance measurement device manual
subtitle: Version 1.1
author: David Schiller
lang: en-US
documentclass: scrartcl
classoption:
    - 10pt
papersize: a5
mainfont: STIX Two Text
mathfont: STIX Two Math
sansfont: Source Sans Pro
monofont: Source Code Pro
toc: true
colorlinks: false
urlstyle: tt
header-includes: |
    ```{=latex}
    \usepackage{siunitx}
    \KOMAoptions{headings=standardclasses,DIV=10}
    ```
---

\thispagestyle{empty}
\newpage
\KOMAoptions{twoside=true,DIV=calc,BCOR=12mm}

# Introduction

![Photo of the device with control terminal and attached measurement
board](images/photo_new.jpg){width=60%}

The device is a combination of an industrial computer in the form of a
"Seeedstudio reTerminal" and a custom PCB with impedance and temperature
measurement capability. Unknown complex impedances (magnitude and phase) can be
characterized via frequency sweeps or continuous measurements at a fixed
frequency over time. The Analog Devices AD5933 IC is used for impedance
conversion and a Microchip MCP9600 serves as a thermocouple interface.

# Technical specifications

\enlargethispage*{\baselineskip}
* 5" $1280 \times 720$ capacitive touchscreen
* networking capability via Ethernet and Wi-Fi
* $\qty{32}{\giga\byte}$ of onboard storage
* two USB ports for external storage or other peripherals
* excitation frequency range: $\qtyrange{10}{100}{\kilo\hertz}$
* impedance measurement ranges by magnitude (based on estimates):
  - 1: $\qtyrange{15}{675}{\ohm}$
  - 2: $\qtyrange{1}{45}{\kilo\ohm}$
  - 3: $\qtyrange{100}{450}{\kilo\ohm}$
  - 4: $> \qty{1}{\mega\ohm}$
* thermocouple measurement accuracy: $\qty{+-1.5}{\celsius}$
* thermocouple measurement resolution: $\qty{0.0625}{\celsius}$

\pagebreak

# Basic operation

## Overview

You can turn on the device by pressing the button on the top left. A cold boot
should take around 15 seconds. You will be greeted with a touch-enabled user
interface grouped into five tabs:

1. *Sweep*: for frequency sweeps. The plot shows magnitude and phase over
   frequency.
2. *Continuous*: for continuous measurements. The plot shows magnitude over time
   at a fixed frequency.
3. *Setup*: provides a way to set parameters for both measurement modes. This
   includes
   * measurement range
   * start frequency
   * frequency increment
   * number of increments
4. *Export*: for saving acquired measurement data to disk
5. *Debug*: technical info helpful for troubleshooting

The front buttons labeled "F1", "F2" and "F3" allow quick switching between the
first three tabs. The green button is a shortcut for starting a measurement and
works both in sweep and continuous modes.

## Plot settings

These settings are largely the same between the two modes. You can select
between linear and logarithmic scaling for the vertical axis. By default, axis
scaling is performed automatically based on the measured data. You can override
this behavior by unchecking "Auto-scale" and setting the desired "y-min" and
"y-max" values. This comes into effect after the next measurement.

## Measurements

Before you can start a measurement, you have to perform a calibration step. The
terminals have to be left unconnected (floating) during this process. After
hitting "Calibrate current range", the currently selected range will be
calibrated using onboard calibration resistors. This process usually takes less
than ten seconds. From here on out, the calibration values reside in memory,
meaning re-calibration is necessary after power cycling the device. If you
desire the best accuracy, you should first wait for the device to warm up and
then periodically perform calibrations in between measurements. The latter is
especially important, if the ambient temperature is not stable.

### Sweep measurements

![Screenshot of the "Sweep" tab --- the plot scale can be adjusted with the
controls on top](images/sweep_data.png){width=75%}

Select the sweep parameters and the desired range in the "Setup" tab, before
hitting "Measure" or pushing the green button. The plot will show both magnitude
and phase over a logarithmically-scaled frequency axis. See "[Plot settings]"
for parameters affecting the y-axis.

### Continuous measurements

![Screenshot of the "Continuous" tab --- the "Measure" button is replaced with a
"Start / Stop" button](images/continuous_data.png){width=75%}

As before, you can set the measurement parameters in the "Setup" tab. The "Start
frequency" parameter from the sweep settings doubles as the fixed measurement
frequency in this mode. In contrast to the sweep mode, which is a one-shot
measurement, the continuous measurement has to be stopped explicitly --- either
via touch control or the physical button. The plot will also update as new data
is acquired. Because this is a potentially long-running process, the drawing and
measurement steps are offloaded to separate background threads. This means, that
you can navigate to a different tab, while the measurement continues to run.
This makes it possible to check the log for errors in the "Debug" tab, for
instance.

## Exporting data

![Screenshot of the "Export" tab --- a CSV preview of the current buffer is
shown in the left image and the file picker is shown in the right
image](images/export_both.png){width=100%}

The following is a general explanation of the data acquisition process. Repeated
measurements are saved to a temporary buffer located in memory. Individual
measurement series are tagged with an index that starts at zero and is
incremented by one for each series. The buffer is cleared in two situations:

* The user selects "Clear measurement" in the "Export tab".
* The user switches between one of the two measurement modes and initiates a new
  measurement --- only one type of data can reside in the buffer at the same
  time.

The "Export" tab features a preview of said buffer in CSV format and allows
writing the data to a file. The available columns shown in the preview depend on
the measurement mode. The above-mentioned index is represented as a separate
column and is always present.

At this point one can optionally mount an external drive with the "Mount USB
drive" button. The next step in the export process is to toggle to the file
dialog and select a target directory and file name. The starting directory in
this dialog is either a local directory or the root of an external drive,
depending on whether one was mounted in the previous step. Hit "Save" to write
the file and complete the process. Afterwards you can unmount the external
drive, if present, and/or clear the buffer.

# Advanced topics

## Measuring at low excitation frequencies

The AD5933 has an internal, fixed clock source running at $\qty{16}{\MHz}$. The
accuracy figures from the data sheet have been derived in this mode of
operation. Unfortunately, this has the side effect of severely limiting low
excitation frequency measurement performance, due to artifacts arising in the
DFT engine when clocked at this comparatively high rate. It is however possible
to connect an external clock signal to one of the AD5933's pins to mitigate this
issue. In the current revision of this device this is accomplished by dividing
down the crystal oscillator signal from the connected terminal and then feeding
it to the AD5933.

In effect this means that if you want to measure at frequencies lower than
around $\qty{3}{\kHz}$, you will have to lower the clock frequency from the
startup default of $\qty{9}{\MHz}$. The parameters in the following table
should ensure an accuracy of about $\pm \qty{5}{\percent}$.

| Clock frequency | Lower excitation frequency |
|----------------:|---------------------------:|
|           9 MHz |                      3 kHz |
|        2.25 MHz |                      1 kHz |
|        1.25 MHz |                     500 Hz |
|       281250 Hz |                     200 Hz |
|       140625 Hz |                     100 Hz |
|        22500 Hz |                      70 Hz |

: Clock frequencies and associated lower excitation frequency limits

It is not possible to generate clock frequencies below $\qty{22.5}{\kHz}$. For
the best possible phase accuracy you should stick to frequencies that can be
integer divided from $\qty{54}{\MHz}$ (Raspberry Pi crystal oscillator) without
remainder:

$$ f_\mathrm{clk} = \frac{f_\mathrm{osc}}{n} $$
$$ f_\mathrm{osc} \bmod n = 0 $$

This is because integer division yields the least amount of clock jitter. Keep
in mind that there is no one single clock frequency that can cover all frequency
ranges. For instance, at the lowest possible clock frequency, you have a useful
bandwidth of $\qtyrange{70}{1000}{\Hz}$. If you desire a wideband spectrum, you
have to split it into multiple sweeps with calibrations in between.

## Remote control via SSH

After you have established a network connection, you can connect to the device
via SSH. This enables you to transfer files from the internal storage or run the
GUI on your local machine using X11 forwarding. Assuming the device has
"10.0.0.2" as its IP address --- check the "Debug" tab for the currently
assigned address --- you can type the following to connect to it:

```sh
ssh -XC wood@10.0.0.2
```

The password is "knock". After establishing a connection, you can type:

```sh
start-gui -x
```

This will pop up a new window with the measurement GUI on your local machine.
The behavior is exactly identical to the touchscreen on the device itself, with
the added benefit of being able to resize the window, as well as having a
physical keyboard. Once you are done, just type "exit" at the prompt to close
the connection.

For file transfer you can use the "sftp" program or graphical file managers like
"FileZilla" or "WinSCP".

### Additional steps for Windows users

The process as described above assumes you have a working X server setup, which
is the case by default on Linux and is easily enabled on macOS. For Windows
users the quickest path is to set up "Windows Subsystem for Linux" (WSL) ---
notably version two.

On recent Windows versions (later versions of Windows 10, Windows 11) you can
open up a PowerShell prompt and then execute the following command:

```powershell
wsl --install
```

You will be prompted for a username and password along the way. If the command
finishes successfully, you should be able to find a "WSL" item in the start
menu. This will launch a shell in the WSL environment and from hereon out the
steps are identical to what is described above.

If you encounter any problems, please refer to the documentation provided by
Microsoft:

<https://learn.microsoft.com/en-us/windows/wsl/install>
