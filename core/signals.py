"""Deterministic audio/visual signals extracted with ffmpeg.

These are cheap, objective measurements that complement the LLM's judgement:
- silence ratio / long silences  -> dead air, disengaged class, tech trouble
- loudness                        -> mic problems (too quiet / clipping)
- screen change rate              -> is anything happening on screen?

They are reported as evidence and used for sanity flags, NOT as the main score:
a quiet class can still be excellent (kids solving a problem silently), so we
let the model interpret them in context.
"""
import json
import re
import shutil
import subprocess

FFMPEG = shutil.which("ffmpeg") or "ffmpeg"
FFPROBE = shutil.which("ffprobe") or "ffprobe"


def _run(cmd, timeout=1800):
    return subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)


def probe(path):
    out = _run([FFPROBE, "-v", "error", "-print_format", "json",
                "-show_format", "-show_streams", path])
    info = json.loads(out.stdout or "{}")
    fmt = info.get("format", {})
    streams = info.get("streams", [])
    v = next((s for s in streams if s.get("codec_type") == "video"), None)
    a = next((s for s in streams if s.get("codec_type") == "audio"), None)
    return {
        "duration_sec": float(fmt.get("duration", 0) or 0),
        "has_video": v is not None,
        "has_audio": a is not None,
        "resolution": f"{v.get('width')}x{v.get('height')}" if v else None,
    }


def silence_stats(path, duration, noise_db=-35, min_len=2.0):
    """Fraction of the class that is silent, and the longest silent stretch."""
    out = _run([FFMPEG, "-hide_banner", "-nostats", "-i", path, "-vn",
                "-af", f"silencedetect=noise={noise_db}dB:d={min_len}",
                "-f", "null", "-"])
    durs = [float(x) for x in re.findall(r"silence_duration:\s*([\d.]+)", out.stderr)]
    starts = [float(x) for x in re.findall(r"silence_start:\s*([\d.]+)", out.stderr)]
    total = sum(durs)
    longest = max(durs) if durs else 0.0
    longest_at = starts[durs.index(longest)] if durs and len(starts) == len(durs) else None
    return {
        "silence_ratio": round(total / duration, 3) if duration else 0.0,
        "silent_stretches_over_2s": len(durs),
        "long_silences_over_15s": sum(1 for d in durs if d >= 15),
        "longest_silence_sec": round(longest, 1),
        "longest_silence_at": _ts(longest_at) if longest_at is not None else None,
    }


def loudness(path):
    out = _run([FFMPEG, "-hide_banner", "-nostats", "-i", path, "-vn",
                "-af", "volumedetect", "-f", "null", "-"])
    mean = re.search(r"mean_volume:\s*(-?[\d.]+) dB", out.stderr)
    peak = re.search(r"max_volume:\s*(-?[\d.]+) dB", out.stderr)
    return {
        "mean_volume_db": float(mean.group(1)) if mean else None,
        "max_volume_db": float(peak.group(1)) if peak else None,
    }


def screen_activity(path, duration, threshold=0.25):
    """Count visual scene changes (slide flips, screen-share switches, camera cuts)."""
    out = _run([FFMPEG, "-hide_banner", "-nostats", "-i", path, "-an",
                "-vf", f"fps=2,scale=320:-2,select='gt(scene,{threshold})',showinfo",
                "-f", "null", "-"])
    changes = len(re.findall(r"pts_time:", out.stderr))
    mins = duration / 60 if duration else 0
    return {
        "screen_changes": changes,
        "screen_changes_per_min": round(changes / mins, 2) if mins else 0.0,
    }


def extract_all(path):
    meta = probe(path)
    d = meta["duration_sec"]
    sig = {**meta}
    if meta["has_audio"]:
        sig.update(silence_stats(path, d))
        sig.update(loudness(path))
    if meta["has_video"]:
        sig.update(screen_activity(path, d))
    sig["flags"] = flags(sig)
    return sig


def flags(s):
    """Human-readable warnings derived from the raw numbers."""
    f = []
    if not s.get("has_audio"):
        f.append("No audio track — teaching quality can only be judged from the screen.")
    if s.get("silence_ratio", 0) > 0.35:
        f.append(f"{int(s['silence_ratio'] * 100)}% of the recording is silent — "
                 "possible dead air, disengagement or connection problems.")
    if s.get("long_silences_over_15s", 0) >= 3:
        f.append(f"{s['long_silences_over_15s']} silences longer than 15s "
                 f"(longest {s.get('longest_silence_sec')}s at {s.get('longest_silence_at')}).")
    mv = s.get("mean_volume_db")
    if mv is not None and mv < -40:
        f.append(f"Very low average volume ({mv} dB) — weak or distant microphone.")
    if s.get("max_volume_db") is not None and s["max_volume_db"] >= -0.1:
        f.append("Audio peaks hit 0 dB — likely clipping/distortion at times.")
    if s.get("has_video") and s.get("screen_changes_per_min", 1) < 0.1 and s.get("duration_sec", 0) > 300:
        f.append("Screen is almost static for the whole class — little visual material used.")
    if s.get("duration_sec", 0) and s["duration_sec"] < 600:
        f.append("Recording is under 10 minutes — assessment is based on a short clip.")
    return f


def compress_for_upload(src, dst):
    """Shrink video for fast upload: 360p, 1 fps (the model samples ~1 fps anyway),
    mono 16 kHz speech audio. A 60-min class goes from ~1 GB to ~40-80 MB."""
    cmd = [FFMPEG, "-y", "-hide_banner", "-loglevel", "error", "-i", src,
           "-vf", "scale=-2:360,fps=1", "-c:v", "libx264", "-preset", "veryfast",
           "-crf", "32", "-ac", "1", "-ar", "16000", "-c:a", "aac", "-b:a", "48k",
           "-movflags", "+faststart", dst]
    r = _run(cmd, timeout=3600)
    if r.returncode != 0:
        raise RuntimeError(f"ffmpeg compression failed: {r.stderr[-500:]}")
    return dst


def _ts(sec):
    sec = int(sec)
    return f"{sec // 60:02d}:{sec % 60:02d}" if sec < 3600 else \
        f"{sec // 3600}:{(sec % 3600) // 60:02d}:{sec % 60:02d}"
