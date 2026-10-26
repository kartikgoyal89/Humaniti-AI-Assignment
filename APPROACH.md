# Approach (≤300 words)

**Idea.** Class quality isn't only what the teacher says. It also shows in who is talking, how the class sounds and what's on screen. So the system combines two kinds of evidence:

1. **Objective signals (ffmpeg):** silence ratio and long dead-air stretches, loudness and clipping, and the rate of screen changes. These are cheap, reproducible, and catch tech problems and static, lecture-only screens.
2. **Multimodal judgement (Gemini):** the model watches and listens to the whole recording in one pass and scores an 8-part teaching rubric (engagement, questioning, clarity, pacing, warmth, visuals, checking understanding, management). JSON-schema output forces 2–4 **timestamped** observations per dimension plus interaction counts (teacher/student talk %, questions, student responses). That makes the explanation specific rather than generic.

**Classification.** The label comes from a weighted rubric score passed through thresholds that are **fitted on the labelled sample recordings** (`calibrate.py`). The model's own holistic label is a cross-check. If the two disagree by two levels, confidence is downgraded instead of hidden. Per-label profiles from the samples go into the prompt so the scale matches 8x8's standards.

**Misleading signals handled explicitly.** Silence can mean dead air or kids working on a task. Polished slides and a confident voice don't equal learning. The prompt makes the model interpret the measurements in context and say how it weighed them.

**What worked / failed:** *[fill in after running calibrate.py: accuracy on the samples, where it confused adjacent levels]*

**Limitations.**
- With very few samples the thresholds can overfit, and accuracy on the samples is optimistic.
- Talk-time and question counts are model estimates, not true speaker diarisation.
- Adjacent levels (Good vs Excellent) are the hardest to separate.
- Results vary slightly run to run (temperature 0.2).
- Long recordings depend on upload size and host memory limits; the link input mitigates this.
- Processing relies on a third-party API, so the organiser must permit it, with a paid-tier key and uploads deleted after each run.
