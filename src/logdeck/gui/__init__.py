"""Optional Tkinter GUI chassis for logdeck consumer apps.

``import logdeck`` never pulls in tkinter; this submodule does. Install
the ``gui`` extra for the ``tkinterdnd2`` drag & drop dependency (apps
that want drop support create a ``TkinterDnD.Tk()`` root; a plain
``tk.Tk()`` root degrades to browse-only).
"""

from logdeck.gui.analyzer import (
    AnalyzerConfig,
    AnalyzerWindow,
    ReportWorker,
    accepts_path,
    report_path_for,
    run_centered,
)

__all__ = [
    "AnalyzerConfig",
    "AnalyzerWindow",
    "ReportWorker",
    "accepts_path",
    "report_path_for",
    "run_centered",
]
