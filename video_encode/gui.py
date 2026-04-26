from __future__ import annotations

import queue
import threading
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, ttk

from .codec import (
    CodecConfig,
    decode_video_to_file,
    encode_file_to_video,
    run_roundtrip_integrity_check,
    verify_files_match,
)


class VideoEncodeApp(tk.Tk):
    def __init__(self) -> None:
        super().__init__()
        self.title("YouTube-Storage GUI")
        self.geometry("900x640")
        self.minsize(820, 560)

        self._queue: queue.Queue = queue.Queue()
        self._busy = False

        self.encode_input = tk.StringVar(value="testfiles/input.bin")
        self.encode_output = tk.StringVar(value="videos/output.avi")
        self.decode_input = tk.StringVar(value="videos/output.avi")
        self.decode_output = tk.StringVar(value="testfiles/decoded.bin")

        self.width_var = tk.IntVar(value=3840)
        self.height_var = tk.IntVar(value=2160)
        self.pixel_size_var = tk.IntVar(value=12)
        self.fps_var = tk.IntVar(value=60)
        self.frames_per_chunk_var = tk.IntVar(value=1)
        self.codec_var = tk.StringVar(value="x264")
        self.tolerance_var = tk.IntVar(value=120)

        self.status_var = tk.StringVar(value="Ready")
        self.progress_var = tk.DoubleVar(value=0.0)

        self._build_ui()
        self.after(75, self._drain_queue)

    def _build_ui(self) -> None:
        root = ttk.Frame(self, padding=14)
        root.pack(fill=tk.BOTH, expand=True)

        style = ttk.Style(self)
        style.configure("Title.TLabel", font=("Segoe UI Semibold", 15))
        style.configure("Section.TLabelframe", padding=12)

        ttk.Label(root, text="Video Encode / Decode", style="Title.TLabel").pack(anchor=tk.W, pady=(0, 10))

        tabs = ttk.Notebook(root)
        tabs.pack(fill=tk.BOTH, expand=True)

        encode_tab = ttk.Frame(tabs, padding=10)
        decode_tab = ttk.Frame(tabs, padding=10)
        settings_tab = ttk.Frame(tabs, padding=10)

        tabs.add(encode_tab, text="Encode")
        tabs.add(decode_tab, text="Decode")
        tabs.add(settings_tab, text="Settings")

        self._build_encode_tab(encode_tab)
        self._build_decode_tab(decode_tab)
        self._build_settings_tab(settings_tab)

        bottom = ttk.Frame(root)
        bottom.pack(fill=tk.X, pady=(10, 0))
        self.progress = ttk.Progressbar(bottom, maximum=100, variable=self.progress_var)
        self.progress.pack(fill=tk.X)
        ttk.Label(bottom, textvariable=self.status_var).pack(anchor=tk.W, pady=(8, 0))

        self.log = tk.Text(root, height=8, wrap="word")
        self.log.pack(fill=tk.BOTH, expand=False, pady=(10, 0))
        self.log.insert("end", "Application started. Configure paths and press Encode or Decode.\n")
        self.log.configure(state="disabled")

    def _build_encode_tab(self, parent: ttk.Frame) -> None:
        group = ttk.LabelFrame(parent, text="Encode File to Video", style="Section.TLabelframe")
        group.pack(fill=tk.BOTH, expand=True)

        self._file_row(group, "Input file", self.encode_input, self._browse_encode_input)
        self._file_row(group, "Output video", self.encode_output, self._browse_encode_output)

        controls = ttk.Frame(group)
        controls.pack(fill=tk.X, pady=(16, 0))
        self.encode_btn = ttk.Button(controls, text="Start Encode", command=self._start_encode)
        self.encode_btn.pack(side=tk.LEFT)

    def _build_decode_tab(self, parent: ttk.Frame) -> None:
        group = ttk.LabelFrame(parent, text="Decode Video to File", style="Section.TLabelframe")
        group.pack(fill=tk.BOTH, expand=True)

        self._file_row(group, "Input video", self.decode_input, self._browse_decode_input)
        self._file_row(group, "Output file", self.decode_output, self._browse_decode_output)

        controls = ttk.Frame(group)
        controls.pack(fill=tk.X, pady=(16, 0))
        self.decode_btn = ttk.Button(controls, text="Start Decode", command=self._start_decode)
        self.decode_btn.pack(side=tk.LEFT)
        self.verify_btn = ttk.Button(controls, text="Verify (SHA-256)", command=self._start_verify)
        self.verify_btn.pack(side=tk.LEFT, padx=(10, 0))

    def _build_settings_tab(self, parent: ttk.Frame) -> None:
        group = ttk.LabelFrame(parent, text="Codec Settings", style="Section.TLabelframe")
        group.pack(fill=tk.BOTH, expand=True)

        rows = [
            ("Frame width", self.width_var),
            ("Frame height", self.height_var),
            ("Pixel size", self.pixel_size_var),
            ("FPS", self.fps_var),
            ("Frames per chunk", self.frames_per_chunk_var),
            ("Tolerance (decode)", self.tolerance_var),
        ]

        for i, (label, var) in enumerate(rows):
            ttk.Label(group, text=label).grid(row=i, column=0, sticky="w", padx=(0, 12), pady=6)
            ttk.Entry(group, textvariable=var, width=16).grid(row=i, column=1, sticky="w", pady=6)

        ttk.Label(group, text="Codec (4 chars)").grid(row=len(rows), column=0, sticky="w", padx=(0, 12), pady=6)
        ttk.Entry(group, textvariable=self.codec_var, width=16).grid(row=len(rows), column=1, sticky="w", pady=6)

        preset_row = ttk.Frame(group)
        preset_row.grid(row=len(rows) + 1, column=0, columnspan=2, sticky="w", pady=(14, 0))
        ttk.Button(
            preset_row,
            text="Apply High-Accuracy Preset",
            command=self._apply_high_accuracy_preset,
        ).pack(side=tk.LEFT)
        self.roundtrip_btn = ttk.Button(
            preset_row,
            text="Run Round-Trip Test",
            command=self._start_roundtrip_test,
        )
        self.roundtrip_btn.pack(side=tk.LEFT, padx=(10, 0))

        hint = (
            "Tips: mp4v works for .mp4 on many systems. If writer fails, use codec=FFV1 and output extension .avi. "
            "Pixel size must divide both width and height."
        )
        ttk.Label(group, text=hint, wraplength=700, foreground="#555").grid(
            row=len(rows) + 2, column=0, columnspan=2, sticky="w", pady=(14, 0)
        )

    def _file_row(self, parent: ttk.Widget, label: str, var: tk.StringVar, browse_cmd) -> None:
        frame = ttk.Frame(parent)
        frame.pack(fill=tk.X, pady=8)
        ttk.Label(frame, text=label, width=16).pack(side=tk.LEFT)
        ttk.Entry(frame, textvariable=var).pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 8))
        ttk.Button(frame, text="Browse", command=browse_cmd).pack(side=tk.LEFT)

    def _browse_encode_input(self) -> None:
        path = filedialog.askopenfilename(title="Select file to encode")
        if path:
            self.encode_input.set(path)

    def _browse_encode_output(self) -> None:
        path = filedialog.asksaveasfilename(
            title="Save encoded video",
            defaultextension=".avi",
            filetypes=[("MP4", "*.mp4"), ("AVI", "*.avi"), ("All files", "*.*")],
        )
        if path:
            self.encode_output.set(path)

    def _browse_decode_input(self) -> None:
        path = filedialog.askopenfilename(
            title="Select encoded video",
            filetypes=[("Video files", "*.mp4 *.avi *.mov *.mkv *.webm"), ("All files", "*.*")],
        )
        if path:
            self.decode_input.set(path)

    def _browse_decode_output(self) -> None:
        path = filedialog.asksaveasfilename(title="Save decoded output", defaultextension=".bin")
        if path:
            self.decode_output.set(path)

    def _config(self) -> CodecConfig:
        codec = self.codec_var.get().strip() or "mp4v"
        if len(codec) < 4:
            codec = (codec + "mp4v")[:4]
        codec = codec[:4]

        config = CodecConfig(
            width=int(self.width_var.get()),
            height=int(self.height_var.get()),
            pixel_size=int(self.pixel_size_var.get()),
            fps=int(self.fps_var.get()),
            frames_per_chunk=int(self.frames_per_chunk_var.get()),
            codec=codec,
            tolerance=int(self.tolerance_var.get()),
        )

        if config.pixel_size <= 0:
            raise ValueError("Pixel size must be greater than 0")
        if config.width <= 0 or config.height <= 0:
            raise ValueError("Width and height must be greater than 0")
        if config.width % config.pixel_size != 0 or config.height % config.pixel_size != 0:
            raise ValueError("Pixel size must divide width and height")
        if config.frames_per_chunk <= 0:
            raise ValueError("Frames per chunk must be greater than 0")

        return config

    def _set_busy(self, busy: bool) -> None:
        self._busy = busy
        state = "disabled" if busy else "normal"
        self.encode_btn.configure(state=state)
        self.decode_btn.configure(state=state)
        self.verify_btn.configure(state=state)
        self.roundtrip_btn.configure(state=state)

    def _apply_high_accuracy_preset(self) -> None:
        self.codec_var.set("FFV1")
        self.pixel_size_var.set(12)
        self.fps_var.set(60)
        self.frames_per_chunk_var.set(1)
        self.tolerance_var.set(120)

        encode_out = self.encode_output.get().strip()
        decode_in = self.decode_input.get().strip()

        if encode_out:
            self.encode_output.set(str(Path(encode_out).with_suffix(".avi")))
        if decode_in:
            self.decode_input.set(str(Path(decode_in).with_suffix(".avi")))

        self._log("Applied high-accuracy preset: codec=FFV1, pixel_size=12, tolerance=120, output=.avi")
        self._set_status("High-accuracy preset applied")

    def _start_encode(self) -> None:
        if self._busy:
            return
        try:
            cfg = self._config()
        except Exception as exc:
            messagebox.showerror("Invalid settings", str(exc))
            return

        input_file = self.encode_input.get().strip()
        output_video = self.encode_output.get().strip()
        if not input_file or not output_video:
            messagebox.showerror("Missing values", "Set both input file and output video")
            return

        self._set_busy(True)
        self._set_status("Encoding started...")
        self._log(f"Encoding {input_file} -> {output_video}")
        threading.Thread(
            target=self._worker_encode, args=(input_file, output_video, cfg), daemon=True
        ).start()

    def _start_decode(self) -> None:
        if self._busy:
            return
        try:
            cfg = self._config()
        except Exception as exc:
            messagebox.showerror("Invalid settings", str(exc))
            return

        input_video = self.decode_input.get().strip()
        output_file = self.decode_output.get().strip()
        if not input_video or not output_file:
            messagebox.showerror("Missing values", "Set both input video and output file")
            return

        self._set_busy(True)
        self._set_status("Decoding started...")
        self._log(f"Decoding {input_video} -> {output_file}")
        threading.Thread(
            target=self._worker_decode, args=(input_video, output_file, cfg), daemon=True
        ).start()

    def _start_verify(self) -> None:
        if self._busy:
            return

        original_file = self.encode_input.get().strip()
        decoded_file = self.decode_output.get().strip()
        if not original_file or not decoded_file:
            messagebox.showerror("Missing values", "Set original input file and decoded output file first")
            return

        self._set_busy(True)
        self._set_status("Verifying file integrity...")
        self._log(f"Verifying SHA-256: {original_file} vs {decoded_file}")
        threading.Thread(target=self._worker_verify, args=(original_file, decoded_file), daemon=True).start()

    def _start_roundtrip_test(self) -> None:
        if self._busy:
            return

        try:
            cfg = self._config()
        except Exception as exc:
            messagebox.showerror("Invalid settings", str(exc))
            return

        self._set_busy(True)
        self.progress_var.set(0.0)
        self._set_status("Running round-trip integrity test...")
        self._log("Running one-click round-trip test (random input -> encode -> decode -> SHA-256 compare)")
        threading.Thread(target=self._worker_roundtrip_test, args=(cfg,), daemon=True).start()

    def _worker_encode(self, input_file: str, output_video: str, cfg: CodecConfig) -> None:
        try:
            encoded = encode_file_to_video(
                input_file,
                output_video,
                cfg,
                progress=lambda current, total, msg: self._queue.put(("progress", current, total, msg)),
            )
            self._queue.put(("done", f"Encode complete: {encoded} bytes written to video."))
        except Exception as exc:
            self._queue.put(("error", str(exc)))

    def _worker_decode(self, input_video: str, output_file: str, cfg: CodecConfig) -> None:
        try:
            decoded = decode_video_to_file(
                input_video,
                output_file,
                cfg,
                progress=lambda current, total, msg: self._queue.put(("progress", current, total, msg)),
            )

            original_path = self.encode_input.get().strip()
            if original_path and Path(original_path).exists():
                is_match, expected_hash, actual_hash = verify_files_match(original_path, output_file)
                if is_match:
                    self._queue.put(("done", f"Decode complete: {decoded} bytes recovered. Integrity check PASSED ({actual_hash})."))
                else:
                    self._queue.put(
                        (
                            "error",
                            "Decode complete but integrity check FAILED. "
                            f"Expected {expected_hash}, got {actual_hash}.",
                        )
                    )
            else:
                self._queue.put(("done", f"Decode complete: {decoded} bytes recovered."))
        except Exception as exc:
            self._queue.put(("error", str(exc)))

    def _worker_verify(self, original_file: str, decoded_file: str) -> None:
        try:
            is_match, expected_hash, actual_hash = verify_files_match(original_file, decoded_file)
            if is_match:
                self._queue.put(("done", f"Integrity check PASSED. SHA-256: {actual_hash}"))
            else:
                self._queue.put(
                    (
                        "error",
                        "Integrity check FAILED. "
                        f"Original SHA-256: {expected_hash} | Decoded SHA-256: {actual_hash}",
                    )
                )
        except Exception as exc:
            self._queue.put(("error", str(exc)))

    def _worker_roundtrip_test(self, cfg: CodecConfig) -> None:
        try:
            result = run_roundtrip_integrity_check(Path("testfiles"), cfg, sample_bytes=262_144)
            if bool(result["ok"]):
                self._queue.put(
                    (
                        "done",
                        "Round-trip test PASSED. "
                        f"SHA-256: {result['original_hash']} | "
                        f"Video: {result['encoded_video']}",
                    )
                )
            else:
                self._queue.put(
                    (
                        "error",
                        "Round-trip test FAILED. "
                        f"Original SHA-256: {result['original_hash']} | "
                        f"Decoded SHA-256: {result['decoded_hash']}",
                    )
                )
        except Exception as exc:
            self._queue.put(("error", f"Round-trip test failed to run: {exc}"))

    def _drain_queue(self) -> None:
        while True:
            try:
                item = self._queue.get_nowait()
            except queue.Empty:
                break

            tag = item[0]
            if tag == "progress":
                _, current, total, msg = item
                total = max(total, 1)
                pct = (current / total) * 100.0
                self.progress_var.set(max(0.0, min(100.0, pct)))
                self._set_status(msg)
            elif tag == "done":
                _, msg = item
                self._set_status(msg)
                self._log(msg)
                self.progress_var.set(100.0)
                self._set_busy(False)
            elif tag == "error":
                _, msg = item
                self._set_status("Operation failed")
                self._log(f"Error: {msg}")
                self._set_busy(False)
                messagebox.showerror("Operation failed", msg)

        self.after(75, self._drain_queue)

    def _set_status(self, text: str) -> None:
        self.status_var.set(text)

    def _log(self, text: str) -> None:
        self.log.configure(state="normal")
        self.log.insert("end", text + "\n")
        self.log.see("end")
        self.log.configure(state="disabled")


def run_app() -> None:
    app = VideoEncodeApp()
    app.mainloop()
