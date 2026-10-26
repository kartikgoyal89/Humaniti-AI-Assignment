"""Turn rubric scores into a final label.

Final label = weighted rubric score mapped through thresholds (calibrated on the
sample set if calibration.json exists). The model's own holistic label is kept as
a cross-check: if the two disagree by more than one level we report it and lower
confidence instead of silently picking one.
"""
import json
import os

from .rubric import DEFAULT_THRESHOLDS, DIMENSIONS, LABELS

CALIBRATION_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "calibration.json")


def load_calibration():
    if os.path.exists(CALIBRATION_PATH):
        with open(CALIBRATION_PATH) as f:
            return json.load(f)
    return None


def weighted_score(assessment):
    dims = assessment["dimensions"]
    total = sum(DIMENSIONS[k]["weight"] * dims[k]["score"] for k in DIMENSIONS)
    return round(total / sum(d["weight"] for d in DIMENSIONS.values()), 2)


def label_for(score, thresholds):
    if score >= thresholds["Excellent"]:
        return "Excellent"
    if score >= thresholds["Good"]:
        return "Good"
    if score >= thresholds["Average"]:
        return "Average"
    return "Poor"


def finalize(assessment, signals, calibration=None):
    thresholds = (calibration or {}).get("thresholds", DEFAULT_THRESHOLDS)
    score = weighted_score(assessment)
    rubric_label = label_for(score, thresholds)
    model_label = assessment.get("holistic_label", rubric_label)
    gap = abs(LABELS.index(rubric_label) - LABELS.index(model_label))

    confidence = assessment.get("confidence", "medium")
    notes = []
    if gap == 1:
        notes.append(f"Rubric score points to {rubric_label}; overall impression was "
                     f"{model_label}. Borderline between the two.")
    elif gap >= 2:
        notes.append(f"Rubric score ({rubric_label}) and overall impression ({model_label}) "
                     "disagree strongly — treat this result with caution.")
        confidence = "low"

    return {
        "label": rubric_label,
        "score": score,
        "thresholds": thresholds,
        "model_holistic_label": model_label,
        "confidence": confidence,
        "notes": notes,
        "signals": signals,
        "assessment": assessment,
        "calibrated": bool(calibration),
    }
