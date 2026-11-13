"""Tests for the logdeck.gui chassis (skipped when Tk cannot create a window)."""

import subprocess
import sys
import tempfile
import time
from pathlib import Path

import pytest

from logdeck.gui.analyzer import AnalyzerConfig, accepts_path, classify_paths, report_path_for

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

SIDECAR_CONFIG = AnalyzerConfig(
    title="Sidecar Analyzer",
    heading="🧪 Sidecar",
    subtitle="sub",
    accept_suffixes=(".bundle",),
    dialog_title="Pick",
    dialog_filetype_label="Test bundles",
    drop_hint="drop here",
    browse_text="Browse",
    process_text="Analyze",
    sidecar_suffixes=(".csv",),
    sidecar_name_hint=("companion_", "companion2_"),
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
        ("sample.tgz", True),
        ("sample.TGZ", True),
        ("sample.tar.gz", True),
        ("sample.TAR.GZ", True),
        ("sample.zip", False),
        ("sample.tar", False),
        ("tgz", False),
    ],
)
def test_accepts_path(name, expected):
    assert accepts_path(name, (".tgz", ".tar.gz")) is expected


def test_report_path_for(tmp_path):
    out = report_path_for(tmp_path / "sample.tgz", "analysis_report.html")
    assert out == tmp_path / "sample_analysis_report.html"


def test_classify_paths_mixed_drop():
    names = [
        "/d/b.bundle",
        "/d/companion_x.csv",
        "/d/other.zip",
        "/d/a.bundle",
        "/d/companion2_y.csv",
        "/d/random.txt",
    ]
    prim, side = classify_paths(names, (".bundle",), (".csv",))
    assert prim == ["/d/b.bundle", "/d/a.bundle"]
    assert side == ["/d/companion_x.csv", "/d/companion2_y.csv"]


def test_classify_paths_dedup_case_insensitive_on_windows_style():
    names = ["/d/a.csv", "/d/A.CSV", "/d/a.csv"]
    prim, side = classify_paths(names, (".bundle",), (".csv",))
    assert prim == []
    # On POSIX, normcase is identity: only exact duplicates collapse.
    assert side == ["/d/a.csv"] or side == ["/d/a.csv", "/d/A.CSV"]


def test_classify_paths_empty_sidecar_suffixes_keeps_single_file():
    prim, side = classify_paths(["a.tgz", "b.tgz", "x.csv"], (".tgz",), ())
    assert prim == ["a.tgz", "b.tgz"]
    assert side == []


def test_classify_paths_primary_suffix_wins_over_sidecar():
    prim, side = classify_paths(["dual.csv"], (".csv",), (".csv",))
    assert prim == ["dual.csv"]
    assert side == []


def test_window_builds_with_initial_state():
    tk, root = _make_root()
    try:
        from logdeck.gui.analyzer import AnalyzerWindow

        win = AnalyzerWindow(root, CONFIG, lambda i, s, o: o)
        assert win.processing is False
        assert win.current_input is None
        assert win.current_sidecars == ()
        assert win.status_var.get() == CONFIG.initial_status
        assert str(win.process_btn["state"]) == "disabled"
        assert "#198754" in str(win.status_label.cget("foreground"))
        assert not hasattr(win, "attach_btn")  # no sidecar_suffixes -> no Attach button
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
        win = analyzer.AnalyzerWindow(root, CONFIG, lambda i, s, o: o)
        with tempfile.TemporaryDirectory() as td:
            inp = Path(td) / "sample.tgz"
            inp.write_bytes(b"x")
            report = Path(td) / "sample_analysis_report.html"
            report.write_text("<html></html>")

            win.current_input = inp
            win._on_process_clicked()
            _drive_window(win, tk)

            assert win.current_report == report
            assert report.name in win.report_path_var.get()
            assert "Report opened in your browser" in win.status_var.get()
            assert opened == [report.as_uri()]
            assert str(win.open_browser_btn["state"]) == "normal"
            assert "#d1e7dd" in str(win.drop_label.cget("bg"))
    finally:
        root.destroy()


def test_failure_path_shows_error_state(monkeypatch):
    import logdeck.gui.analyzer as analyzer

    tk, root = _make_root()
    errors: list[tuple[str, str]] = []
    monkeypatch.setattr(analyzer.messagebox, "showerror", lambda t, m: errors.append((t, m)))
    monkeypatch.setattr(analyzer.webbrowser, "open_new_tab", lambda u: None)
    try:
        def boom(primary, sidecars, report_path):
            raise ValueError("bad archive")

        win = analyzer.AnalyzerWindow(root, CONFIG, boom)
        with tempfile.TemporaryDirectory() as td:
            inp = Path(td) / "sample.tgz"
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
        win = analyzer.AnalyzerWindow(root, CONFIG, lambda i, s, o: o, auto_open_report=False)
        with tempfile.TemporaryDirectory() as td:
            inp = Path(td) / "sample.tgz"
            inp.write_bytes(b"x")
            out = Path(td) / "sample_analysis_report.html"
            out.write_text("<html></html>")
            win.current_input = inp
            win._on_process_clicked()
            _drive_window(win, tk)
            assert opened == []
            assert "generated successfully" in win.status_var.get()
    finally:
        root.destroy()


def test_worker_receives_primary_and_sidecar_tuple(monkeypatch):
    """Chassis routing: worker gets (primary, sidecars-tuple, suggested out)."""
    import logdeck.gui.analyzer as analyzer

    tk, root = _make_root()
    monkeypatch.setattr(analyzer.webbrowser, "open_new_tab", lambda u: None)
    calls: list[tuple] = []

    def worker(primary, sidecars, report_path):
        calls.append((primary, sidecars, report_path))
        report_path.write_text("<html></html>")
        return report_path

    try:
        win = analyzer.AnalyzerWindow(root, SIDECAR_CONFIG, worker)
        with tempfile.TemporaryDirectory() as td:
            bundle = Path(td) / "server.bundle"
            bundle.write_bytes(b"x")
            csv1 = Path(td) / "companion_a.csv"
            csv1.write_text("a")
            csv2 = Path(td) / "companion2_b.csv"
            csv2.write_text("b")
            junk = Path(td) / "readme.txt"
            junk.write_text("j")

            win._handle_dropped_paths([str(bundle), str(csv1), str(junk), str(csv2)])
            assert win.current_input == bundle
            assert win.current_sidecars == (csv1, csv2)
            assert "2 sidecar(s) attached" in win.status_var.get()

            win._on_process_clicked()
            _drive_window(win, tk)

            assert calls == [(bundle, (csv1, csv2), Path(td) / "server_analysis_report.html")]
    finally:
        root.destroy()


def test_new_primary_replaces_sidecars_and_dedups(monkeypatch):
    import logdeck.gui.analyzer as analyzer

    tk, root = _make_root()
    monkeypatch.setattr(analyzer.messagebox, "showwarning", lambda t, m: None)
    try:
        win = analyzer.AnalyzerWindow(root, SIDECAR_CONFIG, lambda i, s, o: o)
        with tempfile.TemporaryDirectory() as td:
            bundle1, bundle2 = Path(td) / "a.bundle", Path(td) / "b.bundle"
            csv1 = Path(td) / "companion_x.csv"
            for p in (bundle1, bundle2, csv1):
                p.write_text("x")

            win._handle_dropped_paths([str(bundle1), str(csv1)])
            assert win.current_sidecars == (csv1,)

            # Sidecar-only drop appends, deduped by path.
            win._handle_dropped_paths([str(csv1), str(csv1)])
            assert win.current_sidecars == (csv1,)

            # A new primary wipes previous sidecars.
            win._handle_dropped_paths([str(bundle2)])
            assert win.current_input == bundle2
            assert win.current_sidecars == ()

            # Garbage-only drop warns and changes nothing.
            win._handle_dropped_paths([str(Path(td) / "junk.zip")])
            assert win.current_input == bundle2
            assert win.current_sidecars == ()
    finally:
        root.destroy()


def test_setup_dnd_registers_and_routes_without_tkinterdnd2(monkeypatch):
    """_setup_dnd must run without tkdnd (regression: Event[] runtime annotations)."""
    import logdeck.gui.analyzer as analyzer

    tk, root = _make_root()
    monkeypatch.setattr(analyzer.messagebox, "showwarning", lambda t, m: None)
    try:
        win = analyzer.AnalyzerWindow(root, SIDECAR_CONFIG, lambda i, s, o: o)
        binds: list = []
        root.drop_target_register = lambda fmt: binds.append(("root", fmt))
        root.dnd_bind = lambda seq, cb: binds.append(("root-cb", cb))
        root.splitlist = lambda data: tuple(p.strip("{}") for p in data.split())
        win.drop_label.drop_target_register = lambda fmt: binds.append(("label", fmt))
        win.drop_label.dnd_bind = lambda seq, cb: binds.append(("label-cb", cb))

        win._setup_dnd()
        assert ("root", "DND_Files") in binds and ("label", "DND_Files") in binds

        drop_cb = next(cb for kind, cb in binds if kind == "root-cb")
        with tempfile.TemporaryDirectory() as td:
            bundle, csv1 = Path(td) / "a.bundle", Path(td) / "companion_1.csv"
            bundle.write_text("x")
            csv1.write_text("y")
            event = type("Ev", (), {"data": f"{{{bundle}}} {csv1}"})()
            drop_cb(event)
            assert win.current_input == bundle
            assert win.current_sidecars == (csv1,)
    finally:
        root.destroy()


def test_chip_removal_and_attach_button():
    import logdeck.gui.analyzer as analyzer

    tk, root = _make_root()
    try:
        win = analyzer.AnalyzerWindow(root, SIDECAR_CONFIG, lambda i, s, o: o)
        assert str(win.attach_btn["state"]) == "normal"
        with tempfile.TemporaryDirectory() as td:
            bundle = Path(td) / "a.bundle"
            csv1, csv2 = Path(td) / "companion_1.csv", Path(td) / "companion_2.csv"
            for p in (bundle, csv1, csv2):
                p.write_text("x")
            win._handle_dropped_paths([str(bundle), str(csv1), str(csv2)])

            chips = win.chip_frame.winfo_children()
            assert len(chips) == 2
            assert "companion_1.csv" in chips[0].cget("text") and "✕" in chips[0].cget("text")

            win._remove_sidecar(csv1)
            assert win.current_sidecars == (csv2,)
            assert len(win.chip_frame.winfo_children()) == 1
            assert "1 sidecar(s) attached" in win.status_var.get()

            win._remove_sidecar(csv2)
            assert win.current_sidecars == ()
            assert win.chip_frame not in [
                c for c in win.drop_frame.pack_slaves()
            ]  # chip row hidden when empty
            assert "sidecar" not in win.status_var.get()
    finally:
        root.destroy()
