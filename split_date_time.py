# =============================================================================
# Script: split_date_time.py
# Purpose: Read a CSV, split the "DateTimeOriginal" column into separate
#          "Date" (YYYY-MM-DD) and "Time" (HH:MM:SS) columns, and write a new CSV.
# Author: Ashley Starr
# Last Updated: 2025-08-17
# Python: 3.8+
# Requirements: pandas
#
# Usage (CHANGE THESE PATHS):
#   Windows (CMD/PowerShell):
#     py split_datetime_original.py --input "C:\path\to\your\date_time_original.csv" ^
#                                   --output "C:\path\to\your\date_time_original_split.csv"
#
#   macOS/Linux:
#     python3 split_datetime_original.py --input "/path/to/your/date_time_original.csv" \
#                                        --output "/path/to/your/date_time_original_split.csv"
#
# Options:
#   --col        Name of the datetime column to split (default: DateTimeOriginal)
#
# Notes:
# - Accepts dates like "YYYY:MM:DD HH:MM:SS", "YYYY-MM-DD HH:MM:SS", or "YYYY/MM/DD HH:MM:SS".
# - Rows with missing/invalid values (e.g., "Not found", "Error: ...") become "Not found" in Date/Time.
# - Keeps all original columns and appends "Date" and "Time".
# =============================================================================

# ========== 0) Imports & Globals ==============================================
import argparse
import os
import pandas as pd
import re


# ========== 1) Core Function ===================================================
def split_datetime_column(df: pd.DataFrame, col: str) -> pd.DataFrame:
    """
    Split the specified datetime column into 'Date' (YYYY-MM-DD) and 'Time' (HH:MM:SS).

    Rules:
      - Valid patterns:
          YYYY:MM:DD HH:MM:SS
          YYYY-MM-DD HH:MM:SS
          YYYY/MM/DD HH:MM:SS
      - Invalid/empty/'Not found'/'Error:' -> 'Not found' in both Date and Time
    """
    if col not in df.columns:
        raise SystemExit(f"ERROR: Column '{col}' not found in CSV. Available columns: {list(df.columns)}")

    # Normalize to string and strip whitespace
    dt_series = df[col].fillna("").astype(str).str.strip()

    # Flag obviously bad entries early
    bad_mask = dt_series.eq("") | dt_series.str.match(r"^(Not found|Error:)", flags=re.IGNORECASE)

    # Extract date + time parts with a permissive regex (colon, dash, or slash separators for date)
    parts = dt_series.str.extract(r"^\s*(\d{4}[:/\-]\d{2}[:/\-]\d{2})\s+(\d{2}:\d{2}:\d{2})\s*$")

    # Build Date column: replace ":" and "/" with "-" in the date part
    date_col = parts[0].where(~bad_mask, other="Not found").fillna("Not found")
    date_col = date_col.str.replace(r"[:/]", "-", regex=True)

    # Build Time column: keep HH:MM:SS as-is
    time_col = parts[1].where(~bad_mask, other="Not found").fillna("Not found")

    # Optional: enforce strict HH:MM:SS; anything else -> Not found
    time_col = time_col.where(time_col.str.match(r"^\d{2}:\d{2}:\d{2}$") | time_col.eq("Not found"), other="Not found")

    df["Date"] = date_col
    df["Time"] = time_col
    return df


# ========== 2) CLI / Entrypoint ===============================================
def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="Split a DateTime column into Date (YYYY-MM-DD) and Time (HH:MM:SS)."
    )
    p.add_argument(
        "--input",
        required=True,
        help='Path to input CSV. Example (Windows): "C:\\path\\to\\your\\date_time_original.csv"',
    )
    p.add_argument(
        "--output",
        required=True,
        help='Path to output CSV. Example (Windows): "C:\\path\\to\\your\\date_time_original_split.csv"',
    )
    p.add_argument(
        "--col",
        default="DateTimeOriginal",
        help="Name of the datetime column to split (default: DateTimeOriginal)",
    )
    return p.parse_args()


def main():
    args = parse_args()

    if not os.path.isfile(args.input):
        raise SystemExit(f"ERROR: Input file not found: {args.input}")

    df = pd.read_csv(args.input)
    df = split_datetime_column(df, args.col)
    df.to_csv(args.output, index=False)
    print(f"✅ Done! File with separate Date and Time columns saved to: {args.output}")


if __name__ == "__main__":
    main()