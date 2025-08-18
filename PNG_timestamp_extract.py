# =============================================================================
# Script: PNG_timestamp_extract.py
# Purpose: OCR timestamps from LAST-FRAME PNG/JPGs (e.g., made by AVI_picture_extract.py)
#          and write a CSV with the parsed timestamps. Includes robust parsing,
#          variant image preprocessing, and weighted voting across candidates.
# Author: Ashley Starr
# Last Updated: 2025-08-17
# Python: 3.9+
# Requirements: opencv-python, pytesseract, numpy
#
# ⚠️ Recommendation:
#   After this runs, SPOT-CHECK the timestamps against the images. If any are wrong,
#   fix them directly in the output CSV BEFORE running follow-up scripts.
#
# Usage (CHANGE THESE PATHS):
#   Windows (CMD/PowerShell):
#     py PNG_timestamp_extract.py --image_folder "C:\path\to\your\data\AVI_last_frames" ^
#                                 --output_csv   "C:\path\to\your\lastframe_timestamps.csv" ^
#                                 --save_debug   --debug_dir "C:\path\to\your\_ocr_debug"
#
#   macOS/Linux:
#     python3 PNG_timestamp_extract.py --image_folder "/path/to/data/AVI_last_frames" \
#                                      --output_csv   "/path/to/lastframe_timestamps.csv" \
#                                      --save_debug   --debug_dir "/path/to/_ocr_debug"
#
# Notes:
# - Accepts .png/.jpg/.jpeg files in ONE folder (non-recursive).
# - Output CSV columns: file, timestamp (quoted for Excel), raw_ocr
# - Explicit Tesseract path is set via --tesseract_cmd (default is Ashley's path).
# =============================================================================

# ========== 0) Imports & CLI Config ===========================================
import os
import re
import csv
import cv2
import pytesseract
import numpy as np
import argparse
import datetime as dt
from collections import defaultdict
from datetime import datetime

# ========== 1) CLI / User Options =============================================
def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description=(
            "OCR timestamps from LAST-FRAME images (PNG/JPG) produced from AVI files. "
            "Uses multiple preprocessing variants and weighted voting to pick the best timestamp."
        )
    )
    p.add_argument("--image_folder", required=True,
                   help='Folder with *_lastframe.png images. Example (Win): "C:\\path\\to\\your\\data\\AVI_last_frames"')
    p.add_argument("--output_csv", required=True,
                   help='Output CSV path. Example (Win): "C:\\path\\to\\your\\lastframe_timestamps.csv"')
    p.add_argument("--tesseract_cmd", default=r"C:\Users\Ashley.Starr\AppData\Local\Programs\Tesseract-OCR\tesseract.exe",
                   help="Full path to Tesseract executable. Change if different on your machine.")
    p.add_argument("--save_debug", action="store_true",
                   help="If set, saves debug crops and candidate logs.")
    p.add_argument("--debug_dir", default=None,
                   help="Directory for debug outputs (default: <image_folder>\\_ocr_debug).")
    p.add_argument("--elite_margin", type=float, default=0.8,
                   help="How far the top candidate must lead to skip voting (default: 0.8).")
    return p.parse_args()


# ========== 2) Globals (set from args in main) =================================
EXTS = {".jpg", ".jpeg", ".png"}
TESS_CFG = (
    "--oem 3 --psm 7 "
    "-c classify_bln_numeric_mode=1 "
    "-c tessedit_char_whitelist=0123456789:- "
    "-c preserve_interword_spaces=1"
)

# Flexible timestamp regexes
FLEX_PAT = re.compile(r'(20\d{2})\D{0,4}(\d{2})\D{0,4}(\d{2})\D{0,6}(\d{1,2})\D{0,4}(\d{2})\D{0,4}(\d{2})')
DATE_THEN_TIME_1OR2H = re.compile(r'(20\d{2})\D{0,5}(\d{2})\D{0,5}(\d{2}).{0,12}?(\d{1,2})\D{0,3}(\d{2})\D{0,3}(\d{2})')
TS_PATTERNS = [
    r'(20\d{2})-(\d{2})-(\d{2})[ T](\d{2}):(\d{2}):(\d{2})',
    r'(20\d{2})(\d{2})(\d{2})[ T]?(\d{2})(\d{2})(\d{2})',
    r'(20\d{2})-(\d{2})-(\d{2}).{0,3}(\d{2}).{0,3}(\d{2}).{0,3}(\d{2})',
]
_SLASH_LIKE = r'[\/\\\u2215\u2044\uFF0F\uFF3C]'
SLASH_RE = re.compile(_SLASH_LIKE)

# Weights (ROI & variant)
ROI_WEIGHT = {"left70": 3.2, "full": 1.4, "mid60": -1.0, "right60": -1.5}
VARIANT_WEIGHT = {
    "cubic|morph_inv":     3.6,
    "cubic|blur_otsu_inv": 2.4,
    "cubic|otsu_inv":      1.2,
    "cubic|adapt_inv":     0.8,
    "nearest|otsu_inv":   -1.0,
    "nearest|adapt_inv":  -1.2,
}


# ========== 3) Utilities =======================================================
def ensure_dir(path: str):
    if path and not os.path.isdir(path):
        os.makedirs(path, exist_ok=True)

TRIPLET_FIELD = re.compile(r'([:\s])(\d{3})(?=[:\s]|$)')
def repair_time_triplets(s: str) -> str:
    """Fix OCR artifacts like ':107:' or ':159' -> keep last two digits when valid (00–59)."""
    def _fix(m):
        tri = m.group(2)
        last2 = tri[-2:]
        if tri[0] in '10' and last2.isdigit() and 0 <= int(last2) <= 59:
            return m.group(1) + last2
        return m.group(1) + tri
    return TRIPLET_FIELD.sub(_fix, s)

def normalize_ocr(s: str) -> str:
    if not s:
        return ""
    t = s.replace("\n", " ").strip()
    t = (t.replace('O', '0').replace('o', '0')
           .replace('I', '1').replace('l', '1')
           .replace('S', '5').replace('B', '8')
           .replace('—', '-').replace('–', '-'))
    t = SLASH_RE.sub('', t)
    t = re.sub(r'\s+', ' ', t)
    t = re.sub(r':{2,}', ':', t)
    t = re.sub(r'-{2,}', '-', t)
    return t


# ========== 4) Parsing Helpers =================================================
def _pairify(two_digit_maybe_split: str) -> int:
    m = re.match(r'^\s*(\d)\D?(\d)\s*$', two_digit_maybe_split)
    if not m:
        raise ValueError("not a pair")
    return int(m.group(1) + m.group(2))

def _grab_fields_loose(t: str):
    """Legacy loose extractor expecting pairs; used as a noisy fallback."""
    ymatch = re.search(r'(20\d{2})', t)
    if not ymatch:
        return None
    y = int(ymatch.group(1))
    i = ymatch.end()

    def next_pair(start_idx):
        m = re.search(r'(\d\D?\d)', t[start_idx:])
        if not m:
            return None, None
        span_end = start_idx + m.end()
        val = _pairify(m.group(1))
        return val, span_end

    fields = []
    idx = i
    for _ in range(5):
        val, idx = next_pair(idx)
        if val is None:
            return None
        fields.append(val)

    M, d, h, m_, s_ = fields
    try:
        dtobj = dt.datetime(y, M, d, h, m_, s_)
        return dtobj, (y, M, d, h, m_, s_)
    except ValueError:
        return None

def parse_timestamp_flex(raw: str):
    if not raw:
        return None, None
    t = normalize_ocr(raw)
    t = repair_time_triplets(t)

    # (0) Anchor on date, then colonized time (1–2 digit hour)
    dm = re.search(r'(20\d{2})\D{0,4}(\d{2})\D{0,4}(\d{2})', t)
    if dm:
        y, M, d = map(int, dm.groups())
        rest = t[dm.end():]
        mtime = re.search(r'(\d{1,2})\s*:\s*(\d{2})\s*:\s*(\d{2})', rest)
        if mtime:
            h, m_, s_ = map(int, mtime.groups())
            try:
                return dt.datetime(y, M, d, h, m_, s_), (y, M, d, h, m_, s_)
            except ValueError:
                pass

    # (1) Flexible 1–2 digit hour
    m = DATE_THEN_TIME_1OR2H.search(t)
    if m:
        y, M, d, h, m_, s_ = map(int, m.groups())
        try:
            return dt.datetime(y, M, d, h, m_, s_), (y, M, d, h, m_, s_)
        except ValueError:
            pass

    # (2) Legacy loose pairs
    loose = _grab_fields_loose(t)
    if loose:
        return loose

    # (3) Big flexible pattern
    m = FLEX_PAT.search(t)
    if m:
        y, M, d, h, m_, s_ = map(int, m.groups())
        try:
            return dt.datetime(y, M, d, h, m_, s_), (y, M, d, h, m_, s_)
        except ValueError:
            pass

    # (4) Strict fallbacks
    for pat in TS_PATTERNS:
        m = re.search(pat, t)
        if m:
            y, M, d, h, m_, s_ = map(int, m.groups())
            try:
                return dt.datetime(y, M, d, h, m_, s_), (y, M, d, h, m_, s_)
            except ValueError:
                continue
    return None, None


# ========== 5) ROI & Variants ==================================================
def moving_groups(idxs):
    if not idxs:
        return
    start = prev = idxs[0]
    for i in idxs[1:]:
        if i == prev + 1:
            prev = i
            continue
        yield (start, prev)
        start = prev = i
    yield (start, prev)

def find_top_black_banner(gray: np.ndarray):
    """Locate the dark banner at the top where overlay lives; fallback to top 9% if unsure."""
    h, w = gray.shape
    top = gray[: int(h * 0.25), :]
    row_means = top.mean(axis=1)
    idxs = np.where(row_means < 60)[0].tolist()

    best = None
    for y0, y1 in moving_groups(idxs):
        if y0 <= 5 and (y1 - y0 + 1) >= 10:
            if best is None or (y1 - y0) > (best[1] - best[0]):
                best = (y0, y1)

    if best is None:
        y0, y1 = 0, max(16, int(h * 0.09))
    else:
        y0, y1 = best

    y0 = max(0, y0 - 2)
    y1 = min(h, y1 + 2)
    return y0, y1

def variant_images(gray_small: np.ndarray):
    """Generate binarized/rescaled variants for OCR."""
    out = []
    scales = [
        ("cubic",   cv2.resize(gray_small, None, fx=2.2, fy=2.2, interpolation=cv2.INTER_CUBIC)),
        ("nearest", cv2.resize(gray_small, None, fx=2.4, fy=2.4, interpolation=cv2.INTER_NEAREST)),
    ]
    for up_tag, big in scales:
        _, th = cv2.threshold(big, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
        out.append((f"{up_tag}|otsu_inv", 255 - th))
        if up_tag == "cubic":
            bl = cv2.GaussianBlur(big, (3, 3), 0)
            _, th2 = cv2.threshold(bl, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
            out.append((f"{up_tag}|blur_otsu_inv", 255 - th2))
            k = cv2.getStructuringElement(cv2.MORPH_RECT, (3, 2))
            closed = cv2.morphologyEx(th2, cv2.MORPH_CLOSE, k, iterations=1)
            out.append((f"{up_tag}|morph_inv", 255 - closed))
        ad = cv2.adaptiveThreshold(big, 255, cv2.ADAPTIVE_THRESH_MEAN_C,
                                   cv2.THRESH_BINARY, 31, 5)
        out.append((f"{up_tag}|adapt_inv", 255 - ad))
    return out


# ========== 6) Weights & Selection ============================================
def rough_layout_bonus(raw: str) -> float:
    t = normalize_ocr(raw)
    c = t.count(':')
    bonus = 0.0
    if 2 <= c <= 3:
        bonus += 0.4
    if re.search(r':[0-9]{3}(?=[:\s]|$)', t):
        bonus -= 0.6
    if re.search(r':[0-9]{2}\s*:\s*[0-9]{2}', t):
        bonus += 0.2
    return bonus

def candidate_weight(roi_tag: str, var_tag: str, raw: str) -> float:
    base = ROI_WEIGHT.get(roi_tag, 0.0) + VARIANT_WEIGHT.get(var_tag, 0.0)
    return base + rough_layout_bonus(raw)

PREFERRED_ROIS = {"left70", "full"}
PREFERRED_VARS = {"cubic|morph_inv", "cubic|blur_otsu_inv"}

def weighted_mode(values, weights):
    tally = defaultdict(float)
    for v, w in zip(values, weights):
        if w > 0:
            tally[v] += w
    if not tally:
        return None
    return sorted(tally.items(), key=lambda kv: (-kv[1], kv[0]))[0][0]

def choose_elite_candidate(all_cands, elite_margin: float):
    """Pick a single 'elite' candidate if it clearly leads and comes from preferred paths."""
    if not all_cands:
        return None
    ranked = sorted(all_cands, key=lambda c: c["w"], reverse=True)
    top = ranked[0]
    nxt = ranked[1]["w"] if len(ranked) > 1 else -1e9
    preferred = (top["roi"] in PREFERRED_ROIS) and (top["var"] in PREFERRED_VARS)
    if preferred and (top["w"] >= nxt + elite_margin):
        return top
    return None

def choose_by_weighted_whole_string(all_cands):
    by_key = defaultdict(float)
    for c in all_cands:
        if c["w"] > 0:
            by_key[c["canon"]] += c["w"]
    if not by_key:
        return None, None
    best_key = sorted(by_key.items(), key=lambda kv: (-kv[1], kv[0]))[0][0]
    reps = [c for c in all_cands if c["canon"] == best_key]
    rep = sorted(reps, key=lambda c: (-c["w"], c["roi"]))[0]
    return rep["dt"], rep

def choose_by_weighted_fields(all_cands):
    parts_list = [c["parts"] for c in all_cands]
    weights = [c["w"] for c in all_cands]
    fields = list(zip(*parts_list))
    voted = []
    for col in fields:
        v = weighted_mode(col, weights)
        if v is None:
            return None, None
        voted.append(v)
    y, M, d, h, mm, ss = voted
    try:
        consensus = dt.datetime(y, M, d, h, mm, ss)
    except ValueError:
        return choose_by_weighted_whole_string(all_cands)
    # choose representative with highest weight (prefer exact match)
    rep = None
    best = -1e9
    for c in all_cands:
        score = c["w"] if c["dt"] == consensus else c["w"] - 0.5
        if score > best:
            best, rep = score, c
    return consensus, rep


# ========== 7) OCR Pipeline ====================================================
def collect_candidates_from_roi(roi_gray, roi_tag, debug_lines):
    cand = []
    for vtag, im in variant_images(roi_gray):
        raw = pytesseract.image_to_string(im, config=TESS_CFG).strip().replace("\n", " ")
        dtobj, parts = parse_timestamp_flex(raw)
        if dtobj:
            canon = dtobj.strftime("%Y-%m-%d %H:%M:%S")
            w = candidate_weight(roi_tag, vtag, raw)
            cand.append({
                "dt": dtobj,
                "canon": canon,
                "parts": parts,
                "raw": raw,
                "roi": roi_tag,
                "var": vtag,
                "img": im,
                "w": w
            })
            debug_lines.append(f"[{roi_tag}|{vtag}] OK :: {raw} -> {canon}  (w={w:+.2f})")
        else:
            debug_lines.append(f"[{roi_tag}|{vtag}] .. :: {raw}")
    return cand

def process_image(path, save_debug: bool, debug_dir: str, elite_margin: float):
    base = os.path.splitext(os.path.basename(path))[0]
    bgr = cv2.imread(path, cv2.IMREAD_COLOR)
    if bgr is None:
        return None, ""

    gray = cv2.cvtColor(bgr, cv2.COLOR_BGR2GRAY)
    y0, y1 = find_top_black_banner(gray)
    band = gray[y0:y1, :]
    H, W = band.shape

    rois = [
        ("full",   band),
        ("left70", band[:, : int(W * 0.70)]),
        ("mid60",  band[:, int(W * 0.20): int(W * 0.80)]),
        ("right60",band[:, int(W * 0.40):]),
    ]

    all_cands = []
    debug_lines = []
    for rtag, roi in rois:
        all_cands.extend(collect_candidates_from_roi(roi, rtag, debug_lines))

    if save_debug:
        ensure_dir(debug_dir)
        with open(os.path.join(debug_dir, f"{base}_candidates.txt"), "w", encoding="utf-8") as f:
            f.write("\n".join(debug_lines))
        cv2.imwrite(os.path.join(debug_dir, f"{base}_band.png"), band)

    if not all_cands:
        return None, ""

    # Try “elite” winner first (strong candidate from preferred path)
    elite = choose_elite_candidate(all_cands, elite_margin)
    if elite is not None:
        if save_debug:
            cv2.imwrite(os.path.join(debug_dir, f"{base}_best_{elite['roi']}_{elite['var']}.png"), elite["img"])
        return elite["dt"], elite["raw"]

    # Weighted field vote → whole-string fallback → absolute top
    dt_obj, rep = choose_by_weighted_fields(all_cands)
    if dt_obj is None:
        rep = max(all_cands, key=lambda c: c["w"])
        dt_obj = rep["dt"]

    if save_debug and rep is not None:
        cv2.imwrite(os.path.join(debug_dir, f"{base}_best_{rep['roi']}_{rep['var']}.png"), rep["img"])

    return dt_obj, (rep["raw"] if rep else "")


# ========== 8) Driver ==========================================================
def main():
    args = parse_args()

    # Explicit Tesseract path (override-able)
    pytesseract.pytesseract.tesseract_cmd = args.tesseract_cmd

    image_folder = args.image_folder
    output_csv = args.output_csv
    debug_dir = args.debug_dir or os.path.join(image_folder, "_ocr_debug")
    save_debug = bool(args.save_debug)
    elite_margin = float(args.elite_margin)

    if not os.path.isdir(image_folder):
        raise SystemExit(f"ERROR: Image folder not found: {image_folder}")

    files = sorted(
        os.path.join(image_folder, f)
        for f in os.listdir(image_folder)
        if os.path.splitext(f)[1].lower() in EXTS
    )

    if not files:
        print("No images found.")
        return

    rows = [("file", "timestamp", "raw_ocr")]
    for p in files:
        dt_obj, raw = process_image(p, save_debug=save_debug, debug_dir=debug_dir, elite_margin=elite_margin)
        ts_str = f'="{dt_obj.strftime("%Y-%m-%d %H:%M:%S")}"' if dt_obj else ""
        print(f"Processing: {os.path.basename(p)} ... {ts_str or '[unreadable]'}")
        rows.append((os.path.basename(p), ts_str, raw or ""))

    ensure_dir(os.path.dirname(output_csv))
    with open(output_csv, "w", newline="", encoding="utf-8") as f:
        csv.writer(f).writerows(rows)
    print(f"\nSaved: {output_csv}")
    if save_debug:
        print(f"Debug artifacts: {debug_dir}")


if __name__ == "__main__":
    main()