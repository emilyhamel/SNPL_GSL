PROJECT: Trail Camera Timestamp Tools

OVERVIEW
These scripts extract, OCR, and reconcile timestamps from trail camera media. Workflow:
1) Pull EXIF DateTimeOriginal (images) and file Modified times (AVIs).
2) Convert DateTimeOriginal into separate Date/Time columns.
3) Save the LAST frame of each AVI as a PNG for OCR.
4) OCR the overlay timestamp from those PNGs.
5) Split the OCR’d timestamp into Date/Time.
6) Combine: fill missing EXIF Date/Time with OCR’d Date/Time.

REQUIREMENTS
- Python 3.8+ (works with 3.13 as well)
- pip packages:
  pandas
  pillow
  opencv-python
  pytesseract
  numpy
- System dependency: Tesseract OCR
  Default Windows path used by scripts:
  C:\Users\<You>\AppData\Local\Programs\Tesseract-OCR\tesseract.exe
  (Override with --tesseract_cmd in PNG_timestamp_extract.py)

NO-ADMIN SETUP (Windows)
1) Install Python for “Just Me” and check “Add Python to PATH”.
2) Install packages to your user profile:
   py -m pip install --upgrade pip
   py -m pip install --user pandas pillow opencv-python pytesseract numpy
3) Install Tesseract OCR to a user path (no admin), e.g.:
   %LOCALAPPDATA%\Programs\Tesseract-OCR\
   Verify:
   "C:\Users\<You>\AppData\Local\Programs\Tesseract-OCR\tesseract.exe" --version
4) Point the OCR script at your Tesseract:
   --tesseract_cmd "C:\Users\<You>\AppData\Local\Programs\Tesseract-OCR\tesseract.exe"

DIRECTORY HINTS
- Use raw strings (r"...") or escape backslashes in Windows paths.
- Keep each camera’s AVI_last_frames next to its media for clarity.
- Scripts are SINGLE-FOLDER tools and non-recursive.

SCRIPTS & USAGE (CHANGE THE EXAMPLE PATHS)
1) extract_timestamps.py
   Purpose: Read one media folder; record EXIF DateTimeOriginal for JPG/JPEG
            and Last-Modified for AVIs into a CSV.
   Example:
     py extract_timestamps.py --folder "C:\cams\KO_2_1" --output "C:\out\date_time_original.csv"

2) split_datetime_original.py
   Purpose: Split DateTimeOriginal into Date (YYYY-MM-DD) and Time (HH:MM:SS).
   Example:
     py split_datetime_original.py --input "C:\out\date_time_original.csv" --output "C:\out\date_time_original_split.csv"

3) AVI_picture_extract.py
   Purpose: Save the LAST frame of each AVI as a PNG (for OCR).
   Output: <folder>\AVI_last_frames\<video_basename>_lastframe.png
   Example:
     py AVI_picture_extract.py --folder "C:\cams\KO_2_1"

4) PNG_timestamp_extract.py
   Purpose: OCR timestamps from last-frame PNG/JPGs; robust parsing & voting.
   Outputs: lastframe_timestamps.csv  (columns: file, timestamp, raw_ocr)
   Example:
     py PNG_timestamp_extract.py --image_folder "C:\cams\KO_2_1\AVI_last_frames" ^
                                 --output_csv   "C:\cams\KO_2_1\AVI_last_frames\lastframe_timestamps.csv" ^
                                 --tesseract_cmd "C:\Users\<You>\AppData\Local\Programs\Tesseract-OCR\tesseract.exe" ^
                                 --save_debug --debug_dir "C:\cams\KO_2_1\AVI_last_frames\_ocr_debug"

   Note: After this step, SPOT-CHECK timestamps against the images (see Accuracy below).
         If any are wrong, edit the CSV before continuing.

5) PNG_split_date_time.py
   Purpose: Split the OCR "timestamp" into Date and Time columns.
   Example:
     py PNG_split_date_time.py --input "C:\cams\KO_2_1\AVI_last_frames\lastframe_timestamps.csv" ^
                               --output "C:\cams\KO_2_1\AVI_last_frames\lastframe_timestamps_split.csv"

6) combine_spreadsheets.py
   Purpose: Fill missing Date/Time in the EXIF-derived CSV using the OCR CSV.
   Example:
     py combine_spreadsheets.py --ko_csv "C:\out\date_time_original_split.csv" ^
                                --lf_csv "C:\cams\KO_2_1\AVI_last_frames\lastframe_timestamps_split.csv" ^
                                --out_csv "C:\out\KO_2_1_Timestamps_FILLED.csv"
   Advanced: If your file IDs aren’t like RCNX0000, set:
     --id_regex "(YOURID\d{4})"

ACCURACY
- Current measured error rate ≈ 0.879%.
- Estimated interval: true error rate is between 0.879% − 0.396% and 0.879% + 0.396%,
  i.e., ≈ 0.48% to 1.28%.
- Always spot-check a few rows (morning/noon/night) against image overlays.

TROUBLESHOOTING
- TesseractNotFoundError or “no such file”: Pass a correct --tesseract_cmd.
- “Image load failed” in AVI extract: Confirm codec is supported and files aren’t locked.
- Empty Date/Time after split: The value isn’t in “YYYY-MM-DD HH:MM:SS” — fix the OCR CSV first.
- Nothing filled during combine: Check the ID regex and that both files contain matching IDs.

CREDITS
- Author: Ashley Starr
- Acknowledgements: National Audubon Society – project team & collaborators
- License: (choose one: MIT/Apache/Proprietary)