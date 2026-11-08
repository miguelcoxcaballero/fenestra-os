# SPDX-License-Identifier: GPL-3.0-or-later
"""Adaptive color (System › Display): the screen's white point follows the ambient light.

Fenestra Shell does the work (shell/src/services/adaptivecolor.h): it reads an ambient light
sensor that reports colour and tints the screen through KWin's Night light pipeline. Settings
only stores the switch, ``[Display] AdaptiveColor`` in shell.conf (on unless turned off, as in
Windows on devices with a colour sensor), and shows it only where such a sensor exists: an IIO
device with in_chromaticity_x/y or in_colortemp (``FENESTRA_ALS_PATH`` points at a fake tree in
tests, as for the shell).
"""
from __future__ import annotations

import os

from . import shellconf

KEY = "Display/AdaptiveColor"
IIO = "/sys/bus/iio/devices"


def _colour(d: str) -> bool:
    def ok(n):
        return os.access(os.path.join(d, n), os.R_OK)
    return (ok("in_chromaticity_x_raw") and ok("in_chromaticity_y_raw")) or ok("in_colortemp_raw") \
        or ok("in_colortemp_input")


def sensor() -> str | None:
    """Directory of the first colour-capable ambient light sensor, or None."""
    root = os.environ.get("FENESTRA_ALS_PATH") or IIO
    if _colour(root):
        return root
    try:
        names = sorted(n for n in os.listdir(root) if n.startswith("iio:device"))
    except OSError:
        return None
    for n in names:
        if _colour(os.path.join(root, n)):
            return os.path.join(root, n)
    return None


def supported() -> bool:
    return sensor() is not None


def enabled() -> bool:
    return shellconf.get_bool(KEY, True)


def set_enabled(on: bool) -> bool:
    return shellconf.set(KEY, bool(on))
