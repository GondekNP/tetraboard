"""UI control panel plumbing: pickers, PNG export, and save/load state.

This is the portal between the plain-HTML control panel in index.html and
whatever sketchingpy object graph main.py builds. It owns:
  * reading the current picker selections (tuning, fret count, sharps/flats)
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
from config import AccidentalType
from pyodide.ffi import create_proxy

_TUNING_ID = "control-tuning"
_FRET_COUNT_ID = "control-fret-count"
_ACCIDENTAL_TYPE_ID = "control-accidental-type"
_MODE_A_ID = "control-mode-a"
_MODE_B_ID = "control-mode-b"
_KEY_ID = "control-key"
_KEY_MODE_ID = "control-key-mode"
_VALIDATE_TOGGLE_ID = "control-validate-toggle"
_CLEAR_BOARD_ID = "control-clear-board"
_PATTERN_NAME_ID = "control-pattern-name"
_EXPORT_VIEW_ID = "control-export-view"
_PLAYED_ONLY_ID = "control-played-only"
_GRAYSCALE_ID = "control-grayscale"
_ANNOTATE_TOGGLE_ID = "control-annotate-toggle"
_EXPORT_PNG_ID = "control-export-png"
_EXPORT_FOLDER_ID = "control-export-folder"
_SAVE_STATE_ID = "control-save-state"
_LOAD_STATE_ID = "control-load-state"

_DEFAULT_EXPORT_FOLDER_LABEL = "Set export folder…"

_export_png_callback = None
_set_export_folder_callback = None
_save_state_callback = None
_load_state_callback = None
_visible_modes_change_callback = None
_validator_change_callback = None
_clear_board_callback = None
_tuning_change_callback = None
_accidental_type_change_callback = None
_annotate_toggle_callback = None


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


def set_tuning(notes: list[str]) -> None:
    """Set the tuning picker to whichever preset's value matches `notes`
    exactly (same note-list format get_tuning() returns). If none of the
    <option>s match, the picker silently keeps its prior selection --
    same "must match a real TUNINGS preset" assumption main.py's
    _resolve_tuning() already enforces on read.
    """
    js.document.getElementById(_TUNING_ID).value = ",".join(notes)


def set_fret_count(value: int) -> None:
    """Set the fret count picker (used when restoring Load State)."""
    js.document.getElementById(_FRET_COUNT_ID).value = str(value)


def set_accidental_type(value: str) -> None:
    """Set the sharps/flats picker from an AccidentalType member's name
    (e.g. "SHARP", "FLAT") -- used when restoring Load State."""
    js.document.getElementById(_ACCIDENTAL_TYPE_ID).value = value


def set_visible_modes(mode_a: str, mode_b: str) -> None:
    """Set both mode tray pickers (used when restoring Load State).

    Sets the DOM value directly without dispatching a `change` event --
    main.py's load-state path calls its own rebuild once after restoring
    every control, rather than relying on on_visible_modes_change's
    live-update path firing mid-restore.
    """
    js.document.getElementById(_MODE_A_ID).value = mode_a
    js.document.getElementById(_MODE_B_ID).value = mode_b


def set_key(value: str) -> None:
    """Set the Key picker (used when restoring Load State)."""
    js.document.getElementById(_KEY_ID).value = value


def set_validation_enabled(value: bool) -> None:
    """Set the Validate checkbox (used when restoring Load State)."""
    js.document.getElementById(_VALIDATE_TOGGLE_ID).checked = bool(value)


def get_key() -> str:
    """Read the currently selected key (a bare pitch class, e.g. "A", "C#") --
    the root the validator builds its Ionian scale from."""
    element = js.document.getElementById(_KEY_ID)
    return element.value


def get_key_mode() -> str:
    """Read the currently selected key mode (e.g. "Ionian", "Dorian") --
    which of the seven diatonic rotations the validator/interval-degree
    math should build from config.MODE_INTERVALS, alongside get_key()'s
    root. Previously this was implicitly always Ionian."""
    element = js.document.getElementById(_KEY_MODE_ID)
    return element.value


def set_key_mode(value: str) -> None:
    """Set the Key Mode picker (used when restoring Load State)."""
    js.document.getElementById(_KEY_MODE_ID).value = value


def is_validation_enabled() -> bool:
    """Read the Validate checkbox: whether dropped pieces should be checked
    against the current key's scale."""
    element = js.document.getElementById(_VALIDATE_TOGGLE_ID)
    return bool(element.checked)


def get_pattern_name() -> str:
    """Read the pattern-name text field: a one-time name for the current
    board, reused as the export filename's stem (with a per-view suffix
    appended, e.g. "_intervals") so the user isn't retyping a filename on
    every export click -- see main.py's _export_png."""
    element = js.document.getElementById(_PATTERN_NAME_ID)
    return element.value


def get_export_view() -> str:
    """Read the currently selected export label mode: "vanilla" (note
    name), "interval" (scale degree), or "fingering" (assigned finger
    number) -- see main.py's _export_png for where this actually changes
    what gets drawn."""
    element = js.document.getElementById(_EXPORT_VIEW_ID)
    return element.value


def get_played_only() -> bool:
    """Read the "Played only" export checkbox.

    When checked, a note without an assigned fingering should render
    de-emphasized on export (see MainCanvas._export_png) -- a fingering
    is this app's only signal for "this note is actually used in this
    take", as opposed to just being part of the underlying tetrachord
    shape a piece represents.
    """
    element = js.document.getElementById(_PLAYED_ONLY_ID)
    return bool(element.checked)


def get_grayscale() -> bool:
    """Read the "Grayscale" export checkbox.

    When checked, note badges render in the existing black (root) / gray
    (non-root) / gray-with-hatch (accidental) scheme (see main.py's
    _export_png). When unchecked, each note badge instead uses its own
    piece's live mode color (the same color its tray/board piece already
    has) -- distinguishing which mode/shape a note came from is otherwise
    impossible in grayscale once labels are covered by another view (e.g.
    two differently-shaped patterns that happen to land on the same board
    positions read as identical in black-and-white).
    """
    element = js.document.getElementById(_GRAYSCALE_ID)
    return bool(element.checked)


def is_annotate_enabled() -> bool:
    """Read the Annotate checkbox: whether a left-click on a board piece
    should open the finger/note-assignment prompt instead of picking the
    piece up to drag (see MainCanvas._on_press / _try_annotate_piece)."""
    element = js.document.getElementById(_ANNOTATE_TOGGLE_ID)
    return bool(element.checked)


def toggle_annotate() -> None:
    """Flip the Annotate checkbox programmatically (see MainCanvas.
    _on_key_press's Shift hotkey) and fire the same live callback a real
    click's "change" event would -- setting `.checked` directly doesn't
    dispatch that event on its own, so the on_annotate_toggle listener
    has to be invoked here explicitly instead of relying on the browser
    to notice the change.
    """
    element = js.document.getElementById(_ANNOTATE_TOGGLE_ID)
    element.checked = not element.checked
    if _annotate_toggle_callback is not None:
        _annotate_toggle_callback()


def on_validator_change(callback):
    """Register what happens when the Key picker, Key Mode picker, or
    Validate checkbox changes. Fires live, same reasoning as
    on_visible_modes_change -- picking a new key/mode or flipping the
    toggle should update immediately, not wait for a reload.

    Args:
        callback: Zero-argument function. Call get_key()/get_key_mode()/
            is_validation_enabled() again inside it to see the new values.
    """
    global _validator_change_callback
    _validator_change_callback = callback


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


def on_tuning_change(callback):
    """Register what happens when the Tuning picker changes.

    Fires live, same reasoning as on_visible_modes_change -- a tuning
    switch that silently does nothing until reload would just look
    broken. Unlike Key/Validate/Mode changes, a new tuning can change
    the fretboard's string count, which can strand board pieces on rows
    that no longer exist -- so this is expected to clear the board as
    part of handling the change, not just rebuild in place.

    Args:
        callback: Zero-argument function. Call get_tuning() again inside
            it to see the new selection.
    """
    global _tuning_change_callback
    _tuning_change_callback = callback


def on_accidental_type_change(callback):
    """Register what happens when the sharps/flats picker changes.

    Fires live, same reasoning as on_validator_change -- flipping this
    silently doing nothing until some *other* control triggers a rebuild
    (e.g. Tuning) looked broken. Doesn't change string count or fret
    count, so unlike on_tuning_change there's no reason to clear the
    board here -- just re-derive fret note names in place.

    Args:
        callback: Zero-argument function. Call get_accidental_type()
            again inside it to see the new selection.
    """
    global _accidental_type_change_callback
    _accidental_type_change_callback = callback


def on_annotate_toggle(callback):
    """Register what happens when the Annotate checkbox changes (either
    direction).

    Fires live, unlike is_annotate_enabled() itself (read on demand,
    since it only changes click behavior) -- needed so main.py can drop
    its in-progress cell selection the moment Annotate is toggled either
    way, rather than leaving a stale selection highlighted once it no
    longer means anything.

    Args:
        callback: Zero-argument function.
    """
    global _annotate_toggle_callback
    _annotate_toggle_callback = callback


def on_clear_board(callback):
    """Register what happens when "Clear Board" is clicked.

    Args:
        callback: Zero-argument function. Should wipe whatever your code
            considers "placed on the board", leaving tray contents alone.
    """
    global _clear_board_callback
    _clear_board_callback = callback


def on_export_png(callback):
    """Register what happens when "Export PNG" is clicked.

    Args:
        callback: Zero-argument function, or coroutine function -- it's
            awaited (see _handle_export_png) so it can use a native
            "Save As" dialog, which doesn't resolve until the user
            responds to it. Do whatever you need with your live sketch to
            export it, e.g. `sketch.save_image("fretboard.png")` (see
            TUTORIAL.md section 7 for what that does and does not do).
    """
    global _export_png_callback
    _export_png_callback = callback


def on_set_export_folder(callback):
    """Register what happens when "Set export folder…" is clicked.

    Args:
        callback: Zero-argument coroutine function -- it's awaited (see
            _handle_set_export_folder), same as on_export_png's, since
            picking a folder means awaiting a native directory-picker
            dialog. Whatever it does should end with
            set_export_folder_label(...) if it succeeds, so the button
            reflects the chosen folder.
    """
    global _set_export_folder_callback
    _set_export_folder_callback = callback


def set_export_folder_label(folder_name: str) -> None:
    """Update the "Set export folder…" button to show the current choice.

    Called by whatever on_set_export_folder's callback does, both right
    after the user picks a folder and at startup if a previous session's
    choice was successfully restored -- this is the only user-visible
    sign of which one (if any) is currently remembered, since exporting
    into it happens with no dialog at all.
    """
    button = js.document.getElementById(_EXPORT_FOLDER_ID)
    if button is not None:
        button.textContent = f"Export folder: {folder_name}"


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


def _handle_validator_change(event):
    if _validator_change_callback is not None:
        _validator_change_callback()


def _handle_tuning_change(event):
    if _tuning_change_callback is not None:
        _tuning_change_callback()


def _handle_accidental_type_change(event):
    if _accidental_type_change_callback is not None:
        _accidental_type_change_callback()


def _handle_clear_board(event):
    if _clear_board_callback is not None:
        _clear_board_callback()


def _handle_annotate_toggle(event):
    if _annotate_toggle_callback is not None:
        _annotate_toggle_callback()


async def _handle_export_png(event):
    if _export_png_callback is not None:
        await _export_png_callback()


async def _handle_set_export_folder(event):
    if _set_export_folder_callback is not None:
        await _set_export_folder_callback()


_DEFAULT_SAVE_STATE_FILENAME = "tetraboard-state.json"


def _handle_save_state(event):
    if _save_state_callback is None:
        return
    state = _save_state_callback()

    filename = js.window.prompt("Save as:", _DEFAULT_SAVE_STATE_FILENAME)
    if filename is None:
        return  # user hit Cancel -- no download
    filename = filename.strip() or _DEFAULT_SAVE_STATE_FILENAME
    if not filename.endswith(".json"):
        filename += ".json"

    _download_text(json.dumps(state), filename, "application/json")


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

    key_select = js.document.getElementById(_KEY_ID)
    key_select.addEventListener("change", create_proxy(_handle_validator_change))

    key_mode_select = js.document.getElementById(_KEY_MODE_ID)
    key_mode_select.addEventListener("change", create_proxy(_handle_validator_change))

    validate_toggle = js.document.getElementById(_VALIDATE_TOGGLE_ID)
    validate_toggle.addEventListener("change", create_proxy(_handle_validator_change))

    tuning_select = js.document.getElementById(_TUNING_ID)
    tuning_select.addEventListener("change", create_proxy(_handle_tuning_change))

    accidental_type_select = js.document.getElementById(_ACCIDENTAL_TYPE_ID)
    accidental_type_select.addEventListener("change", create_proxy(_handle_accidental_type_change))

    clear_board_button = js.document.getElementById(_CLEAR_BOARD_ID)
    clear_board_button.addEventListener("click", create_proxy(_handle_clear_board))

    annotate_toggle = js.document.getElementById(_ANNOTATE_TOGGLE_ID)
    annotate_toggle.addEventListener("change", create_proxy(_handle_annotate_toggle))

    export_button = js.document.getElementById(_EXPORT_PNG_ID)
    export_button.addEventListener("click", create_proxy(_handle_export_png))

    # Only wired up (and left visible) where the File System Access
    # API's directory picker actually exists -- Firefox/Safari have no
    # equivalent as of this writing, and a button that always throws the
    # moment it's clicked is worse than no button at all.
    export_folder_button = js.document.getElementById(_EXPORT_FOLDER_ID)
    if hasattr(js.window, "showDirectoryPicker"):
        export_folder_button.textContent = _DEFAULT_EXPORT_FOLDER_LABEL
        export_folder_button.addEventListener("click", create_proxy(_handle_set_export_folder))
    else:
        export_folder_button.style.display = "none"

    save_button = js.document.getElementById(_SAVE_STATE_ID)
    save_button.addEventListener("click", create_proxy(_handle_save_state))

    load_input = js.document.getElementById(_LOAD_STATE_ID)
    load_input.addEventListener("change", create_proxy(_handle_load_state))


_bind()
