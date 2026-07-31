"""
Dev-only hot reload for main.py.

This file is loaded once by index.html and never re-executed itself --
that's what lets it survive across edits and hold state (the running
sketch, the last-seen version) that a re-exec of main.py shouldn't reset.

It polls scripts/serve.py's /main-version endpoint (bumped only when
main.py changes -- see serve.py) and, on change, tears down the running
sketch and re-execs main.py in place, skipping the Pyodide/PyScript boot
a full page reload would pay.

Two things make this safe rather than a pile of stacked state:
* Sketchingpy's Sketch2DWeb.quit() cleanly stops its render loop, so we
  call it on whatever sketch is currently running before starting the
  next one.
* Sketchingpy attaches its mouse/keyboard listeners directly to the
  canvas element via addEventListener, with no matching
  removeEventListener anywhere in the library. Swapping in a fresh
  canvas node (rather than reusing the old one) is what actually drops
  those listeners instead of stacking a new set on every reload.

Known gap: if main.py raises *after* constructing the sketch but before
returning it from main(), that instance's render loop has no handle we
can quit() on the next reload. Rare in practice (it means breaking your
own code between Sketch2D(...) and the end of main()) and not worth
building a more invasive contract with main.py to close for a dev-only
convenience.
"""

import asyncio
import traceback

import js

POLL_INTERVAL_S = 0.8
MAIN_SRC_URL = "main.py"
VERSION_URL = "/main-version"
CANVAS_ID = "sketch-canvas"
MESSAGE_ID = "sketch-load-message"

_current_sketch = None
_last_version = None


def _fresh_canvas():
    old = js.document.getElementById(CANVAS_ID)
    new = js.document.createElement("canvas")
    new.id = CANVAS_ID
    old.parentNode.replaceChild(new, old)


def _show_error(message):
    el = js.document.getElementById(MESSAGE_ID)
    if el is None:
        return
    el.textContent = message
    el.style.color = "#ff6b6b"
    el.style.display = "block"


async def _fetch_text(url):
    response = await js.fetch(url)
    return await response.text()


def _run(source):
    global _current_sketch

    if _current_sketch is not None:
        try:
            _current_sketch.quit()
        except Exception:  # noqa: BLE001 -- best-effort cleanup, must not block the reload
            traceback.print_exc()
        _current_sketch = None

    _fresh_canvas()

    namespace = {"__name__": "__devreload__"}
    try:
        exec(compile(source, MAIN_SRC_URL, "exec"), namespace)  # noqa: S102 -- re-executing the edited source is the point of this file
        _current_sketch = namespace["main"]()
    except Exception:  # noqa: BLE001 -- main.py can raise anything; must not crash the harness
        traceback.print_exc()
        _show_error(
            "main.py failed to load -- see browser console for the "
            "traceback. Fix and save to retry."
        )


async def _poll_loop():
    global _last_version

    while True:
        try:
            version = await _fetch_text(VERSION_URL)
        except Exception:  # noqa: BLE001 -- a transient network hiccup shouldn't kill the poll loop
            await asyncio.sleep(POLL_INTERVAL_S)
            continue

        if version != _last_version:
            _last_version = version
            try:
                source = await _fetch_text(MAIN_SRC_URL)
            except Exception:  # noqa: BLE001 -- same as above
                traceback.print_exc()
            else:
                _run(source)

        await asyncio.sleep(POLL_INTERVAL_S)


asyncio.ensure_future(_poll_loop())
