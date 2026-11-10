"""Review Smoother: Anki add-on entry point.

`smoothing.py` holds the pure logic and must stay free of Anki imports, so
this package stays importable from tests and tools: the Anki integration is
only loaded when running inside Anki.
"""

try:
    from aqt import mw
except ImportError:  # outside Anki (tests, tools)
    mw = None

if mw is not None:
    from .ui import setup_menu

    setup_menu()
