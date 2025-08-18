# =============================================================================
# Script: extract_timestamps.py
# Purpose: Scan ONE folder, collect EXIF DateTimeOriginal for JPG/JPEG images
#          and Last-Modified timestamps for .AVI videos, then write to CSV.
# Author: Ashley Starr
# Last Updated: 2025-08-17
# Python: 3.8+
# Requirements: pillow, pandas
#
# Usage (CHANGE THESE PATHS):
#   Windows (CMD/PowerShell):
#     py extract_timestamps.py --folder "C:\path\to\your\data" --output "C:\path\to\your\date_time_original.csv"
#
#   macOS/Linux:
#     python3 extract_timestamps.py --folder "/path/to/your/data" --output "/path/to/your/date_time_original.csv"
#
# Notes:
# - This script scans ONLY the provided folder (non-recursive).
# - DateTimeOriginal is preserved as reported by the camera (e.g., "YYYY:MM:DD HH:MM:SS").
# - Last-Modified is reported in local time ("YYYY-MM-DD HH:MM:SS").
# - Files other than .jpg/.jpeg/.avi are ignored.
# =============================================================================

# ========== 0) Imports & Globals ==============================================
import os
import argparse
from datetime import datetime
from typing import Dict, List, Optional

import pandas as pd
from PIL import Image
from PIL.ExifTags import TAGS


# ========== 1) Helper Functions ===============================================
def get_datetime_original(img_path: str) -> str:
    """
    Return the EXIF DateTimeOriginal string for a JPEG/JPG image if present.
    If not found, returns "Not found". On error, returns "Error: <message>".
    """
    try:
        with Image.open(img_path) as img:
            exif = None
            # Try both EXIF access methods for Pillow compatibility
            try:
                exif = img._getexif()
            except Exception:
                exif = None
            if not exif:
                try:
                    exif = img.getexif()
                except Exception:
                    exif = None

            if exif:
                items = dict(exif) if not isinstance(exif, dict) else exif
                for tag_id, value in items.items():
                    tag = TAGS.get(tag_id, tag_id)
                    if tag == "DateTimeOriginal":
                        return str(value)
        return "Not found"
    except Exception as e:
        return f"Error: {e}"


def get_last_modified(path: str) -> str:
    """
    Return last-modified timestamp (local time) in 'YYYY-MM-DD HH:MM:SS' format,
    or 'Error: <message>' if retrieval fails.
    """
    try:
        mod_ts = os.path.getmtime(path)
        return datetime.fromtimestamp(mod_ts).strftime("%Y-%m-%d %H:%M:%S")
    except Exception as e:
        return f"Error: {e}"


def scan_folder(folder: str) -> List[Dict[str, str]]:
    """
    Non-recursively scan ONE folder, extracting:
      - For .jpg/.jpeg: EXIF DateTimeOriginal
      - For .avi:       Last modified timestamp
    Returns list of row dicts ready for CSV.
    """
    rows: List[Dict[str, str]] = []
    image_count = 0
    video_count = 0

    for filename in sorted(os.listdir(folder)):
        path = os.path.join(folder, filename)
        if not os.path.isfile(path):
            continue

        lower = filename.lower()

        if lower.endswith((".jpg", ".jpeg")):
            dto = get_datetime_original(path)
            if dto.startswith("Error:"):
                print(f"{filename}: Error reading file ({dto[7:].strip()})")
            elif dto == "Not found":
                print(f"{filename}: DateTimeOriginal NOT found.")
            else:
                print(f"{filename}: DateTimeOriginal = {dto}")
            rows.append(
                {
                    "filename": filename,
                    "type": "image",
                    "DateTimeOriginal": dto,
                    "LastModified": "",
                }
            )
            image_count += 1

        elif lower.endswith(".avi"):
            lm = get_last_modified(path)
            if lm.startswith("Error:"):
                print(f"{filename}: {lm}")
            else:
                print(f"{filename}: Last modified = {lm}")
            rows.append(
                {
                    "filename": filename,
                    "type": "video",
                    "DateTimeOriginal": "",
                    "LastModified": lm,
                }
            )
            video_count += 1

        else:
            # Ignore other file types
            continue

    print(f"\nSummary: {image_count} image(s), {video_count} video(s) processed.")
    return rows


def save_csv(rows: List[Dict[str, str]], output_csv: str) -> None:
    """
    Save collected rows to CSV (UTF-8, no index). Ensures headers exist even if no rows.
    """
    columns = ["filename", "type", "DateTimeOriginal", "LastModified"]
    df = pd.DataFrame(rows, columns=columns)
    df.to_csv(output_csv, index=False)
    print(f"Done! Results saved to {output_csv}")


# ========== 2) Core Pipeline ====================================================
def run(folder: str, output_csv: str) -> None:
    if not os.path.isdir(folder):
        raise SystemExit(f"ERROR: Folder does not exist: {folder}")
    rows = scan_folder(folder)
    save_csv(rows, output_csv)


# ========== 3) CLI / Main =======================================================
def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Scan ONE folder (non-recursive) to extract EXIF DateTimeOriginal from JPG/JPEG "
            "and Last-Modified from AVI, writing results to CSV."
        )
    )
    parser.add_argument(
        "--folder",
        required=True,
        help='Folder to scan. Example (Windows): "C:\\path\\to\\your\\KO_2_1"  |  (macOS/Linux): "/path/to/your/KO_2_1"',
    )
    parser.add_argument(
        "--output",
        required=True,
        help='Output CSV file. Example (Windows): "C:\\path\\to\\your\\date_time_original.csv"  |  (macOS/Linux): "/path/to/your/date_time_original.csv"',
    )
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()
    run(args.folder, args.output)