# =============================================================================
# Script: combine_spreadsheets.py
# Purpose: Fill missing Date/Time in a camera CSV (EXIF-derived) using the
#          Date/Time from OCR'd last-frame PNG timestamps.
# Author: Ashley Starr
# Last Updated: 2025-08-16
# Python: 3.8+
# Requirements: pandas
#
# Inputs:
#   1) KO CSV  -> produced by: extract_timestamps.py + split_datetime_original.py
#      Expected cols: filename, Date, Time  (plus others OK)
#   2) LF CSV  -> produced by: PNG_timestamp_extract.py + PNG_split_date_time.py
#      Expected cols: file, Date, Time  (plus others OK)
#
# How matching works:
#   - We extract a shared ID from both filenames (default regex: RCNX\d{4})
#   - Left-join LF on KO by that ID, then ONLY fill KO Date/Time where missing.
#
# Usage (CHANGE THESE PATHS):
#   Windows:
#     py combine_spreadsheets.py --ko_csv "C:\path\to\date_time_original_split.csv" ^
#                                --lf_csv "C:\path\to\AVI_last_frames\lastframe_timestamps_split.csv" ^
#                                --out_csv "C:\path\to\KO_13_2_Timestamps_FILLED.csv"
#
#   macOS/Linux:
#     python3 combine_spreadsheets.py --ko_csv "/path/to/date_time_original_split.csv" \
#                                     --lf_csv "/path/to/AVI_last_frames/lastframe_timestamps_split.csv" \
#                                     --out_csv "/path/to/KO_13_2_Timestamps_FILLED.csv"
#
# Optional:
#   --id_regex "(RCNX\d{4})"   # Change if your camera file IDs use another pattern
# =============================================================================

# ========== 0) Imports & CLI ===================================================
import argparse
import os
import re
import pandas as pd


# ========== 1) Helpers =========================================================
def is_missing(series: pd.Series) -> pd.Series:
    """True for blank or 'Not found' (case-insensitive)."""
    s = series.fillna("").astype(str).str.strip().str.lower()
    return (s == "") | (s == "not found")


def extract_id(s: pd.Series, pattern: str) -> pd.Series:
    """Extract shared ID (e.g., RCNX0020) using a regex capturing group."""
    rgx = re.compile(pattern)
    return s.astype(str).str.extract(rgx, expand=True)[0]


# ========== 2) Core Pipeline ====================================================
def run(ko_csv: str, lf_csv: str, out_csv: str, id_regex: str) -> None:
    if not os.path.isfile(ko_csv):
        raise SystemExit(f"ERROR: KO CSV not found: {ko_csv}")
    if not os.path.isfile(lf_csv):
        raise SystemExit(f"ERROR: LF CSV not found: {lf_csv}")

    ko = pd.read_csv(ko_csv, dtype=str).fillna("")
    lf = pd.read_csv(lf_csv, dtype=str).fillna("")

    # Normalize headers (defensive)
    ko.columns = [c.strip() for c in ko.columns]
    lf.columns = [c.strip() for c in lf.columns]

    # Sanity-check expected columns
    if "filename" not in ko.columns:
        raise SystemExit("ERROR: KO CSV must contain a 'filename' column.")
    if "Date" not in ko.columns or "Time" not in ko.columns:
        raise SystemExit("ERROR: KO CSV must contain 'Date' and 'Time' columns (run the split step first).")

    # LF "file" column may be named differently; fall back to the first column
    lf_file_col = "file" if "file" in lf.columns else lf.columns[0]
    if "Date" not in lf.columns or "Time" not in lf.columns:
        raise SystemExit("ERROR: LF CSV must contain 'Date' and 'Time' columns (run PNG_split_date_time.py first).")

    # Extract base IDs for joining (e.g., RCNX0020)
    ko["__base"] = extract_id(ko["filename"], id_regex)
    lf["__base"] = extract_id(lf[lf_file_col], id_regex)

    # Warn if IDs are missing
    missing_ko_ids = ko["__base"].isna().sum()
    missing_lf_ids = lf["__base"].isna().sum()
    if missing_ko_ids or missing_lf_ids:
        print(f"Warning: Missing IDs -> KO: {missing_ko_ids}, LF: {missing_lf_ids}. "
              f"Regex used: {id_regex}")

    # Keep only the last-frame Date/Time we need
    lf_small = lf[["__base", "Date", "Time"]].rename(columns={"Date": "__LF_Date", "Time": "__LF_Time"})

    # Left-join LF onto KO
    m = ko.merge(lf_small, on="__base", how="left")

    # Masks where KO is missing but LF has values
    mask_date_missing = is_missing(m["Date"]) & m["__LF_Date"].fillna("").ne("")
    mask_time_missing = is_missing(m["Time"]) & m["__LF_Time"].fillna("").ne("")

    # Counters before filling
    n_before_date = mask_date_missing.sum()
    n_before_time = mask_time_missing.sum()

    # Fill ONLY where KO missing
    m.loc[mask_date_missing, "Date"] = m.loc[mask_date_missing, "__LF_Date"]
    m.loc[mask_time_missing, "Time"] = m.loc[mask_time_missing, "__LF_Time"]

    # Drop helper columns
    m = m.drop(columns=["__LF_Date", "__LF_Time", "__base"], errors="ignore")

    # Save
    out_dir = os.path.dirname(out_csv)
    if out_dir and not os.path.isdir(out_dir):
        os.makedirs(out_dir, exist_ok=True)
    m.to_csv(out_csv, index=False)

    print(f"✅ Filled KO timestamps saved to:\n{out_csv}")
    print(f"Filled from LF -> Date: {n_before_date} row(s), Time: {n_before_time} row(s)")


# ========== 3) CLI / Main =======================================================
def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="Fill missing Date/Time in KO CSV using OCR'd last-frame Date/Time."
    )
    p.add_argument("--ko_csv", required=True, help='EXIF-derived KO CSV (after split). Example: "C:\\path\\to\\date_time_original_split.csv"')
    p.add_argument("--lf_csv", required=True, help='OCR-derived LF CSV (after split). Example: "C:\\path\\to\\AVI_last_frames\\lastframe_timestamps_split.csv"')
    p.add_argument("--out_csv", required=True, help='Output CSV path. Example: "C:\\path\\to\\KO_13_2_Timestamps_FILLED.csv"')
    p.add_argument("--id_regex", default=r"(RCNX\d{4})",
                   help="Regex (with one capture group) to extract the shared file ID. Default: (RCNX\\d{4})")
    return p.parse_args()


if __name__ == "__main__":
    args = parse_args()
    run(args.ko_csv, args.lf_csv, args.out_csv, args.id_regex)