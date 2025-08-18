# =============================================================================
# Script: AVI_picture_extract.py
# Purpose: For each .AVI in ONE folder, save a PNG of the LAST frame to a
#          subfolder named "AVI_last_frames". Useful for OCR timestamp scripts.
# Author: Ashley Starr
# Last Updated: 2025-08-17
# Python: 3.8+
# Requirements: opencv-python
#
# Usage (CHANGE THESE PATHS):
#   Windows (CMD/PowerShell):
#     py AVI_picture_extract.py --folder "C:\path\to\your\data"
#
#   macOS/Linux:
#     python3 AVI_picture_extract.py --folder "/path/to/your/data"
#
# Notes:
# - Writes images to: <folder>\AVI_last_frames\<video_basename>_lastframe.png
# - This scans ONLY the provided folder (non-recursive).
# - If the last frame seek fails (some codecs), a fallback method is tried.
# =============================================================================

# ========== 0) Imports & Globals ==============================================
import os
import argparse
import cv2
from typing import Tuple


# ========== 1) Helper Functions ===============================================
def read_last_frame(video_path: str) -> Tuple[bool, "cv2.Mat | None"]:
    """
    Attempt to read the last frame of an AVI using multiple strategies.

    Returns:
        (success, frame)
    """
    cap = cv2.VideoCapture(video_path)
    if not cap.isOpened():
        return False, None

    # Strategy A: direct seek to last index
    frame_count = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))  # may be 0/unknown for some codecs
    if frame_count and frame_count > 1:
        cap.set(cv2.CAP_PROP_POS_FRAMES, frame_count - 1)
        ok, frame = cap.read()
        if ok and frame is not None:
            cap.release()
            return True, frame

    # Strategy B: ratio seek near end
    cap.set(cv2.CAP_PROP_POS_AVI_RATIO, 0.999)  # seek to ~end
    ok, frame = cap.read()
    if ok and frame is not None:
        cap.release()
        return True, frame

    # Strategy C: sequential read to end (slow for long videos, but reliable)
    cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
    last = None
    while True:
        ok, f = cap.read()
        if not ok:
            break
        last = f
    cap.release()
    return (last is not None), last


# ========== 2) Core Pipeline ====================================================
def process_folder(folder: str) -> None:
    if not os.path.isdir(folder):
        raise SystemExit(f"ERROR: Folder does not exist: {folder}")

    out_dir = os.path.join(folder, "AVI_last_frames")
    os.makedirs(out_dir, exist_ok=True)

    avi_files = sorted(f for f in os.listdir(folder) if f.lower().endswith(".avi"))
    if not avi_files:
        print("No .avi files found in the folder.")
        return

    print(f"Found {len(avi_files)} AVI file(s). Processing...")

    ok_count = 0
    fail_count = 0

    for filename in avi_files:
        path = os.path.join(folder, filename)
        success, frame = read_last_frame(path)

        if success and frame is not None:
            base = os.path.splitext(filename)[0]
            out_path = os.path.join(out_dir, f"{base}_lastframe.png")
            if cv2.imwrite(out_path, frame):
                ok_count += 1
                print(f"Saved last frame: {filename} -> {out_path}")
            else:
                fail_count += 1
                print(f"ERROR: Failed to write image for: {filename}")
        else:
            fail_count += 1
            print(f"ERROR: Could not read last frame of: {filename}")

    print(f"\nSummary: {ok_count} saved, {fail_count} failed, out of {len(avi_files)} AVI file(s).")
    print(f"Output folder: {out_dir}")


# ========== 3) CLI / Main =======================================================
def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="Extract the LAST frame from each .AVI in ONE folder and save as PNG."
    )
    p.add_argument(
        "--folder",
        required=True,
        help='Folder containing .AVI files (non-recursive). Example (Windows): "C:\\path\\to\\your\\KO_2_1"',
    )
    return p.parse_args()


if __name__ == "__main__":
    args = parse_args()
    process_folder(args.folder)