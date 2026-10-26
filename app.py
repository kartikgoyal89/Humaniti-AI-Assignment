import json
import os
import tempfile

import streamlit as st

from core.pipeline import download, run
from core.rubric import DIMENSIONS

st.set_page_config(page_title="Class Quality AI", page_icon="🎓", layout="wide")


def secret(name, default=None):
    try:
        return st.secrets.get(name, os.getenv(name, default))
    except Exception:
        return os.getenv(name, default)


# ---------- access gate (recordings are confidential) ----------
APP_PASSWORD = secret("APP_PASSWORD")
if APP_PASSWORD and not st.session_state.get("authed"):
    st.title("🎓 Class Quality AI")
    pw = st.text_input("Access code", type="password")
    if pw:
        if pw == APP_PASSWORD:
            st.session_state.authed = True
            st.rerun()
        else:
            st.error("Wrong access code.")
    st.stop()

API_KEY = secret("GEMINI_API_KEY")
MODEL = secret("GEMINI_MODEL")

st.title("🎓 Class Quality AI")
st.caption("Upload an online class recording. The model watches the screen and listens to the "
           "audio, scores it on an 8-part teaching rubric with timestamped evidence, and "
           "classifies it as Poor, Average, Good or Excellent.")

if not API_KEY:
    st.error("GEMINI_API_KEY is not configured. Add it to .streamlit/secrets.toml or the environment.")
    st.stop()

tab_up, tab_link = st.tabs(["📁 Upload file", "🔗 Paste link"])
with tab_up:
    up = st.file_uploader("Class recording", type=["mp4", "mov", "mkv", "webm", "avi", "m4a", "mp3", "wav"])
with tab_link:
    link = st.text_input("Google Drive share link or direct video URL",
                         help="Use this for long recordings — it streams to disk instead of memory.")

go = st.button("Assess class", type="primary", disabled=not (up or link))

if go:
    status = st.status("Starting…", expanded=True)
    try:
        with tempfile.TemporaryDirectory() as tmp:
            if up:
                path = os.path.join(tmp, up.name)
                with open(path, "wb") as f:
                    f.write(up.getbuffer())
            else:
                status.update(label="Downloading recording…")
                path = download(link.strip(), tmp)
            result = run(path, API_KEY, MODEL, on_status=lambda m: status.update(label=m))
        status.update(label="Done", state="complete", expanded=False)
        st.session_state.result = result
    except Exception as e:
        status.update(label="Failed", state="error")
        st.error(f"Could not assess this recording: {e}")

r = st.session_state.get("result")
if r:
    a = r["assessment"]
    colors = {"Poor": "#c0392b", "Average": "#d68910", "Good": "#2e86c1", "Excellent": "#1e8449"}

    c1, c2, c3 = st.columns([1.3, 1, 1])
    with c1:
        st.markdown(
            f"<div style='padding:18px;border-radius:12px;background:{colors[r['label']]};color:white'>"
            f"<div style='font-size:14px;opacity:.85'>Overall quality</div>"
            f"<div style='font-size:40px;font-weight:700'>{r['label']}</div>"
            f"<div>Rubric score {r['score']} / 4 · confidence {r['confidence']}</div></div>",
            unsafe_allow_html=True)
    with c2:
        m = a["interaction_metrics"]
        st.metric("Teacher : student talk", f"{m['teacher_talk_pct']}% : {m['student_talk_pct']}%")
        st.metric("Teacher questions (open-ended)", f"{m['questions_asked_by_teacher']} ({m['open_ended_questions']})")
    with c3:
        st.metric("Student responses", m["student_responses"])
        st.metric("Students who spoke", m["students_who_spoke"])

    for n in r["notes"]:
        st.info(n)
    st.write(f"**Class:** {a['class_summary']}")

    st.subheader("Rubric breakdown")
    for k, meta in DIMENSIONS.items():
        d = a["dimensions"][k]
        with st.expander(f"{'●' * d['score']}{'○' * (4 - d['score'])}  {meta['name']} — {d['score']}/4  (weight {int(meta['weight']*100)}%)"):
            st.write(d["justification"])
            for ev in d["evidence"]:
                st.markdown(f"- `{ev['timestamp']}` {ev['observation']}")

    s1, s2 = st.columns(2)
    with s1:
        st.subheader("✅ Strengths")
        for s in a["strengths"]:
            st.markdown(f"- {s}")
    with s2:
        st.subheader("🛠 What to improve")
        for s in a["improvements"]:
            st.markdown(f"- {s}")

    st.subheader("Key moments")
    for km in sorted(a["key_moments"], key=lambda x: x["timestamp"]):
        icon = "🟢" if km["type"] == "strength" else "🔴"
        st.markdown(f"{icon} `{km['timestamp']}` {km['description']}")

    with st.expander("Measured audio/screen signals"):
        sig = r["signals"]
        for fl in sig.get("flags", []):
            st.warning(fl)
        st.json({k: v for k, v in sig.items() if k != "flags"})
        st.caption(f"How signals were weighed: {a['misleading_signals_considered']}")

    st.caption(f"Model's holistic label: {r['model_holistic_label']} · "
               f"{'Thresholds calibrated on sample classes' if r['calibrated'] else 'Default thresholds'}: {r['thresholds']}")
    st.download_button("Download full report (JSON)", json.dumps(r, indent=2),
                       file_name="class_assessment.json", mime="application/json")
