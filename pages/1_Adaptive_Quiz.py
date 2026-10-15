"""
Adaptive Quiz.

Pipeline: notes -> grounded questions with a visible source citation ->
quiz ordered by round_robin_selector (the baseline that won the stage 3
simulation, see docs/FINDINGS.md) -> per-concept estimated-mastery chart.

Two question sources, chosen automatically:
  - No OPENAI_API_KEY: demo path, a bundled fixture document + questions.
  - OPENAI_API_KEY present and notes supplied: the real LLM path
    (src.quiz_generator.generate_quiz), with every generated question
    run through the grounding verifier before it reaches the quiz. Not
    exercised against the real API by automated tests — see
    docs/FINDINGS.md's manual test checklist.

All logic lives in adaptive_quiz/logic.py (Streamlit-free, unit-tested);
this file only renders. Does not modify app.py or src/.

Design: this page intentionally avoids marketing copy, emoji, and nested
bordered cards — plain labels, one accent color, thin dividers. Scope is
this page only; app.py's own styling is untouched.
"""
import pandas as pd
import streamlit as st
from dotenv import load_dotenv

from adaptive_quiz.logic import (
    AVAILABLE_POLICIES,
    DEFAULT_POLICY,
    build_evidence,
    build_llm_grounded_quiz,
    build_quiz,
    grade_and_update_mastery,
    is_demo_mode,
    ordered_concept_ids,
    plain_language_reason,
    render_notes_html,
)
from engine.concepts import split_passages

load_dotenv()

st.set_page_config(page_title="Adaptive Quiz", layout="wide")

st.markdown(
    """
    <style>
    :root {
        --aq-accent: #3b6e8f;
        --aq-highlight-bg: rgba(59, 110, 143, 0.16);
        --aq-highlight-border: rgba(59, 110, 143, 0.55);
    }
    @media (prefers-color-scheme: dark) {
        :root {
            --aq-highlight-bg: rgba(130, 190, 225, 0.22);
            --aq-highlight-border: rgba(130, 190, 225, 0.6);
        }
    }
    .aq-notes {
        white-space: pre-wrap;
        line-height: 1.65;
        font-size: 0.95rem;
    }
    .aq-highlight {
        background: var(--aq-highlight-bg);
        border-bottom: 2px solid var(--aq-highlight-border);
        border-radius: 2px;
        padding: 0 1px;
    }
    .aq-status {
        color: var(--aq-accent);
        font-size: 0.85rem;
    }
    </style>
    """,
    unsafe_allow_html=True,
)

st.title("Adaptive Quiz")
st.write("Paste notes, answer questions grounded in them, and see which sentence supports each one.")

for key, default in [
    ("aq_quiz", None),
    ("aq_notes_text", ""),
    ("aq_mastery", {}),
    ("aq_review", None),
    ("aq_error", None),
    ("aq_summary", None),
    ("aq_current_question", None),
]:
    if key not in st.session_state:
        st.session_state[key] = default


def _reset():
    st.session_state.aq_quiz = None
    st.session_state.aq_notes_text = ""
    st.session_state.aq_mastery = {}
    st.session_state.aq_review = None
    st.session_state.aq_error = None
    st.session_state.aq_summary = None
    st.session_state.aq_current_question = None


demo_active = is_demo_mode()
mode_text = (
    "Mode: demo — template questions, no key required."
    if demo_active
    else "Mode: LLM — questions generated with your key, checked against your notes."
)
st.markdown(f'<div class="aq-status">{mode_text}</div>', unsafe_allow_html=True)

st.divider()

st.subheader("Notes")
pasted = st.text_area(
    "Paste notes",
    height=160,
    disabled=demo_active,
    label_visibility="collapsed",
    placeholder="Demo mode is active — using the bundled sample document instead."
    if demo_active
    else "Paste lecture notes or a textbook excerpt...",
)
policy = st.selectbox(
    "Question order",
    AVAILABLE_POLICIES,
    index=AVAILABLE_POLICIES.index(DEFAULT_POLICY),
    help="round_robin is the default — the baseline that won the stage 3 simulation.",
)
build_disabled = not demo_active and not pasted.strip()
if st.button("Build quiz", type="primary", disabled=build_disabled):
    _reset()
    st.session_state.aq_policy = policy

    if demo_active:
        result = build_quiz(None, demo_mode=True)
        st.session_state.aq_quiz = result
        st.session_state.aq_notes_text = result.document_text
        n_generated = len(result.kept_questions) + len(result.dropped_questions)
        st.session_state.aq_summary = (n_generated, len(result.kept_questions), len(result.dropped_questions))
    else:
        passages = split_passages(pasted)
        llm_result = build_llm_grounded_quiz(pasted, passages)
        if not llm_result.ok:
            st.session_state.aq_error = llm_result.error
        else:
            st.session_state.aq_quiz = llm_result
            st.session_state.aq_notes_text = pasted
            st.session_state.aq_summary = (
                llm_result.generated_count,
                len(llm_result.kept_questions),
                len(llm_result.dropped_questions),
            )

if st.session_state.aq_error:
    st.error(f"Couldn't build the quiz: {st.session_state.aq_error}")

quiz = st.session_state.aq_quiz
if quiz:
    st.divider()
    n_generated, n_kept, n_rejected = st.session_state.aq_summary
    st.markdown(f"Generated `{n_generated}` · Kept `{n_kept}` · Rejected `{n_rejected}`")

    if not quiz.kept_questions:
        st.write("No questions passed the grounding check — nothing to quiz on.")
    else:
        ordered_ids = ordered_concept_ids(quiz.kept_questions, policy=st.session_state.aq_policy)
        questions_by_id = {q.id: q for q in quiz.kept_questions}
        evidence = build_evidence(st.session_state.aq_notes_text, quiz.kept_questions)

        if st.session_state.aq_current_question not in ordered_ids:
            st.session_state.aq_current_question = ordered_ids[0]

        st.divider()
        col_questions, col_notes = st.columns([1, 1])

        with col_questions:
            st.subheader("Questions")
            st.caption(f"Order: `{st.session_state.aq_policy}`")
            current = st.radio(
                "Preview evidence for",
                options=ordered_ids,
                format_func=lambda cid: f"{ordered_ids.index(cid) + 1}. {questions_by_id[cid].question}",
                key="aq_current_question",
                label_visibility="collapsed",
            )

            with st.form("aq_quiz_form"):
                answers = {}
                for position, concept_id in enumerate(ordered_ids, start=1):
                    question = questions_by_id[concept_id]
                    st.markdown(f"`{position}.` {question.question}")
                    answers[concept_id] = st.text_input(
                        "Your answer", key=f"aq_ans_{concept_id}", label_visibility="collapsed"
                    )
                submitted = st.form_submit_button("Submit answers", type="primary")

            if submitted:
                mastery, review, correctness = grade_and_update_mastery(
                    quiz.kept_questions, answers, st.session_state.aq_mastery
                )
                st.session_state.aq_mastery = mastery
                st.session_state.aq_review = review
                st.session_state.aq_correctness = correctness

        with col_notes:
            st.subheader("Notes")
            current_evidence = evidence.get(current)
            span = current_evidence.span if current_evidence else None
            st.markdown(render_notes_html(st.session_state.aq_notes_text, span), unsafe_allow_html=True)

        if st.session_state.get("aq_correctness"):
            st.divider()
            st.subheader("Results")
            for concept_id in ordered_ids:
                question = questions_by_id[concept_id]
                correct = st.session_state.aq_correctness.get(concept_id, False)
                st.markdown(f"`{'correct' if correct else 'incorrect'}` — {question.question}")
                st.write(f"Correct answer: {question.answer}")
                sentence = evidence[concept_id].sentence
                st.write(f'Supporting sentence: "{sentence}"' if sentence else "Supporting sentence: not found in your notes")
                st.divider()

    if quiz.dropped_questions:
        st.subheader("Rejected: not supported by your notes")
        st.caption(
            "This check is word-overlap based and can reject valid questions — "
            "read the reason below before assuming the question was wrong."
        )
        for question, reason in quiz.dropped_questions:
            st.markdown(f"**{question.question}**")
            st.write(f"Assigned passage: {question.citation or '(none found)'}")
            st.write(plain_language_reason(reason))
            st.divider()

if st.session_state.aq_mastery:
    st.subheader("Estimated mastery")
    st.caption("Estimated; not validated on real learners.")
    chart_df = pd.DataFrame(
        {"concept": list(st.session_state.aq_mastery.keys()), "mastery": list(st.session_state.aq_mastery.values())}
    ).set_index("concept")
    st.bar_chart(chart_df)

    if st.session_state.aq_review:
        st.write("Concepts to review:")
        for concept_id in st.session_state.aq_review:
            st.markdown(f"- `{concept_id}`")
