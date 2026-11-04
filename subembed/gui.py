"""
Desktop Graphical User Interface for SubEmbed.
Lightweight, native, responsive Tkinter desktop GUI for fast container softsub embedding.
"""

import os
import subprocess
import threading
import time
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, ttk
from typing import Optional

from .core import (
    LANGUAGE_MAP,
    VALID_SUB_EXTS,
    VALID_VIDEO_EXTS,
    SubEmbedError,
    auto_detect_subtitles,
    detect_language_from_filename,
    embed_subtitles,
    probe_media,
)


def format_bytes(b: int) -> str:
    for unit in ["B", "KB", "MB", "GB"]:
        if b < 1024:
            return f"{b:3.1f} {unit}"
        b /= 1024
    return f"{b:.1f} TB"


class SubEmbedGUI(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("SubEmbed - Lossless Subtitle Container Embedder")
        self.geometry("720x620")
        self.minsize(640, 540)

        # Style configuration
        self.style = ttk.Style(self)
        try:
            self.style.theme_use("clam")
        except Exception:
            pass

        self.last_output_path: Optional[Path] = None

        self._init_ui()

    def _init_ui(self):
        # Configure colors and styles
        bg_color = "#1e1e2e"
        card_bg = "#252538"
        fg_color = "#cdd6f4"
        accent_color = "#89b4fa"
        accent_hover = "#b4befe"

        self.configure(bg=bg_color)

        self.style.configure(".", background=bg_color, foreground=fg_color, font=("Sans", 10))
        self.style.configure("TLabel", background=bg_color, foreground=fg_color)
        self.style.configure("Header.TLabel", font=("Sans", 16, "bold"), foreground=accent_color)
        self.style.configure("SubHeader.TLabel", font=("Sans", 9), foreground="#a6adc8")
        self.style.configure("Status.TLabel", font=("Sans", 9, "bold"), foreground="#a6e3a1")

        self.style.configure("Card.TFrame", background=card_bg, relief="flat")
        self.style.configure("TFrame", background=bg_color)
        self.style.configure("TCheckbutton", background=bg_color, foreground=fg_color)

        self.style.configure("Action.TButton", font=("Sans", 11, "bold"), background=accent_color, foreground="#11111b")
        self.style.map("Action.TButton", background=[("active", accent_hover)])

        # Main container with padding
        container = ttk.Frame(self, padding=20)
        container.pack(fill=tk.BOTH, expand=True)

        # Header
        header_frame = ttk.Frame(container)
        header_frame.pack(fill=tk.X, pady=(0, 15))
        title_lbl = ttk.Label(header_frame, text="SubEmbed", style="Header.TLabel")
        title_lbl.pack(anchor="w")
        desc_lbl = ttk.Label(
            header_frame,
            text="Container Softsub Embedder • 100% Lossless Video & Audio Stream Copy (No Re-encoding)",
            style="SubHeader.TLabel"
        )
        desc_lbl.pack(anchor="w", pady=(2, 0))

        # --- Section 1: Video File Selection ---
        video_box = ttk.LabelFrame(container, text=" 1. Select Video ", padding=12)
        video_box.pack(fill=tk.X, pady=(0, 12))

        v_row = ttk.Frame(video_box)
        v_row.pack(fill=tk.X)
        self.video_var = tk.StringVar()
        self.video_entry = ttk.Entry(v_row, textvariable=self.video_var, font=("Sans", 10))
        self.video_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 8))
        self.video_var.trace_add("write", self._on_video_changed)

        btn_browse_v = ttk.Button(v_row, text="Browse Video...", command=self._browse_video)
        btn_browse_v.pack(side=tk.RIGHT)

        self.video_info_lbl = ttk.Label(video_box, text="No video selected", style="SubHeader.TLabel")
        self.video_info_lbl.pack(anchor="w", pady=(6, 0))

        # --- Section 2: Subtitle File Selection ---
        sub_box = ttk.LabelFrame(container, text=" 2. Select Subtitle File ", padding=12)
        sub_box.pack(fill=tk.X, pady=(0, 12))

        s_row = ttk.Frame(sub_box)
        s_row.pack(fill=tk.X)
        self.sub_var = tk.StringVar()
        self.sub_entry = ttk.Entry(s_row, textvariable=self.sub_var, font=("Sans", 10))
        self.sub_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 8))
        self.sub_var.trace_add("write", self._on_sub_changed)

        btn_browse_s = ttk.Button(s_row, text="Browse Sub...", command=self._browse_subtitle)
        btn_browse_s.pack(side=tk.RIGHT)

        self.sub_info_lbl = ttk.Label(sub_box, text="Supports .srt, .vtt, .ass, .ssa (auto-detects from video folder)", style="SubHeader.TLabel")
        self.sub_info_lbl.pack(anchor="w", pady=(6, 0))

        # --- Section 3: Track Metadata & Options ---
        opt_box = ttk.LabelFrame(container, text=" 3. Track Settings & Output Format ", padding=12)
        opt_box.pack(fill=tk.X, pady=(0, 15))

        meta_grid = ttk.Frame(opt_box)
        meta_grid.pack(fill=tk.X)

        ttk.Label(meta_grid, text="Language:").grid(row=0, column=0, sticky="w", padx=(0, 5), pady=4)
        self.lang_var = tk.StringVar(value="eng")
        lang_combo = ttk.Combobox(meta_grid, textvariable=self.lang_var, width=12, values=["eng", "spa", "fra", "deu", "ita", "por", "rus", "jpn", "zho", "kor", "ara", "hin", "urd"])
        lang_combo.grid(row=0, column=1, sticky="w", padx=(0, 20), pady=4)

        ttk.Label(meta_grid, text="Track Title:").grid(row=0, column=2, sticky="w", padx=(0, 5), pady=4)
        self.title_var = tk.StringVar(value="English")
        self.title_entry = ttk.Entry(meta_grid, textvariable=self.title_var, width=22)
        self.title_entry.grid(row=0, column=3, sticky="w", padx=(0, 5), pady=4)

        ttk.Label(meta_grid, text="Format:").grid(row=1, column=0, sticky="w", padx=(0, 5), pady=4)
        self.fmt_var = tk.StringVar(value="Auto (Preserve)")
        fmt_combo = ttk.Combobox(meta_grid, textvariable=self.fmt_var, state="readonly", width=14, values=["Auto (Preserve)", "MP4 (.mp4)", "Matroska (.mkv)"])
        fmt_combo.grid(row=1, column=1, sticky="w", padx=(0, 20), pady=4)

        self.default_var = tk.BooleanVar(value=True)
        chk_default = ttk.Checkbutton(meta_grid, text="Make this the Default active track", variable=self.default_var)
        chk_default.grid(row=1, column=2, columnspan=2, sticky="w", pady=4)

        self.force_var = tk.BooleanVar(value=False)
        chk_force = ttk.Checkbutton(opt_box, text="Overwrite output if already exists", variable=self.force_var)
        chk_force.pack(anchor="w", pady=(5, 0))

        # --- Section 4: Action & Status ---
        action_frame = ttk.Frame(container)
        action_frame.pack(fill=tk.X, pady=(5, 0))

        self.btn_run = ttk.Button(
            action_frame,
            text="⚡ Embed Subtitles Losslessly (0% Quality Loss)",
            style="Action.TButton",
            command=self._start_embedding
        )
        self.btn_run.pack(fill=tk.X, ipady=8)

        self.status_lbl = ttk.Label(action_frame, text="Ready", style="Status.TLabel")
        self.status_lbl.pack(anchor="w", pady=(10, 0))

        # Result actions (hidden initially)
        self.result_frame = ttk.Frame(action_frame)
        self.result_frame.pack(fill=tk.X, pady=(8, 0))

        self.btn_play = ttk.Button(self.result_frame, text="▶ Play Video", command=self._play_output)
        self.btn_open_folder = ttk.Button(self.result_frame, text="📂 Open Folder", command=self._open_folder)

    def _browse_video(self):
        filetypes = [
            ("Video Files", "*.mp4 *.mkv *.mov *.webm *.avi *.m4v *.ts"),
            ("All Files", "*.*")
        ]
        chosen = filedialog.askopenfilename(title="Select Video File", filetypes=filetypes)
        if chosen:
            self.video_var.set(chosen)

    def _browse_subtitle(self):
        filetypes = [
            ("Subtitle Files", "*.srt *.vtt *.ass *.ssa *.sub"),
            ("All Files", "*.*")
        ]
        chosen = filedialog.askopenfilename(title="Select Subtitle File", filetypes=filetypes)
        if chosen:
            self.sub_var.set(chosen)

    def _on_video_changed(self, *args):
        path_str = self.video_var.get().strip()
        if not path_str:
            self.video_info_lbl.config(text="No video selected")
            return

        p = Path(path_str)
        if not p.is_file():
            self.video_info_lbl.config(text="File does not exist", foreground="#f38ba8")
            return

        # Attempt to probe video
        try:
            info = probe_media(p)
            v_codec = info["video_streams"][0]["codec"] if info["video_streams"] else "unknown"
            a_codec = info["audio_streams"][0]["codec"] if info["audio_streams"] else "none"
            existing_subs = len(info["subtitle_streams"])
            self.video_info_lbl.config(
                text=f"{info['filename']}  |  {format_bytes(info['size_bytes'])}  |  Video: {v_codec}  |  Audio: {a_codec}  |  Existing Subs: {existing_subs}",
                foreground="#a6adc8"
            )
        except Exception as e:
            self.video_info_lbl.config(text=f"Selected: {p.name} (Probe error: {e})", foreground="#fab387")

        # Auto-detect matching subtitle in folder if subtitle box is empty
        if not self.sub_var.get().strip():
            matches = auto_detect_subtitles(p)
            if matches:
                self.sub_var.set(str(matches[0]))

    def _on_sub_changed(self, *args):
        path_str = self.sub_var.get().strip()
        if not path_str:
            self.sub_info_lbl.config(text="Supports .srt, .vtt, .ass, .ssa", foreground="#a6adc8")
            return

        p = Path(path_str)
        if not p.is_file():
            self.sub_info_lbl.config(text="Subtitle file does not exist", foreground="#f38ba8")
            return

        code, name = detect_language_from_filename(p.name)
        self.lang_var.set(code)
        self.title_var.set(name)
        self.sub_info_lbl.config(text=f"Loaded: {p.name} (Detected: {name} / {code})", foreground="#a6e3a1")

    def _start_embedding(self):
        v_str = self.video_var.get().strip()
        s_str = self.sub_var.get().strip()

        if not v_str:
            messagebox.showwarning("Missing Input", "Please select a video file.")
            return
        if not s_str:
            messagebox.showwarning("Missing Input", "Please select a subtitle file.")
            return

        v_path = Path(v_str)
        s_path = Path(s_str)

        if not v_path.is_file():
            messagebox.showerror("Error", f"Video file not found: {v_path}")
            return
        if not s_path.is_file():
            messagebox.showerror("Error", f"Subtitle file not found: {s_path}")
            return

        # Target container format
        fmt_choice = self.fmt_var.get()
        target_fmt = None
        if "MP4" in fmt_choice:
            target_fmt = "mp4"
        elif "Matroska" in fmt_choice or "MKV" in fmt_choice:
            target_fmt = "mkv"

        self.btn_run.config(state="disabled")
        self.status_lbl.config(text="Muxing container streams... (this takes only a second)", foreground="#f9e2af")
        self.btn_play.pack_forget()
        self.btn_open_folder.pack_forget()

        def worker():
            try:
                sub_spec = [{
                    "path": s_path,
                    "language": self.lang_var.get().strip() or "eng",
                    "title": self.title_var.get().strip() or "English"
                }]
                result = embed_subtitles(
                    video_path=v_path,
                    subtitles=sub_spec,
                    default_track_index=0 if self.default_var.get() else -1,
                    force_overwrite=self.force_var.get(),
                    target_format=target_fmt
                )
                self.after(0, self._on_success, result)
            except Exception as e:
                self.after(0, self._on_failure, str(e))

        t = threading.Thread(target=worker, daemon=True)
        t.start()

    def _on_success(self, res: dict):
        self.btn_run.config(state="normal")
        out_p = Path(res["output_video"])
        self.last_output_path = out_p

        msg = f"✓ Success! Saved to {out_p.name} ({format_bytes(res['output_size_bytes'])} in {res['elapsed_seconds']}s)"
        self.status_lbl.config(text=msg, foreground="#a6e3a1")

        self.btn_play.pack(side=tk.LEFT, padx=(0, 10))
        self.btn_open_folder.pack(side=tk.LEFT)

        messagebox.showinfo(
            "Embedding Complete",
            f"Subtitles embedded successfully with 0% video quality loss!\n\n"
            f"Saved to:\n{out_p}\n\n"
            f"Elapsed time: {res['elapsed_seconds']}s\n"
            f"Size: {format_bytes(res['output_size_bytes'])}"
        )

    def _on_failure(self, err_msg: str):
        self.btn_run.config(state="normal")
        self.status_lbl.config(text=f"Failed: {err_msg[:60]}...", foreground="#f38ba8")
        messagebox.showerror("Error Embedding Subtitles", err_msg)

    def _play_output(self):
        if self.last_output_path and self.last_output_path.exists():
            subprocess.Popen(["xdg-open", str(self.last_output_path)])

    def _open_folder(self):
        if self.last_output_path and self.last_output_path.exists():
            subprocess.Popen(["xdg-open", str(self.last_output_path.parent)])


def launch_gui():
    app = SubEmbedGUI()
    app.mainloop()


if __name__ == "__main__":
    launch_gui()
