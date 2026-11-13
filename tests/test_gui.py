"""Tests for the logdeck.gui chassis (skipped when Tk cannot create a window)."""

import subprocess
import sys
import tempfile
import time
from pathlib import Path

import pytest

from logdeck.gui.analyzer import AnalyzerConfig, accepts_path, report_path_for

CONFIG = AnalyzerConfig(
    title="Test Analyzer",
    heading="🧪 Test",
    subtitle="sub",
    accept_suffixes=(".tgz", ".tar.gz"),
    dialog_title="Pick",
    dialog_filetype_label="Archives",
    drop_hint="drop here",
    browse_text="Browse",
    process_text="Analyze",
)


def _make_root():
    """Return (tk, root) or skip if tkinter/display is unavailable."""
    try:
        import tkinter as tk
    except ImportError:
        pytest.skip("tkinter not installed")
    try:
        root = tk.Tk()
    except tk.TclError as exc:
        pytest.skip(f"no display for Tk: {exc}")
    root.withdraw()
    return tk, root


def test_core_import_never_pulls_tkinter():
    code = "import sys; import logdeck; sys.exit('tkinter' in sys.modules)"
    result = subprocess.run([sys.executable, "-c", code])
    assert result.returncode == 0, "importing logdeck pulled tkinter into core"


@pytest.mark.parametrize(
    ("name", "expected"),
    [
        ("snap.tgz", True),
        ("snap.TGZ", True),
        ("snap.tar.gz", True),
        ("snap.TAR.GZ", True),
        ("snap.zip", False),
        ("snap.tar", False),
        ("tgz", False),
    ],
)
def test_accepts_path(name, expected):
    assert accepts_path(name, (".tgz", ".tar.gz")) is expected


def test_report_path_for(tmp_path):
    out = report_path_for(tmp_path / "snap.tgz", "analysis_report.html")
    assert out == tmp_path / "snap_analysis_report.html"


def test_window_builds_with_initial_state():
    tk, root = _make_root()
    try:
        from logdeck.gui.analyzer import AnalyzerWindow

        win = AnalyzerWindow(root, CONFIG, lambda i, o: o)
        assert win.processing is False
        assert win.current_input is None
        assert win.status_var.get() == CONFIG.initial_status
        assert str(win.process_btn["state"]) == "disabled"
        assert "#198754" in str(win.status_label.cget("foreground"))
    finally:
        root.destroy()


def _drive_window(win, tk, timeout=3.0):
    """Let the worker thread and the poll loop run until processing ends."""
    deadline = time.monotonic() + timeout
    while win.processing and time.monotonic() < deadline:
        win.root.update()
        time.sleep(0.02)
    assert not win.processing, "worker/poll loop did not finish"


def test_success_path_generates_report_and_opens_browser(monkeypatch):
    import logdeck.gui.analyzer as analyzer

    tk, root = _make_root()
    opened: list[str] = []
    monkeypatch.setattr(analyzer.webbrowser, "open_new_tab", opened.append)
    try:
        win = analyzer.AnalyzerWindow(root, CONFIG, lambda i, o: o)
        with tempfile.TemporaryDirectory() as td:
            inp = Path(td) / "snap.tgz"
            inp.write_bytes(b"x")
            report = Path(td) / "snap_analysis_report.html"
            report.write_text("<html></html>")

            win.current_input = inp
            win._on_process_clicked()
            _drive_window(win, tk)

            assert win.current_report == report
            assert report.name in win.report_path_var.get()
            assert "Report opened in your browser" in win.status_var.get()
            assert opened == [report.as_uri()]
            assert str(win.open_browser_btn["state"]) == "normal"
            assert win.drop_label.cget("bg") == "#d1e7dd"
    finally:
        root.destroy()


def test_failure_path_shows_error_state(monkeypatch):
    import logdeck.gui.analyzer as analyzer

    tk, root = _make_root()
    errors: list[tuple[str, str]] = []
    monkeypatch.setattr(analyzer.messagebox, "showerror", lambda t, m: errors.append((t, m)))
    monkeypatch.setattr(analyzer.webbrowser, "open_new_tab", lambda u: None)
    try:
        def boom(input_path, report_path):
            raise ValueError("bad archive")

        win = analyzer.AnalyzerWindow(root, CONFIG, boom)
        with tempfile.TemporaryDirectory() as td:
            inp = Path(td) / "snap.tgz"
            inp.write_bytes(b"x")
            win.current_input = inp
            win._on_process_clicked()
            _drive_window(win, tk)

            assert errors == [("Processing Failed", "ValueError: bad archive")]
            assert "ValueError" in win.status_var.get()
            assert "#dc3545" in str(win.status_label.cget("foreground"))
            assert "#f8d7da" in str(win.drop_label.cget("bg"))
    finally:
        root.destroy()


def test_auto_open_disabled(monkeypatch):
    import logdeck.gui.analyzer as analyzer

    tk, root = _make_root()
    opened: list[str] = []
    monkeypatch.setattr(analyzer.webbrowser, "open_new_tab", opened.append)
    try:
        win = analyzer.AnalyzerWindow(root, CONFIG, lambda i, o: o, auto_open_report=False)
        with tempfile.TemporaryDirectory() as td:
            inp = Path(td) / "snap.tgz"
            inp.write_bytes(b"x")
            out = Path(td) / "snap_analysis_report.html"
            out.write_text("<html></html>")
            win.current_input = inp
            win._on_process_clicked()
            _drive_window(win, tk)
            assert opened == []
            assert "generated successfully" in win.status_var.get()
    finally:
        root.destroy()
