"""End-to-end: input file -> signals -> compressed upload -> Gemini rubric -> label."""
import os
import re
import tempfile

import requests

from . import signals as sig
from .analyzer import Analyzer
from .scoring import finalize, load_calibration


def download(url, dest_dir):
    """Accept a Google Drive share link or a direct video URL; stream to disk."""
    out = os.path.join(dest_dir, "input_video")
    if "drive.google.com" in url or "docs.google.com" in url:
        import gdown
        m = re.search(r"/d/([\w-]+)", url) or re.search(r"id=([\w-]+)", url)
        if not m:
            raise ValueError("Couldn't find a file id in that Google Drive link.")
        path = gdown.download(id=m.group(1), output=out, quiet=True)
        if not path:
            raise RuntimeError("Download failed — make sure the file is shared as "
                               "'Anyone with the link'.")
        return path
    with requests.get(url, stream=True, timeout=60) as r:
        r.raise_for_status()
        with open(out, "wb") as f:
            for chunk in r.iter_content(1 << 20):
                f.write(chunk)
    return out


def run(input_path, api_key, model=None, on_status=lambda m: None):
    calibration = load_calibration()
    with tempfile.TemporaryDirectory() as tmp:
        on_status("Measuring audio and screen activity…")
        signals = sig.extract_all(input_path)
        if signals["duration_sec"] <= 0:
            raise ValueError("This doesn't look like a playable audio/video file.")

        on_status("Compressing for analysis…")
        small = sig.compress_for_upload(input_path, os.path.join(tmp, "class.mp4"))

        on_status("Uploading to the model…")
        assessment = Analyzer(api_key, model).assess(small, signals, calibration, on_status)

    return finalize(assessment, signals, calibration)
