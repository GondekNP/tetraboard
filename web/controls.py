"""UI control panel plumbing: pickers, PNG export, and save/load state.

This is the portal between the plain-HTML control panel in index.html and
whatever sketchingpy object graph main.py builds. It owns:
  * reading the current picker selections (string count, tuning, fret
    count, sharps/flats)
  * wiring the Export PNG / Save State / Load State controls to callbacks
    your own code registers

It deliberately knows nothing about Fret/String/Fretboard/Sketch2D. What to
export, what "state" means, and how string-count/tuning/fret-count map onto
your fretboard model are entirely up to whatever you register here -- see
DEVELOPING.md for how the pieces are meant to fit together.

Loaded once per page load (like devreload.py) and never re-run, so the
addEventListener calls in _bind() below only ever happen once. If this were
re-run on every main.py hot-swap the way main.py itself is, every save
would stack another set of click listeners on the same buttons.
"""

import json
import urllib.parse

import js
from pyodide.ffi import create_proxy

from config import AccidentalType

_STRING_COUNT_ID = "control-string-count"
_TUNING_ID = "control-tuning"
_FRET_COUNT_ID = "control-fret-count"
_ACCIDENTAL_TYPE_ID = "control-accidental-type"
_MODE_A_ID = "control-mode-a"
_MODE_B_ID = "control-mode-b"
_EXPORT_PNG_ID = "control-export-png"
_SAVE_STATE_ID = "control-save-state"
_LOAD_STATE_ID = "control-load-state"

_export_png_callback = None
_save_state_callback = None
_load_state_callback = None
_visible_modes_change_callback = None


def get_string_count() -> int:
    """Read the currently selected string count."""
    element = js.document.getElementById(_STRING_COUNT_ID)
    return int(element.value)


def get_tuning() -> list[str]:
    """Read the currently selected tuning as note names, low string to high."""
    element = js.document.getElementById(_TUNING_ID)
    return element.value.split(",")


def get_fret_count() -> int:
    """Read the currently selected fret count."""
    element = js.document.getElementById(_FRET_COUNT_ID)
    return int(element.value)


def get_accidental_type() -> AccidentalType:
    """Read the currently selected sharps/flats toggle.

    Returns the same AccidentalType config.get_chromatic_scale() expects,
    so this drops straight in wherever you're computing fret note names.
    """
    element = js.document.getElementById(_ACCIDENTAL_TYPE_ID)
    return AccidentalType[element.value]


def get_visible_modes() -> list[str]:
    """Read the two mode names currently picked for display (Tray A/B).

    Returns names, not a domain Mode object -- like get_tuning(), this
    stays domain-agnostic; matching them against modes.yaml's actual
    Mode list is main.py's job.
    """
    mode_a = js.document.getElementById(_MODE_A_ID).value
    mode_b = js.document.getElementById(_MODE_B_ID).value
    return [mode_a, mode_b]


def on_visible_modes_change(callback):
    """Register what happens when either mode tray picker (Tray A/B) changes.

    Unlike the other pickers (read once when the sketch is built), this
    one fires live -- a tray filter feels broken if picking a new mode
    silently does nothing until the next reload.

    Args:
        callback: Zero-argument function. Call get_visible_modes() again
            inside it to see the new selection.
    """
    global _visible_modes_change_callback
    _visible_modes_change_callback = callback


def on_export_png(callback):
    """Register what happens when "Export PNG" is clicked.

    Args:
        callback: Zero-argument function. Do whatever you need with your
            live sketch to export it, e.g. `sketch.save_image("fretboard.png")`
            (see TUTORIAL.md section 7 for what that does and does not do).
    """
    global _export_png_callback
    _export_png_callback = callback


def on_save_state(callback):
    """Register what gets saved when "Save State" is clicked.

    Args:
        callback: Zero-argument function returning a JSON-serializable
            object describing your current state (a dict is simplest).
            This module handles turning that into a downloaded .json file.
    """
    global _save_state_callback
    _save_state_callback = callback


def on_load_state(callback):
    """Register what happens when a file is picked via "Load State".

    Args:
        callback: One-argument function receiving the parsed JSON object
            from the loaded file. Restore your state however that implies.
    """
    global _load_state_callback
    _load_state_callback = callback


def _download_text(text: str, filename: str, mime: str):
    # Same download-via-synthetic-click mechanism sketchingpy's own
    # WebDataLayer uses internally (see TUTORIAL.md section 5) -- there is
    # no other way to write a file from the browser.
    encoded = urllib.parse.quote(text)
    link = js.document.createElement("a")
    link.download = filename
    link.href = f"data:{mime};charset=utf-8,{encoded}"
    link.click()


def _handle_visible_modes_change(event):
    if _visible_modes_change_callback is not None:
        _visible_modes_change_callback()


def _handle_export_png(event):
    if _export_png_callback is not None:
        _export_png_callback()


def _handle_save_state(event):
    if _save_state_callback is None:
        return
    state = _save_state_callback()
    _download_text(json.dumps(state), "tetraboard-state.json", "application/json")


async def _handle_load_state(event):
    if _load_state_callback is None:
        return
    files = event.target.files
    if files.length == 0:
        return
    text = await files.item(0).text()
    _load_state_callback(json.loads(text))


def _bind():
    mode_a_select = js.document.getElementById(_MODE_A_ID)
    mode_a_select.addEventListener("change", create_proxy(_handle_visible_modes_change))

    mode_b_select = js.document.getElementById(_MODE_B_ID)
    mode_b_select.addEventListener("change", create_proxy(_handle_visible_modes_change))

    export_button = js.document.getElementById(_EXPORT_PNG_ID)
    export_button.addEventListener("click", create_proxy(_handle_export_png))

    save_button = js.document.getElementById(_SAVE_STATE_ID)
    save_button.addEventListener("click", create_proxy(_handle_save_state))

    load_input = js.document.getElementById(_LOAD_STATE_ID)
    load_input.addEventListener("change", create_proxy(_handle_load_state))


_bind()
