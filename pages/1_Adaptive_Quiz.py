"""
StudyBuddy Adaptive — quiz page.

Pipeline: upload/paste notes -> concepts -> grounded questions with a
visible source citation -> quiz ordered by round_robin_selector (the
baseline that won the stage 3 simulation, see docs/FINDINGS.md) ->
per-concept estimated-mastery chart -> concepts to review.

All logic lives in adaptive_quiz/logic.py (Streamlit-free, unit-tested);
this file only renders. Does not modify or import from app.py / src/ —
app.py's own behavior is untouched.
"""
import pandas as pd
import streamlit as st
from dotenv import load_dotenv

from adaptive_quiz.logic import (
    AVAILABLE_POLICIES,
    DEFAULT_POLICY,
    build_quiz,
    grade_and_update_mastery,
    is_demo_mode,
    ordered_concept_ids,
)

load_dotenv()

st.set_page_config(page_title="StudyBuddy Adaptive", page_icon="🧠", layout="centered")

st.title("StudyBuddy Adaptive")
st.caption(
    "Concepts → grounded questions → a quiz ordered by the selection policy that "
    "actually won the simulation (see docs/FINDINGS.md) → estimated mastery."
)

if "aq_quiz" not in st.session_state:
    st.session_state.aq_quiz = None
if "aq_mastery" not in st.session_state:
    st.session_state.aq_mastery = {}
if "aq_review" not in st.session_state:
    st.session_state.aq_review = None


def _reset():
    st.session_state.aq_quiz = None
    st.session_state.aq_mastery = {}
    st.session_state.aq_review = None


demo_active = is_demo_mode()
if demo_active:
    st.info(
        "**Demo mode active** — no `OPENAI_API_KEY` found, so this page is running on a "
        "bundled sample document and pre-written questions. No key, no API cost.",
        icon="🧪",
    )

with st.container(border=True):
    st.subheader("Add your material", icon=":material/upload_file:")
    pasted = st.text_area(
        "Paste notes here (ignored in demo mode)",
        height=160,
        disabled=demo_active,
        placeholder="Demo mode is active — using the bundled sample document instead."
        if demo_active
        else "Paste lecture notes or a textbook excerpt...",
    )
    policy = st.selectbox(
        "Question order policy",
        AVAILABLE_POLICIES,
        index=AVAILABLE_POLICIES.index(DEFAULT_POLICY),
        help="round_robin is the default — it's the baseline that won the stage 3 simulation.",
    )
    build_disabled = not demo_active and not pasted.strip()
    if st.button("Build quiz", type="primary", icon=":material/bolt:", disabled=build_disabled):
        _reset()
        st.session_state.aq_quiz = build_quiz(pasted, demo_mode=None)
        st.session_state.aq_policy = policy

quiz = st.session_state.aq_quiz
if quiz:
    if quiz.dropped_questions:
        with st.expander(f"Dropped questions ({len(quiz.dropped_questions)}) — failed grounding check"):
            for question, reason in quiz.dropped_questions:
                st.markdown(f"- **{question.question}** — _{reason}_")

    if not quiz.kept_questions:
        st.warning("No questions passed the grounding check — nothing to quiz on.")
    else:
        ordered_ids = ordered_concept_ids(quiz.kept_questions, policy=st.session_state.aq_policy)
        questions_by_id = {q.id: q for q in quiz.kept_questions}

        with st.container(border=True):
            st.subheader("Quiz", icon=":material/quiz:")
            st.caption(f"Order: {st.session_state.aq_policy}")
            with st.form("aq_quiz_form"):
                answers = {}
                for position, concept_id in enumerate(ordered_ids, start=1):
                    question = questions_by_id[concept_id]
                    st.markdown(f"**{position}. {question.question}**")
                    with st.expander("Source passage"):
                        st.caption(question.citation)
                    answers[concept_id] = st.text_area(
                        "Your answer:", key=f"aq_ans_{concept_id}", label_visibility="collapsed"
                    )
                submitted = st.form_submit_button("Submit answers", type="primary")

            if submitted:
                mastery, review, correctness = grade_and_update_mastery(
                    quiz.kept_questions, answers, st.session_state.aq_mastery
                )
                st.session_state.aq_mastery = mastery
                st.session_state.aq_review = review

if st.session_state.aq_mastery:
    st.divider()
    st.subheader("Estimated mastery", icon=":material/bar_chart:")
    st.caption("Estimated; not validated on real learners.")
    chart_df = pd.DataFrame(
        {"concept": list(st.session_state.aq_mastery.keys()), "mastery": list(st.session_state.aq_mastery.values())}
    ).set_index("concept")
    st.bar_chart(chart_df)

    if st.session_state.aq_review:
        st.markdown("**Concepts to review:**")
        for concept_id in st.session_state.aq_review:
            st.markdown(f"- {concept_id}")
    else:
        st.success("No concepts below the review threshold.")
