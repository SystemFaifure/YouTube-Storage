from __future__ import annotations

import argparse
from pathlib import Path

from video_encode.codec import CodecConfig, run_roundtrip_integrity_check


def main() -> int:
    parser = argparse.ArgumentParser(description="Run encode/decode corruption check using SHA-256.")
    parser.add_argument("--work-dir", default="testfiles", help="Directory for generated test files")
    parser.add_argument("--bytes", type=int, default=262_144, help="Random test file size in bytes")
    parser.add_argument("--high-accuracy", action="store_true", help="Use MJPG + larger pixel size preset")
    args = parser.parse_args()

    cfg = CodecConfig()
    if args.high_accuracy:
        cfg.codec = "MJPG"
        cfg.pixel_size = 8
        cfg.tolerance = 120

    result = run_roundtrip_integrity_check(Path(args.work_dir), cfg, sample_bytes=max(1, args.bytes))

    print("Round-trip integrity check")
    print(f"  codec:        {cfg.codec}")
    print(f"  pixel_size:   {cfg.pixel_size}")
    print(f"  input bytes:  {result['input_bytes']}")
    print(f"  decoded bytes:{result['decoded_bytes']}")
    print(f"  input hash:   {result['original_hash']}")
    print(f"  decoded hash: {result['decoded_hash']}")
    print(f"  encoded video:{result['encoded_video']}")

    if result["ok"]:
        print("RESULT: PASS")
        return 0

    print("RESULT: FAIL")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
