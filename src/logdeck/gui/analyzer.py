"""Drop-zone analyzer window chassis shared by logdeck consumer apps.
"""
import queue
import threading
import tkinter as tk
import webbrowser
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from pathlib import Path
from tkinter import filedialog, messagebox, ttk

# Worker(input_path, suggested_report_path) -> path of the written report.
ReportWorker = Callable[[Path, Path], Path]

_BG = "#f8f9fa"
_HEADER_BG = "#0066cc"
_STATUS_GREEN = "#198754"
_STATUS_RED = "#dc3545"
_LINK_BLUE = "#0d6efd"
_DROP_IDLE_BG = _BG
_DROP_READY_BG = "#d1e7dd"
_DROP_BUSY_BG = "#fff3cd"
_DROP_ERROR_BG = "#f8d7da"


@dataclass(frozen=True)
class AnalyzerConfig:
    """All user-visible text and file-type routing for one analyzer app."""

    title: str
    heading: str
    subtitle: str
    accept_suffixes: tuple[str, ...]
    dialog_title: str
    dialog_filetype_label: str
    drop_hint: str
    browse_text: str
    process_text: str
    input_group_label: str = "  Input  "
    footer_hint: str = (
        "Tip: The HTML report is saved next to your input file. "
        "You can attach it to tickets or email it."
    )
    initial_status: str = "Ready. Select or drop a file to begin."
    processing_status: str = "🔄  Processing input... This may take some time."


def accepts_path(name: str, accept_suffixes: Sequence[str]) -> bool:
    """True when a file name ends in one of the accepted suffixes.

    Plain ``endswith`` (not ``Path.suffix``) so compound suffixes such as
    ``.tar.gz`` match correctly.
    """
    lowered = name.lower()
    return any(lowered.endswith(suffix.lower()) for suffix in accept_suffixes)


def report_path_for(input_path: Path, report_suffix: str) -> Path:
    """Report path beside the input: ``<input stem>_<report_suffix>``."""
    return input_path.parent / f"{input_path.stem}_{report_suffix}"


class AnalyzerWindow:
    """The GUI chassis. See module docstring for the ownership split."""

    def __init__(
        self,
        root: tk.Tk,
        config: AnalyzerConfig,
        worker: ReportWorker,
        *,
        report_suffix: str = "analysis_report.html",
        auto_open_report: bool = True,
        geometry: str = "720x520",
        minsize: tuple[int, int] = (640, 480),
    ) -> None:
        self.root = root
        self.config = config
        self.worker = worker
        self.report_suffix = report_suffix
        self.auto_open_report = auto_open_report

        self.root.title(config.title)
        self.root.geometry(geometry)
        self.root.minsize(*minsize)
        self.root.configure(bg=_BG)

        # State
        self.current_input: Path | None = None
        self.current_report: Path | None = None
        self.processing = False
        self.result_queue: queue.Queue[tuple[str, Path | str]] = queue.Queue()

        self._build_ui()

        # Start polling the result queue (for thread-safe GUI updates)
        self.root.after(100, self._poll_queue)

        # Drag & drop whenever the injected root supports it (TkinterDnD.Tk)
        if hasattr(self.root, "drop_target_register"):
            self._setup_dnd()

    def _build_ui(self) -> None:
        style = ttk.Style()
        style.theme_use("clam")

        # Header
        header = tk.Frame(self.root, bg=_HEADER_BG, height=90)
        header.pack(fill=tk.X, side=tk.TOP)
        header.pack_propagate(False)

        title = tk.Label(
            header,
            text=self.config.heading,
            font=("Segoe UI", 20, "bold"),
            fg="white",
            bg=_HEADER_BG,
        )
        title.pack(pady=(18, 2))

        subtitle = tk.Label(
            header,
            text=self.config.subtitle,
            font=("Segoe UI", 11),
            fg="#cce5ff",
            bg=_HEADER_BG,
        )
        subtitle.pack()

        # Main content area
        main = ttk.Frame(self.root, padding=20)
        main.pack(fill=tk.BOTH, expand=True)

        # Drop / Select zone
        self.drop_frame = ttk.LabelFrame(main, text=self.config.input_group_label, padding=15)
        self.drop_frame.pack(fill=tk.X, pady=(0, 15))

        self.drop_label = tk.Label(
            self.drop_frame,
            text=self.config.drop_hint,
            font=("Segoe UI", 14),
            fg="#495057",
            bg=_DROP_IDLE_BG,
            height=4,
            relief="solid",
            borderwidth=2,
            cursor="hand2",
        )
        self.drop_label.pack(fill=tk.BOTH, expand=True, pady=5)

        # Make the whole label clickable
        self.drop_label.bind("<Button-1>", lambda event: self._on_browse_clicked())
        self.drop_label.bind("<Enter>", lambda e: self.drop_label.config(bg="#e7f1ff"))
        self.drop_label.bind("<Leave>", lambda e: self.drop_label.config(bg=_DROP_IDLE_BG))

        # Browse button row
        btn_frame = ttk.Frame(main)
        btn_frame.pack(fill=tk.X, pady=(0, 10))

        self.browse_btn = ttk.Button(
            btn_frame,
            text=self.config.browse_text,
            command=self._on_browse_clicked,
            width=28,
        )
        self.browse_btn.pack(side=tk.LEFT, padx=(0, 10))

        self.process_btn = ttk.Button(
            btn_frame,
            text=self.config.process_text,
            command=self._on_process_clicked,
            state=tk.DISABLED,
            width=28,
        )
        self.process_btn.pack(side=tk.LEFT)

        # Status section
        status_frame = ttk.LabelFrame(main, text="  Status  ", padding=10)
        status_frame.pack(fill=tk.BOTH, expand=True)

        self.status_var = tk.StringVar(value=self.config.initial_status)
        self.status_label = ttk.Label(
            status_frame,
            textvariable=self.status_var,
            font=("Segoe UI", 10),
            foreground=_STATUS_GREEN,
            wraplength=650,
        )
        self.status_label.pack(anchor=tk.W, pady=(5, 8))

        # Progress bar (indeterminate)
        self.progress = ttk.Progressbar(status_frame, mode="indeterminate", length=400)

        # Result info
        self.result_frame = ttk.Frame(status_frame)
        self.result_frame.pack(fill=tk.X, pady=(10, 0))

        self.report_path_var = tk.StringVar(value="")
        self.report_label = ttk.Label(
            self.result_frame,
            textvariable=self.report_path_var,
            font=("Consolas", 9),
            foreground=_LINK_BLUE,
            cursor="hand2",
        )
        self.report_label.bind("<Button-1>", lambda event: self._on_open_report_clicked())
        self.report_label.pack(anchor=tk.W)

        self.open_browser_btn = ttk.Button(
            self.result_frame,
            text="🌐  Open Report in Browser",
            command=self._on_open_report_clicked,
            state=tk.DISABLED,
        )
        self.open_browser_btn.pack(anchor=tk.W, pady=(8, 0))

        # Footer hint
        footer = ttk.Label(
            self.root,
            text=self.config.footer_hint,
            font=("Segoe UI", 8),
            foreground="#6c757d",
        )
        footer.pack(side=tk.BOTTOM, pady=8)

    def _setup_dnd(self) -> None:
        """Enable drag & drop on a DND-capable root (app bundles tkinterdnd2)."""
        self.root.drop_target_register("DND_Files")  # type: ignore[attr-defined]
        self.drop_label.drop_target_register("DND_Files")  # type: ignore[attr-defined]

        def on_drop(event: tk.Event[tk.Misc]) -> None:
            # event.data can contain one or more files wrapped in {}
            # (typeshed's Event lacks the .data attribute, hence getattr)
            raw: str = getattr(event, "data", "")
            try:
                files: list[str] = list(self.root.splitlist(raw))
            except (tk.TclError, TypeError):
                files = [raw.strip("{}")]

            if files:
                candidate = Path(files[0])
                if accepts_path(candidate.name, self.config.accept_suffixes):
                    self._select_input(candidate, "Ready to analyze")
                else:
                    accepted = "/".join(self.config.accept_suffixes)
                    messagebox.showwarning("Invalid File", f"Please drop a {accepted} file.")

        self.drop_label.dnd_bind("<<Drop>>", on_drop)  # type: ignore[attr-defined]
        self.root.dnd_bind("<<Drop>>", on_drop)  # type: ignore[attr-defined]

    def _select_input(self, path: Path, hint: str) -> None:
        self.current_input = path
        self.drop_label.config(text=f"✅  {path.name}\n{hint}", bg=_DROP_READY_BG)
        self.process_btn.config(state=tk.NORMAL)
        self.status_var.set(f"File selected: {path.name}")
        self.report_path_var.set("")
        self.open_browser_btn.config(state=tk.DISABLED)

    def _on_browse_clicked(self) -> None:
        if self.processing:
            return
        filetypes = [
            (self.config.dialog_filetype_label, " ".join(self.config.accept_suffixes)),
            ("All files", "*.*"),
        ]
        path = filedialog.askopenfilename(
            title=self.config.dialog_title,
            filetypes=filetypes,
        )
        if path:
            self._select_input(Path(path), "Click 'Analyze' or drop another file")

    def _on_process_clicked(self) -> None:
        if not self.current_input or self.processing:
            return

        self.processing = True
        self.browse_btn.config(state=tk.DISABLED)
        self.process_btn.config(state=tk.DISABLED)
        self.progress.pack(pady=5)
        self.progress.start(12)
        self.status_var.set(self.config.processing_status)
        self.report_path_var.set("")
        self.open_browser_btn.config(state=tk.DISABLED)
        self.drop_label.config(bg=_DROP_BUSY_BG, text="⏳  Processing... Please wait")

        # Run heavy work in background thread
        thread = threading.Thread(target=self._worker_thread, daemon=True)
        thread.start()

    def _worker_thread(self) -> None:
        """Heavy lifting happens here (does not block GUI)."""
        try:
            input_path = self.current_input
            assert input_path is not None
            report_path = report_path_for(input_path, self.report_suffix)
            written = self.worker(input_path, report_path)
            self.result_queue.put(("success", written))
        except Exception as exc:
            self.result_queue.put(("error", f"{type(exc).__name__}: {exc}"))

    def _poll_queue(self) -> None:
        """Check for results from worker thread (runs every ~120ms)."""
        try:
            while True:
                msg_type, payload = self.result_queue.get_nowait()

                self.progress.stop()
                self.progress.pack_forget()
                self.processing = False
                self.browse_btn.config(state=tk.NORMAL)
                self.process_btn.config(state=tk.NORMAL)
                self.drop_label.config(bg=_DROP_IDLE_BG)

                if msg_type == "success":
                    assert isinstance(payload, Path)
                    report_path = payload
                    self.current_report = report_path
                    self.status_var.set("✅  Analysis complete! Report generated successfully.")
                    self.status_label.config(foreground=_STATUS_GREEN)
                    self.report_path_var.set(f"📄  {report_path.name}")
                    self.open_browser_btn.config(state=tk.NORMAL)

                    # Auto-open in browser
                    if self.auto_open_report:
                        try:
                            webbrowser.open_new_tab(report_path.as_uri())
                            self.status_var.set(
                                "✅  Analysis complete! Report opened in your browser."
                            )
                        except (webbrowser.Error, OSError):
                            pass  # browser open is nice-to-have

                    # Reset drop zone text
                    input_name = self.current_input.name if self.current_input else ""
                    self.drop_label.config(
                        text=f"✅  Done: {input_name}\nDrop another file or browse again",
                        bg=_DROP_READY_BG,
                    )

                elif msg_type == "error":
                    self.status_var.set(f"❌  {payload}")
                    self.status_label.config(foreground=_STATUS_RED)
                    self.drop_label.config(
                        text="❌  Failed - see status below\nClick Browse to try another file",
                        bg=_DROP_ERROR_BG,
                    )
                    messagebox.showerror("Processing Failed", str(payload))

                # re-enable buttons
                self.process_btn.config(state=tk.NORMAL if self.current_input else tk.DISABLED)

        except queue.Empty:
            pass

        # Schedule next poll
        self.root.after(120, self._poll_queue)

    def _on_open_report_clicked(self) -> None:
        if self.current_report and self.current_report.exists():
            try:
                webbrowser.open_new_tab(self.current_report.as_uri())
            except (webbrowser.Error, OSError) as exc:
                messagebox.showerror("Browser Error", f"Could not open browser:\n{exc}")
        else:
            messagebox.showwarning("No Report", "No report has been generated yet.")


def run_centered(root: tk.Tk) -> None:
    """Center the window on screen and run the mainloop."""
    root.update_idletasks()
    w = root.winfo_width()
    h = root.winfo_height()
    x = (root.winfo_screenwidth() // 2) - (w // 2)
    y = (root.winfo_screenheight() // 2) - (h // 2)
    root.geometry(f"{w}x{h}+{x}+{y}")
    root.mainloop()
