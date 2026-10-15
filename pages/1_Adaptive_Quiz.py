"""
StudyBuddy Adaptive — quiz page.

Pipeline: upload/paste notes -> concepts/passages -> grounded questions
with a visible source citation -> quiz ordered by round_robin_selector
(the baseline that won the stage 3 simulation, see docs/FINDINGS.md) ->
per-concept estimated-mastery chart -> concepts to review.

Two question sources:
  - No OPENAI_API_KEY: demo mode, bundled fixture document + questions.
  - OPENAI_API_KEY present and notes supplied: the real LLM path
    (src.quiz_generator.generate_quiz), with every generated question
    run through the grounding verifier before it reaches the quiz. This
    path is NOT exercised against the real API by this project's
    automated tests (see docs/FINDINGS.md's manual test checklist) — if
    generation fails or returns malformed output, this page shows an
    error and stops; it never silently falls back to template questions.

All logic lives in adaptive_quiz/logic.py (Streamlit-free, unit-tested);
this file only renders. Does not modify or import from app.py / src/ —
app.py's own behavior is untouched (the LLM path reuses
src.quiz_generator.generate_quiz, but src/ itself is not edited).
"""
import pandas as pd
import streamlit as st
from dotenv import load_dotenv

from adaptive_quiz.logic import (
    AVAILABLE_POLICIES,
    DEFAULT_POLICY,
    build_llm_grounded_quiz,
    build_quiz,
    grade_and_update_mastery,
    is_demo_mode,
    ordered_concept_ids,
)
from engine.concepts import split_passages

load_dotenv()

st.set_page_config(page_title="StudyBuddy Adaptive", page_icon="🧠", layout="centered")

st.title("StudyBuddy Adaptive")
st.caption(
    "Concepts → grounded questions → a quiz ordered by the selection policy that "
    "actually won the simulation (see docs/FINDINGS.md) → estimated mastery."
)

for key, default in [
    ("aq_quiz", None),
    ("aq_mastery", {}),
    ("aq_review", None),
    ("aq_error", None),
    ("aq_summary", None),
]:
    if key not in st.session_state:
        st.session_state[key] = default


def _reset():
    st.session_state.aq_quiz = None
    st.session_state.aq_mastery = {}
    st.session_state.aq_review = None
    st.session_state.aq_error = None
    st.session_state.aq_summary = None


demo_active = is_demo_mode()
if demo_active:
    st.info("**Demo mode: template questions** — no `OPENAI_API_KEY` found, so this page is "
            "running on a bundled sample document and pre-written questions. No key, no API cost.",
            icon="🧪")
else:
    st.info("**Questions from the LLM, checked against your notes** — generated with the real "
            "`generate_quiz()`, then every question is run through the grounding verifier before "
            "it reaches the quiz below.", icon="🤖")

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
        st.session_state.aq_policy = policy

        if demo_active:
            result = build_quiz(None, demo_mode=True)
            st.session_state.aq_quiz = result
            st.session_state.aq_summary = (
                f"{len(result.kept_questions) + len(result.dropped_questions)} generated · "
                f"{len(result.kept_questions)} kept · {len(result.dropped_questions)} dropped"
            )
        else:
            passages = split_passages(pasted)
            llm_result = build_llm_grounded_quiz(pasted, passages)
            if not llm_result.ok:
                st.session_state.aq_error = llm_result.error
            else:
                st.session_state.aq_quiz = llm_result
                st.session_state.aq_summary = (
                    f"{llm_result.generated_count} generated · "
                    f"{len(llm_result.kept_questions)} kept · "
                    f"{len(llm_result.dropped_questions)} dropped"
                )

if st.session_state.aq_error:
    st.error(f"Couldn't build the quiz: {st.session_state.aq_error}")

quiz = st.session_state.aq_quiz
if quiz:
    if st.session_state.aq_summary:
        st.caption(st.session_state.aq_summary)

    if quiz.dropped_questions:
        with st.expander(f"Dropped questions ({len(quiz.dropped_questions)}) — failed grounding check"):
            for question, reason in quiz.dropped_questions:
                st.markdown(f"- **{question.question}**")
                st.caption(f"Assigned passage: {question.citation or '(none found)'}")
                st.caption(f"Reason: {reason}")

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
