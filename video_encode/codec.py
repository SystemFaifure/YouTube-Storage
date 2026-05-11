from __future__ import annotations

from dataclasses import dataclass
import hashlib
import os
from pathlib import Path
from typing import Callable, Optional, Tuple

import cv2
import numpy as np

ProgressCallback = Optional[Callable[[int, int, str], None]]


@dataclass
class CodecConfig:
    width: int = 3840
    height: int = 2160
    pixel_size: int = 8
    fps: int = 60
    frames_per_chunk: int = 1
    codec: str = "MJLS"
    tolerance: int = 60

    @property
    def bytes_per_frame(self) -> int:
        return ((self.width // self.pixel_size) * (self.height // self.pixel_size)) // 4


_COLOR_LUT_BGR = np.array(
    [
        [0, 0, 0],      # 00 -> black
        [0, 0, 255],    # 01 -> red
        [0, 255, 0],    # 10 -> green
        [255, 0, 0],    # 11 -> blue
    ],
    dtype=np.uint8,
)


def estimate_frame_count(input_file: str | Path, config: CodecConfig) -> int:
    size = Path(input_file).stat().st_size
    if size == 0:
        return 0
    return (size + config.bytes_per_frame - 1) // config.bytes_per_frame


def _build_frame(chunk: bytes, config: CodecConfig) -> np.ndarray:
    grid_w = config.width // config.pixel_size
    grid_h = config.height // config.pixel_size
    cell_count = grid_w * grid_h

    grid = np.full((cell_count, 3), 255, dtype=np.uint8)
    if chunk:
        raw = np.frombuffer(chunk, dtype=np.uint8)
        symbols = np.empty(raw.size * 4, dtype=np.uint8)
        symbols[0::4] = (raw >> 6) & 0b11
        symbols[1::4] = (raw >> 4) & 0b11
        symbols[2::4] = (raw >> 2) & 0b11
        symbols[3::4] = raw & 0b11
        used = min(symbols.size, cell_count)
        grid[:used] = _COLOR_LUT_BGR[symbols[:used]]

    grid = grid.reshape((grid_h, grid_w, 3))
    frame = np.repeat(np.repeat(grid, config.pixel_size, axis=0), config.pixel_size, axis=1)
    return frame


def _decode_frame(frame: np.ndarray, config: CodecConfig) -> Tuple[bytes, bool]:
    center = config.pixel_size // 2
    sampled = frame[center:: config.pixel_size, center:: config.pixel_size, :]
    cells = sampled.reshape((-1, 3))

    out = bytearray()
    current = 0
    count = 0

    for b, g, r in cells:
        if b > config.tolerance and g > config.tolerance and r > config.tolerance:
            return bytes(out), True

        max_channel = int(np.argmax((b, g, r)))
        max_value = (b, g, r)[max_channel]
        if max_value <= config.tolerance:
            bits = 0
        elif max_channel == 2:
            bits = 1
        elif max_channel == 1:
            bits = 2
        else:
            bits = 3

        current = ((current << 2) | bits) & 0xFF
        count += 1
        if count == 4:
            out.append(current)
            count = 0

    return bytes(out), False


def encode_file_to_video(
    input_file: str | Path,
    output_video: str | Path,
    config: CodecConfig,
    progress: ProgressCallback = None,
) -> int:
    input_path = Path(input_file)
    output_path = Path(output_video)

    if not input_path.exists():
        raise FileNotFoundError(f"Input file does not exist: {input_path}")

    output_path.parent.mkdir(parents=True, exist_ok=True)

    fourcc = cv2.VideoWriter_fourcc(*config.codec)
    writer = cv2.VideoWriter(str(output_path), fourcc, config.fps, (config.width, config.height))
    if not writer.isOpened():
        raise RuntimeError(
            "Could not open video writer. Try codec='LJPG'/'MJPG' with .avi output, or verify your OpenCV build supports the selected codec."
        )

    total_chunks = estimate_frame_count(input_path, config)
    written = 0

    with input_path.open("rb") as fh:
        index = 0
        while True:
            chunk = fh.read(config.bytes_per_frame)
            if not chunk:
                break

            frame = _build_frame(chunk, config)
            for _ in range(max(config.frames_per_chunk, 1)):
                writer.write(frame)

            index += 1
            written += len(chunk)
            if progress:
                progress(index, max(total_chunks, 1), f"Encoded chunk {index}/{max(total_chunks, 1)}")

    writer.release()
    if progress:
        progress(max(total_chunks, 1), max(total_chunks, 1), f"Done. Encoded {written} bytes.")
    return written


def decode_video_to_file(
    input_video: str | Path,
    output_file: str | Path,
    config: CodecConfig,
    progress: ProgressCallback = None,
) -> int:
    input_path = Path(input_video)
    output_path = Path(output_file)

    if not input_path.exists():
        raise FileNotFoundError(f"Input video does not exist: {input_path}")

    output_path.parent.mkdir(parents=True, exist_ok=True)

    cap = cv2.VideoCapture(str(input_path))
    if not cap.isOpened():
        raise RuntimeError(f"Could not open video: {input_path}")

    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    step = max(config.frames_per_chunk, 1)
    total_chunks = max((total_frames + step - 1) // step, 1)

    written = 0
    chunk_index = 0
    frame_index = 0

    with output_path.open("wb") as out:
        while True:
            ok, frame = cap.read()
            if not ok:
                break

            if frame_index % step != 0:
                frame_index += 1
                continue

            chunk, end_of_stream = _decode_frame(frame, config)
            if chunk:
                out.write(chunk)
                written += len(chunk)

            chunk_index += 1
            if progress:
                progress(chunk_index, total_chunks, f"Decoded chunk {chunk_index}/{total_chunks}")

            frame_index += 1
            if end_of_stream:
                break

    cap.release()
    if progress:
        progress(total_chunks, total_chunks, f"Done. Decoded {written} bytes.")
    return written


def file_sha256(path: str | Path) -> str:
    file_path = Path(path)
    if not file_path.exists():
        raise FileNotFoundError(f"File does not exist: {file_path}")

    digest = hashlib.sha256()
    with file_path.open("rb") as fh:
        while True:
            block = fh.read(1024 * 1024)
            if not block:
                break
            digest.update(block)
    return digest.hexdigest()


def verify_files_match(original_file: str | Path, decoded_file: str | Path) -> tuple[bool, str, str]:
    original_hash = file_sha256(original_file)
    decoded_hash = file_sha256(decoded_file)
    return original_hash == decoded_hash, original_hash, decoded_hash


def run_roundtrip_integrity_check(
    work_dir: str | Path,
    config: CodecConfig,
    sample_bytes: int = 262_144,
) -> dict[str, str | bool | int]:
    base = Path(work_dir)
    base.mkdir(parents=True, exist_ok=True)

    input_file = base / "roundtrip_input.bin"
    encoded_video = base / ("roundtrip_encoded.avi" if config.codec.upper() == "MJLS" else "roundtrip_encoded.mp4")
    decoded_file = base / "roundtrip_decoded.bin"

    input_file.write_bytes(os.urandom(sample_bytes))

    encode_file_to_video(input_file, encoded_video, config)
    decode_video_to_file(encoded_video, decoded_file, config)

    match, original_hash, decoded_hash = verify_files_match(input_file, decoded_file)

    return {
        "ok": match,
        "original_hash": original_hash,
        "decoded_hash": decoded_hash,
        "input_bytes": input_file.stat().st_size,
        "decoded_bytes": decoded_file.stat().st_size,
        "input_file": str(input_file),
        "encoded_video": str(encoded_video),
        "decoded_file": str(decoded_file),
    }