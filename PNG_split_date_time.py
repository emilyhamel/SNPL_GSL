# =============================================================================
# Script: PNG_split_date_time.py
# Purpose: Read the OCR output CSV from PNG_timestamp_extract.py and split the
#          "timestamp" column into "Date" (YYYY-MM-DD) and "Time" (HH:MM:SS).
# Author: Ashley Starr
# Last Updated: 2025-08-16
# Python: 3.8+
# Requirements: pandas
#
# Usage (CHANGE THESE PATHS):
#   Windows (CMD/PowerShell):
#     py PNG_split_date_time.py --input "C:\path\to\your\AVI_last_frames\lastframe_timestamps.csv" ^
#                               --output "C:\path\to\your\AVI_last_frames\lastframe_timestamps_split.csv"
#
#   macOS/Linux:
#     python3 PNG_split_date_time.py --input "/path/to/AVI_last_frames/lastframe_timestamps.csv" \
#                                     --output "/path/to/AVI_last_frames/lastframe_timestamps_split.csv"
#
# Notes:
# - Expects columns from the OCR script: file, timestamp, raw_ocr
# - Handles Excel-like values such as '2024-08-01 06:31:27 and ="2024-08-01 06:31:27"
# - Keeps all original columns and appends Date and Time (reordered after 'timestamp')
# =============================================================================

# ========== 0) Imports & Globals ==============================================
import os
import re
import argparse
import pandas as pd

# Regex: handles optional leading apostrophe and/or Excel ="...":
#   '2024-08-01 06:31:27
#   ="2024-08-01 06:31:27"
#   2024-08-01 06:31:27
TS_RE = re.compile(
    r"""^\s*                 # leading spaces
        (?:'=?"?|=?"?)?      # optional ' or =" or ="
        (\d{4})-(\d{2})-(\d{2})   # YYYY-MM-DD
        \s+
        (\d{2}):(\d{2}):(\d{2})   # HH:MM:SS
        "?$                   # optional closing quote
    """,
    re.VERBOSE,
)


# ========== 1) Helpers =========================================================
def split_ts(value: str):
    """Return (Date, Time) from a timestamp string, or ('Not found','Not found')."""
    if not isinstance(value, str):
        return ("Not found", "Not found")
    v = value.strip()
    m = TS_RE.match(v)
    if not m:
        return ("Not found", "Not found")
    y, M, d, h, mi, s = m.groups()
    return (f"{y}-{M}-{d}", f"{h}:{mi}:{s}")


def reorder_columns_with_date_time(df: pd.DataFrame) -> pd.DataFrame:
    """Place Date/Time after 'timestamp' if present; otherwise just append."""
    base = ["file", "timestamp", "Date", "Time"]
    cols = list(df.columns)
    if "timestamp" in cols and {"Date", "Time"}.issubset(cols):
        rest = [c for c in cols if c not in base]
        return df[[c for c in base if c in df.columns] + rest]
    return df


# ========== 2) Core Pipeline ====================================================
def run(input_csv: str, output_csv: str) -> None:
    if not os.path.isfile(input_csv):
        raise SystemExit(f"ERROR: Input CSV not found: {input_csv}")

    df = pd.read_csv(input_csv, dtype=str).fillna("")
    if "timestamp" not in df.columns:
        raise SystemExit("ERROR: Column 'timestamp' not found in input CSV.")

    # Split timestamps
    dates, times = zip(*(split_ts(v) for v in df["timestamp"]))
    df["Date"] = list(dates)
    df["Time"] = list(times)

    # Quick summary for QC
    parsed_ok = sum(d != "Not found" and t != "Not found" for d, t in zip(dates, times))
    total = len(df)
    print(f"Parsed {parsed_ok}/{total} rows into Date/Time.")

    # Reorder columns nicely
    df = reorder_columns_with_date_time(df)

    # Write output
    out_dir = os.path.dirname(output_csv)
    if out_dir and not os.path.isdir(out_dir):
        os.makedirs(out_dir, exist_ok=True)
    df.to_csv(output_csv, index=False)
    print(f"✅ Done! Saved split file to: {output_csv}")


# ========== 3) CLI / Main =======================================================
def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="Split 'timestamp' column into 'Date' and 'Time' from OCR CSV."
    )
    p.add_argument(
        "--input",
        required=True,
        help='Path to input CSV from PNG_timestamp_extract.py. Example (Windows): "C:\\path\\to\\your\\AVI_last_frames\\lastframe_timestamps.csv"',
    )
    p.add_argument(
        "--output",
        required=True,
        help='Path to output CSV. Example (Windows): "C:\\path\\to\\your\\AVI_last_frames\\lastframe_timestamps_split.csv"',
    )
    return p.parse_args()


if __name__ == "__main__":
    args = parse_args()
    run(args.input, args.output)