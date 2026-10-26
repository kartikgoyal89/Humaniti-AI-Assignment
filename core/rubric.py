"""Rubric definition: the dimensions we score and how they roll up into a label.

Scores are 1-4 per dimension (1 = poor, 4 = excellent). Weights reflect what
matters most in a live online class for children: whether the kids are actually
engaged and interacting, not just whether the teacher talks well.
"""

DIMENSIONS = {
    "student_engagement": {
        "name": "Student engagement & participation",
        "weight": 0.20,
        "looks_for": "How often and how willingly students speak, answer, ask, react; "
                     "signs of attention vs. distraction, silence or drop-off.",
    },
    "interaction_questioning": {
        "name": "Interaction & questioning",
        "weight": 0.15,
        "looks_for": "Open vs. closed questions, wait time, calling on students by turn, "
                     "two-way dialogue rather than lecture.",
    },
    "clarity_of_explanation": {
        "name": "Clarity of explanation",
        "weight": 0.15,
        "looks_for": "Age-appropriate language, examples, step-by-step build-up, accuracy, "
                     "correcting misconceptions.",
    },
    "structure_pacing": {
        "name": "Lesson structure & pacing",
        "weight": 0.10,
        "looks_for": "Clear opening/goal, logical flow, recap/closure, time not wasted, "
                     "not rushed or dragging.",
    },
    "teacher_energy_warmth": {
        "name": "Teacher energy, tone & warmth",
        "weight": 0.10,
        "looks_for": "Vocal variety, enthusiasm, encouragement, patience, rapport with kids.",
    },
    "visuals_activities": {
        "name": "Use of screen, visuals & activities",
        "weight": 0.10,
        "looks_for": "Slides/whiteboard/screen-share actually used, interactive tasks, "
                     "games, practice problems; screen relevant to what is being said.",
    },
    "checking_understanding_feedback": {
        "name": "Checking understanding & feedback",
        "weight": 0.10,
        "looks_for": "Teacher verifies learning (asks students to explain/solve), gives "
                     "specific praise and corrective feedback.",
    },
    "management_technical": {
        "name": "Class management & technical quality",
        "weight": 0.10,
        "looks_for": "Starts on time, handles disruptions, audio/video clarity, mic issues, "
                     "lag, dead air caused by tech problems.",
    },
}

LABELS = ["Poor", "Average", "Good", "Excellent"]

# Default thresholds on the 1-4 weighted score. calibrate.py can overwrite these
# using the labelled sample recordings (saved to calibration.json).
DEFAULT_THRESHOLDS = {"Average": 1.9, "Good": 2.6, "Excellent": 3.3}
