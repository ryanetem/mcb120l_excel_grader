from __future__ import annotations

import queue
import threading
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, ttk, messagebox

from .lab_presets import (
    ALL_LABS,
    build_configs_from_params,
    grouped_params,
    output_basename,
    file_match,
)


APP_TITLE = "MCB120L Excel Grader"
PAD = 8
SECTION_PAD = 10


class GraderApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title(APP_TITLE)
        self.geometry("720x820")
        self.minsize(640, 600)

        self._log_queue = queue.Queue()

        self._param_vars = {}
        self._param_kinds = {}
        self._input_dir = tk.StringVar()
        self._output_dir = tk.StringVar()
        self._section = tk.StringVar()
        self._lab_choice = tk.StringVar(value=list(ALL_LABS.keys())[0])
        self._running = False

        self._build_layout()
        self._on_lab_change()
        self.after(100, self._drain_log_queue)

    def _build_layout(self):
        root = ttk.Frame(self, padding=PAD * 2)
        root.pack(fill="both", expand=True)
        root.columnconfigure(0, weight=1)
        root.rowconfigure(4, weight=1)

        folders = ttk.LabelFrame(root, text="Folders", padding=SECTION_PAD)
        folders.grid(row=0, column=0, sticky="ew")
        folders.columnconfigure(1, weight=1)

        ttk.Label(folders, text="Input folder:").grid(row=0, column=0, sticky="w")
        ttk.Entry(folders, textvariable=self._input_dir).grid(
            row=0, column=1, sticky="ew", padx=PAD
        )
        ttk.Button(folders, text="Browse...", command=self._pick_input_dir).grid(
            row=0, column=2
        )

        ttk.Label(folders, text="Output folder:").grid(
            row=1, column=0, sticky="w", pady=(PAD, 0)
        )
        ttk.Entry(folders, textvariable=self._output_dir).grid(
            row=1, column=1, sticky="ew", padx=PAD, pady=(PAD, 0)
        )
        ttk.Button(folders, text="Browse...", command=self._pick_output_dir).grid(
            row=1, column=2, pady=(PAD, 0)
        )

        ttk.Label(folders, text="Section:").grid(
            row=2, column=0, sticky="w", pady=(PAD, 0)
        )
        ttk.Entry(folders, textvariable=self._section).grid(
            row=2, column=1, sticky="ew", padx=PAD, pady=(PAD, 0)
        )

        lab_row = ttk.Frame(root)
        lab_row.grid(row=1, column=0, sticky="ew", pady=(SECTION_PAD, 0))
        lab_row.columnconfigure(1, weight=1)

        ttk.Label(lab_row, text="Lab:").grid(row=0, column=0, sticky="w")
        lab_combo = ttk.Combobox(
            lab_row,
            values=list(ALL_LABS.keys()),
            textvariable=self._lab_choice,
            state="readonly",
            width=24,
        )
        lab_combo.grid(row=0, column=1, sticky="w", padx=(PAD, 0))
        lab_combo.bind("<<ComboboxSelected>>", lambda _e: self._on_lab_change())

        self._config_container = ttk.Frame(root)
        self._config_container.grid(row=2, column=0, sticky="ew", pady=(SECTION_PAD, 0))
        self._config_container.columnconfigure(0, weight=1)

        run_row = ttk.Frame(root)
        run_row.grid(row=3, column=0, sticky="ew", pady=(SECTION_PAD, 0))
        run_row.columnconfigure(0, weight=1)

        self._run_btn = ttk.Button(
            run_row, text="Run Grading", command=self._run_clicked
        )
        self._run_btn.grid(row=0, column=0, sticky="ew")

        log_frame = ttk.LabelFrame(root, text="Log", padding=SECTION_PAD)
        log_frame.grid(row=4, column=0, sticky="nsew", pady=(SECTION_PAD, 0))
        log_frame.columnconfigure(0, weight=1)
        log_frame.rowconfigure(0, weight=1)

        self._log = tk.Text(
            log_frame, height=10, wrap="word", state="disabled",
            font=("Consolas", 9),
        )
        self._log.grid(row=0, column=0, sticky="nsew")
        scroll = ttk.Scrollbar(log_frame, orient="vertical", command=self._log.yview)
        scroll.grid(row=0, column=1, sticky="ns")
        self._log.configure(yscrollcommand=scroll.set)

    def _on_lab_change(self):
        preset = ALL_LABS[self._lab_choice.get()]

        for child in self._config_container.winfo_children():
            child.destroy()
        self._param_vars.clear()
        self._param_kinds.clear()

        groups = grouped_params(preset)
        if not groups:
            note = ttk.Label(
                self._config_container,
                text="No fixed values to enter for this lab.",
            )
            note.grid(row=0, column=0, sticky="w")
            return

        for i, (group_name, params) in enumerate(groups):
            section = ttk.LabelFrame(
                self._config_container, text=group_name, padding=SECTION_PAD
            )
            section.grid(
                row=i, column=0, sticky="ew",
                pady=(0 if i == 0 else PAD, 0),
            )
            section.columnconfigure(1, weight=1)

            for row, spec in enumerate(params):
                kind = spec["kind"]
                key = spec["key"]
                self._param_kinds[key] = kind

                if kind == "bool_yint":
                    var = tk.BooleanVar(value=bool(spec.get("default", True)))
                    ttk.Checkbutton(
                        section, text=spec["label"], variable=var
                    ).grid(row=row, column=0, columnspan=2, sticky="w", pady=2)
                    self._param_vars[key] = var
                else:
                    ttk.Label(section, text=spec["label"] + ":").grid(
                        row=row, column=0, sticky="w", pady=2
                    )
                    var = tk.StringVar(value=spec.get("default", ""))
                    ttk.Entry(section, textvariable=var).grid(
                        row=row, column=1, sticky="ew", padx=PAD, pady=2
                    )
                    self._param_vars[key] = var

    def _pick_input_dir(self):
        d = filedialog.askdirectory(title="Select folder of student .xlsx files")
        if d:
            self._input_dir.set(d)

    def _pick_output_dir(self):
        d = filedialog.askdirectory(title="Select folder to write graded results into")
        if d:
            self._output_dir.set(d)

    def _run_clicked(self):
        if self._running:
            return

        in_dir = Path(self._input_dir.get()) if self._input_dir.get() else None
        out_dir = Path(self._output_dir.get()) if self._output_dir.get() else None
        if not in_dir or not in_dir.is_dir():
            messagebox.showerror(APP_TITLE, "Pick a valid input folder.")
            return
        if not out_dir:
            messagebox.showerror(APP_TITLE, "Pick an output folder.")
            return

        preset = ALL_LABS[self._lab_choice.get()]

        EXTS = {".xls", ".xlsx", ".xlsm", ".xlsb", ".xltx"}
        xlsx_files = [
            p for p in in_dir.rglob("*")
            if p.is_file()
            and p.suffix.lower() in EXTS
            and not p.name.startswith("~$")
            and not p.name.startswith("._")
        ]
        tokens = file_match(preset)
        if tokens:
            low = [t.lower() for t in tokens]
            xlsx_files = [
                f for f in xlsx_files if any(t in f.name.lower() for t in low)
            ]
        if not xlsx_files:
            if tokens:
                messagebox.showwarning(
                    APP_TITLE,
                    f"No {preset['name']} files found in {in_dir}. "
                    f"Looking for filenames containing: {', '.join(tokens)}.",
                )
            else:
                messagebox.showwarning(
                    APP_TITLE,
                    f"No Excel files found in {in_dir}.",
                )
            return

        raw_params = {}
        for key, var in self._param_vars.items():
            raw_params[key] = var.get()
        try:
            configs = build_configs_from_params(preset, raw_params)
        except Exception as e:  # noqa: BLE001
            messagebox.showerror(APP_TITLE, f"Config input error:\n{e}")
            return

        self._clear_log()
        self._append_log(f"Lab:    {preset['name']}")
        self._append_log(f"Input:  {in_dir}")
        self._append_log(f"Output: {out_dir}")
        self._append_log(f"Found {len(xlsx_files)} file(s).\n")

        self._set_running(True)
        threading.Thread(
            target=self._worker,
            args=(in_dir, out_dir, configs, preset, self._section.get().strip()),
            daemon=True,
        ).start()

    def _worker(self, in_dir, out_dir, configs, preset, section):
        try:
            from .grader_api import grade_folder

            def progress(i, n, fname, result):
                status = "OK" if result["success"] else "ERROR"
                self._log_queue.put(f"[{i}/{n}] {status}  {fname}")
                if not result["success"]:
                    self._log_queue.put(f"    {result['error']}")

            results = grade_folder(
                in_dir,
                out_dir,
                output_basename=output_basename(preset),
                section=section,
                file_match=file_match(preset),
                progress_cb=progress,
                **configs,
            )

            ok = sum(1 for r in results if r["success"])
            err = len(results) - ok
            self._log_queue.put(
                f"\nDone. {ok} succeeded, {err} failed. "
                f"Wrote results and summary to {out_dir}"
            )
        except Exception as e:  # noqa: BLE001
            import traceback as _tb

            self._log_queue.put(f"\nError: {type(e).__name__}: {e}")
            self._log_queue.put(_tb.format_exc())
        finally:
            self._log_queue.put("__DONE__")

    def _drain_log_queue(self):
        try:
            while True:
                msg = self._log_queue.get_nowait()
                if msg == "__DONE__":
                    self._set_running(False)
                else:
                    self._append_log(msg)
        except queue.Empty:
            pass
        self.after(100, self._drain_log_queue)

    def _append_log(self, text):
        self._log.configure(state="normal")
        self._log.insert("end", text + "\n")
        self._log.see("end")
        self._log.configure(state="disabled")

    def _clear_log(self):
        self._log.configure(state="normal")
        self._log.delete("1.0", "end")
        self._log.configure(state="disabled")

    def _set_running(self, running):
        self._running = running
        self._run_btn.configure(
            text="Running..." if running else "Run Grading",
            state="disabled" if running else "normal",
        )


def main():
    GraderApp().mainloop()


if __name__ == "__main__":
    main()
