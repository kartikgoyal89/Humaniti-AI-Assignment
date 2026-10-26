"""Calibrate the scorer on the labelled sample recordings.

Usage:
    python calibrate.py <folder_with_samples> [labels.csv]

Labels come from labels.csv (columns: filename,label) or, if absent, from the
file/sub-folder name containing Poor/Average/Good/Excellent.

Writes calibration.json with:
  - thresholds: midpoints between the mean rubric scores of adjacent labels
  - label_profiles: average dimension scores / interaction metrics / signals per
    label (numbers only — no transcripts or names, so it's safe to commit)
Also prints per-file results so you can see where the system agrees with the labels.
"""
import csv
import json
import os
import sys
from statistics import mean

from core.pipeline import run
from core.rubric import DEFAULT_THRESHOLDS, DIMENSIONS, LABELS
from core.scoring import CALIBRATION_PATH, label_for

VIDEO_EXT = (".mp4", ".mov", ".mkv", ".webm", ".avi", ".m4a", ".mp3", ".wav")


def find_samples(folder, labels_csv=None):
    explicit = {}
    if labels_csv:
        with open(labels_csv) as f:
            for row in csv.DictReader(f):
                explicit[row["filename"].strip()] = row["label"].strip().title()
    out = []
    for root, _, files in os.walk(folder):
        for fn in files:
            if not fn.lower().endswith(VIDEO_EXT):
                continue
            path = os.path.join(root, fn)
            label = explicit.get(fn) or next(
                (l for l in LABELS if l.lower() in path.lower()), None)
            if label:
                out.append((path, label))
            else:
                print(f"skip (no label): {path}")
    return out


def main():
    folder = sys.argv[1]
    labels_csv = sys.argv[2] if len(sys.argv) > 2 else None
    api_key = os.environ["GEMINI_API_KEY"]
    rows = []
    for path, label in find_samples(folder, labels_csv):
        print(f"\n→ {os.path.basename(path)} [{label}]")
        r = run(path, api_key, on_status=lambda m: print("   ", m))
        a = r["assessment"]
        rows.append({
            "file": os.path.basename(path), "true": label, "score": r["score"],
            "model_label": r["model_holistic_label"],
            "dims": {k: a["dimensions"][k]["score"] for k in DIMENSIONS},
            "metrics": a["interaction_metrics"],
            "signals": {k: v for k, v in r["signals"].items()
                        if isinstance(v, (int, float)) and not isinstance(v, bool)},
        })
        print(f"    score={r['score']}  model_label={r['model_holistic_label']}")

    by_label = {l: [x for x in rows if x["true"] == l] for l in LABELS}
    means = {l: mean(x["score"] for x in xs) for l, xs in by_label.items() if xs}

    thresholds = dict(DEFAULT_THRESHOLDS)
    for lo, hi in zip(LABELS, LABELS[1:]):
        if lo in means and hi in means and means[hi] > means[lo]:
            thresholds[hi] = round((means[lo] + means[hi]) / 2, 2)

    def avg(xs, key):
        keys = xs[0][key].keys()
        return {k: round(mean(x[key][k] for x in xs), 2) for k in keys}

    profiles = {l: {"n": len(xs), "mean_rubric_score": round(means[l], 2),
                    "dimension_scores": avg(xs, "dims"),
                    "interaction_metrics": avg(xs, "metrics"),
                    "signals": avg(xs, "signals")}
                for l, xs in by_label.items() if xs}

    with open(CALIBRATION_PATH, "w") as f:
        json.dump({"thresholds": thresholds, "label_profiles": profiles}, f, indent=2)

    print("\n=== Results on sample set ===")
    hit_rubric = hit_model = 0
    for x in rows:
        pred = label_for(x["score"], thresholds)
        hit_rubric += pred == x["true"]
        hit_model += x["model_label"] == x["true"]
        print(f"{x['file'][:40]:40s} true={x['true']:9s} rubric={pred:9s} "
              f"model={x['model_label']:9s} score={x['score']}")
    n = len(rows) or 1
    print(f"\nRubric+thresholds accuracy: {hit_rubric}/{len(rows)} ({hit_rubric / n:.0%})")
    print(f"Model holistic accuracy:    {hit_model}/{len(rows)} ({hit_model / n:.0%})")
    print("(Thresholds were fit on these same files — treat as an optimistic estimate.)")
    print(f"\nSaved {CALIBRATION_PATH}: thresholds={thresholds}")


if __name__ == "__main__":
    main()
