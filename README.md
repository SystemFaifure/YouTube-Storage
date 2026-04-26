# YouTube-Storage (Python + GUI)

This repository now includes a full Python implementation with a desktop GUI for encoding binary files into video frames and decoding videos back into files.

## What It Does

- Encodes any file into color-coded video frames
- Decodes a generated video back into the original bytes
- Provides a GUI for selecting files, tuning settings, and tracking progress

## Tech Stack

- Python 3.9+
- OpenCV-Python
- OpenCV-Python-Headless
- NumPy
- Packaging

## Quick Start (Windows)

1. Start "YouTube-StorageSetup.bat" script
2. Launch the GUI script "YouTube-StorageRun.bat"

## GUI Workflow

### Encode

1. Select an input file (any binary file).
2. Choose output video path ('.mp4' or '.avi').
3. Click **Start Encode**.

### Decode

1. Select encoded input video.
2. Choose output file path.
3. Click **Start Decode**.

### Verify Integrity (No Corruption Check)

1. Ensure **Input file** (Encode tab) points to the original file.
2. Ensure **Output file** (Decode tab) points to the recovered file.
3. Click **Verify (SHA-256)**.

The app reports PASS/FAIL based on SHA-256 hash equality.

## Recommended Settings

- Width: '2560'
- Height: '1440'
- Pixel size: '4'
- FPS: '30'
- Frames per chunk: '1'
- Codec: 'FFV1' for '.avi'

If your machine cannot open/write AVI with 'FFV1', use:

- Codec:		'MJPG'/'mp4v'
- Output extension:	'.avi'/'.mp4'

One-click option: In **Settings**, click **Apply High-Accuracy Preset**.
This sets 'FFV1', 'pixel_size=8', 'tolerance=120', and updates output extension to '.avi'.

You can also click **Run Round-Trip Test** in **Settings** to run a full random-file test and get a GUI PASS/FAIL result.

## Notes

- Encoder and decoder must use matching settings (resolution, pixel size, frames-per-chunk, tolerance).
- Compression artifacts can reduce decode accuracy with some codecs/settings. If accuracy is critical, prefer less lossy settings (for example, 'FFV1' + '.avi') and larger pixel sizes.
- After decode, the GUI automatically runs a hash check when the original input file path is available.
