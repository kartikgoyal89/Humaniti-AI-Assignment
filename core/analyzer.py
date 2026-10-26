"""Multimodal assessment with Gemini: the model watches AND listens to the class.

Flow: upload compressed video -> wait until processed -> ask for a structured,
evidence-backed rubric assessment (JSON schema enforced) -> delete the upload.
"""
import json
import os
import time

from google import genai
from google.genai import types

from .rubric import DIMENSIONS, LABELS

DEFAULT_MODEL = os.getenv("GEMINI_MODEL", "gemini-3.8-flash")

# ---------- structured output schema ----------
_evidence = {
    "type": "object",
    "properties": {
        "timestamp": {"type": "string", "description": "mm:ss in the recording"},
        "observation": {"type": "string"},
    },
    "required": ["timestamp", "observation"],
}

_dimension = {
    "type": "object",
    "properties": {
        "score": {"type": "integer", "minimum": 1, "maximum": 4},
        "justification": {"type": "string"},
        "evidence": {"type": "array", "items": _evidence},
    },
    "required": ["score", "justification", "evidence"],
}

SCHEMA = {
    "type": "object",
    "properties": {
        "class_summary": {"type": "string",
                          "description": "Subject, topic, age group, number of students, format."},
        "dimensions": {
            "type": "object",
            "properties": {k: _dimension for k in DIMENSIONS},
            "required": list(DIMENSIONS),
        },
        "interaction_metrics": {
            "type": "object",
            "properties": {
                "teacher_talk_pct": {"type": "integer"},
                "student_talk_pct": {"type": "integer"},
                "questions_asked_by_teacher": {"type": "integer"},
                "open_ended_questions": {"type": "integer"},
                "student_responses": {"type": "integer"},
                "students_who_spoke": {"type": "integer"},
                "praise_or_encouragement_instances": {"type": "integer"},
                "technical_issue_moments": {"type": "integer"},
            },
            "required": ["teacher_talk_pct", "student_talk_pct", "questions_asked_by_teacher",
                         "open_ended_questions", "student_responses", "students_who_spoke",
                         "praise_or_encouragement_instances", "technical_issue_moments"],
        },
        "key_moments": {"type": "array", "items": {
            "type": "object",
            "properties": {
                "timestamp": {"type": "string"},
                "type": {"type": "string", "enum": ["strength", "weakness"]},
                "description": {"type": "string"},
            },
            "required": ["timestamp", "type", "description"]}},
        "strengths": {"type": "array", "items": {"type": "string"}},
        "improvements": {"type": "array", "items": {"type": "string"}},
        "misleading_signals_considered": {"type": "string",
            "description": "Signals that could mislead a naive judge and how you treated them."},
        "holistic_label": {"type": "string", "enum": LABELS},
        "confidence": {"type": "string", "enum": ["low", "medium", "high"]},
    },
    "required": ["class_summary", "dimensions", "interaction_metrics", "key_moments",
                 "strengths", "improvements", "misleading_signals_considered",
                 "holistic_label", "confidence"],
}


def build_prompt(signals, calibration=None):
    rubric = "\n".join(
        f"- {k} ({v['name']}, weight {int(v['weight'] * 100)}%): {v['looks_for']}"
        for k, v in DIMENSIONS.items())

    sig_lines = {k: v for k, v in signals.items() if k != "flags"}
    calib = ""
    if calibration and calibration.get("label_profiles"):
        calib = ("\n## Reference profiles from labelled 8x8 classes\n"
                 "Use these to calibrate your scale to this company's standards:\n"
                 + json.dumps(calibration["label_profiles"], indent=1) + "\n")

    return f"""You are an experienced online-teaching observer for 8x8, a company that runs
live online classes for children. Watch AND listen to the full recording and assess its
teaching quality.

## Rubric (score each 1-4: 1=poor, 2=average, 3=good, 4=excellent)
{rubric}

## Objective measurements already extracted from this file (ffmpeg)
{json.dumps(sig_lines, indent=1)}
Interpret these in context: silence can be dead air OR students working on a task;
few screen changes can mean a static slide OR a well-used whiteboard. Verify with what
you actually see and hear.
{calib}
## Rules
1. Every justification and evidence item must be SPECIFIC to this recording: cite mm:ss
   timestamps, paraphrase what was said, describe what was on screen. Never write generic
   statements like "the teacher was engaging" without the concrete moment that shows it.
2. Give 2-4 evidence items per dimension, spread across the beginning, middle and end.
3. Judge the class, not the production: a teacher with a cheap webcam who gets every child
   talking beats a polished monologue. Don't reward a confident voice or pretty slides on
   their own; don't penalise an accent.
4. Estimate teacher vs student talk time by listening for different voices.
5. Privacy: children may be identifiable. NEVER write a child's name — refer to them as
   "Student A", "Student B", etc. Do not describe children's appearance.
6. Improvements must be actionable coaching advice tied to moments you observed.
7. If the recording is cut off, mostly silent, or not a class, say so and lower confidence.
"""


class Analyzer:
    def __init__(self, api_key, model=None):
        self.client = genai.Client(api_key=api_key)
        self.model = model or DEFAULT_MODEL

    def upload(self, path, on_status=None):
        f = self.client.files.upload(file=path)
        waited = 0
        while f.state and f.state.name == "PROCESSING":
            if on_status:
                on_status(f"Model is processing the video… {waited}s")
            time.sleep(5)
            waited += 5
            f = self.client.files.get(name=f.name)
        if f.state and f.state.name == "FAILED":
            raise RuntimeError("Gemini could not process this video file.")
        return f

    def assess(self, path, signals, calibration=None, on_status=None):
        uploaded = self.upload(path, on_status)
        try:
            if on_status:
                on_status("Watching and listening to the class…")
            resp = self.client.models.generate_content(
                model=self.model,
                contents=[uploaded, build_prompt(signals, calibration)],
                config=types.GenerateContentConfig(
                    response_mime_type="application/json",
                    response_schema=SCHEMA,
                    temperature=0.2,
                    media_resolution=types.MediaResolution.MEDIA_RESOLUTION_LOW,
                ),
            )
            return json.loads(resp.text)
        finally:
            # Confidentiality: don't leave recordings sitting on the provider side.
            try:
                self.client.files.delete(name=uploaded.name)
            except Exception:
                pass
