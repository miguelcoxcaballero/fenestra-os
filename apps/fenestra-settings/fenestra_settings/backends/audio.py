"""PipeWire audio through wpctl."""
from __future__ import annotations

import re

from .. import util


class Node:
    def __init__(self, nid, name, volume, default, muted=False):
        self.id, self.name, self.volume, self.default, self.muted = nid, name, volume, default, muted

    def __repr__(self):
        return f"<Node {self.id} {self.name} {self.volume} {'*' if self.default else ''}>"


def available() -> bool:
    if util.DEMO:
        return True
    return util.have("wpctl")


def parse_status(text: str):
    """Return (sinks, sources) lists of Node from `wpctl status` output (Audio section)."""
    sinks, sources = [], []
    section = None
    in_audio = False
    for raw in text.splitlines():
        line = raw.replace("│", " ").replace("├", " ").replace("└", " ").replace("─", " ")
        s = line.strip()
        if not raw.startswith(" ") and s:
            in_audio = s.startswith("Audio")
            section = None
            continue
        if not in_audio:
            continue
        if s.endswith(":") and not re.match(r"^\*?\s*\d+\.", s):
            section = s[:-1].strip().lower()
            continue
        m = re.match(r"^(\*)?\s*(\d+)\.\s+(.+?)(?:\s+\[vol:\s*([\d.]+)(\s+MUTED)?\])?\s*$", s)
        if not m or section not in ("sinks", "sources"):
            continue
        node = Node(int(m.group(2)), m.group(3).strip(), float(m.group(4) or 1.0),
                    bool(m.group(1)), bool(m.group(5)))
        (sinks if section == "sinks" else sources).append(node)
    return sinks, sources


def status(callback):
    """callback(sinks, sources) or ([], []) when unavailable."""
    if util.DEMO:
        from . import demo
        demo.later(callback, *demo.audio())
        return
    def done(ok, out, _err):
        if not ok:
            callback([], [])
            return
        callback(*parse_status(out))
    util.run_async(["wpctl", "status"], done)


def pretty_name(name: str) -> str:
    # "Meteor Lake-P HD Audio Controller Speaker" -> "Speaker (Meteor Lake-P HD Audio Controller)"
    for kind in ("Speaker", "Headphones", "Headset", "Digital Microphone", "Stereo Microphone",
                 "Microphone", "Line Out", "Analog Stereo", "Digital Stereo"):
        if name.endswith(" " + kind):
            return f"{kind} ({name[:-len(kind)].strip()})"
    m = re.match(r"^(.*?) (HDMI / DisplayPort \d+ Output)$", name)
    if m:
        return f"{m.group(2)} ({m.group(1)})"
    return name


def set_volume(node_id, fraction, callback=None):
    util.run_async(["wpctl", "set-volume", str(node_id), f"{max(0.0, min(1.5, fraction)):.2f}"],
                   callback, mutating=True)


def set_mute(node_id, mute: bool, callback=None):
    util.run_async(["wpctl", "set-mute", str(node_id), "1" if mute else "0"], callback, mutating=True)


def set_default(node_id, callback=None):
    util.run_async(["wpctl", "set-default", str(node_id)], callback, mutating=True)
