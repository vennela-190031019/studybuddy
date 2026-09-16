"""
StudyBuddy — upload lecture notes or a textbook chapter, get a generated
quiz, take it, and get graded with specific feedback.

Run with: streamlit run app.py
"""
import pandas as pd
import streamlit as st
from dotenv import load_dotenv

from src.extract import extract_text_from_pdf, chunk_text
from src.quiz_generator import generate_quiz
from src.grader import grade_answer
from src.schemas import Quiz

load_dotenv()

# Long documents get split into ~6,000-character chunks (see chunk_text).
# We spread the requested questions across up to this many chunks so a
# multi-page upload doesn't just get quizzed on its first section — capped
# to keep generation time/cost bounded for very long documents.
MAX_CHUNKS = 5

st.set_page_config(page_title="StudyBuddy", page_icon="📚", layout="centered")

# ---------------------------------------------------------------- custom styling
# Colors, fonts, and radii live in .streamlit/config.toml. This CSS only
# covers what theme config can't reach: the header treatment, the card
# framing around the bordered containers below (targeted via their `key=`,
# which Streamlit exposes as a `st-key-<key>` class), and a bit of
# button/upload polish.
st.markdown(
    """
    <style>
    @import url('https://fonts.googleapis.com/css2?family=JetBrains+Mono:wght@400;500&display=swap');

    [data-testid="stMainBlockContainer"] {
        max-width: 900px;
        padding-top: 2.5rem;
    }

    /* ---- thin gradient accent line pinned to the top of the viewport ---- */
    .sb-topbar {
        position: fixed;
        top: 0;
        left: 0;
        right: 0;
        height: 3px;
        background: linear-gradient(90deg, #B45309, #D9A441, #8250DF);
        z-index: 999999;
    }

    /* ---- custom header, replacing the default emoji + st.title ---- */
    .sb-header {
        display: flex;
        align-items: center;
        gap: 1rem;
        margin-bottom: 1.5rem;
    }
    .sb-header__logo {
        width: 54px;
        height: 54px;
        flex-shrink: 0;
        border-radius: 14px;
        display: flex;
        align-items: center;
        justify-content: center;
        font-size: 1.6rem;
        background: linear-gradient(135deg, #B45309, #D9A441);
        box-shadow: 0 6px 16px rgba(180, 83, 9, 0.30);
    }
    .sb-header__text h1 {
        margin: 0;
        font-family: 'Lora', serif;
        font-size: 1.85rem;
        line-height: 1.15;
        color: #232A36;
    }
    .sb-header__text p {
        margin: 0.2rem 0 0;
        color: #6B7280;
        font-size: 0.95rem;
    }
    .sb-badge {
        display: inline-flex;
        align-items: center;
        gap: 0.3rem;
        margin-top: 0.5rem;
        padding: 0.15rem 0.6rem;
        border-radius: 999px;
        background: #EFE9FE;
        color: #6B3FD4;
        font-size: 0.78rem;
        font-weight: 600;
    }

    /* ---- monospace "data label" feel for question metadata ---- */
    [class*="st-key-meta-"] p, [class*="st-key-meta-"] span {
        font-family: 'JetBrains Mono', monospace;
        font-size: 0.78rem;
    }

    /* ---- card-like framing for the bordered containers below ---- */
    [class*="st-key-input-card"] > div,
    [class*="st-key-quiz-card"] > div,
    [class*="st-key-results-card"] > div {
        background: #FFFFFF;
        box-shadow: 0 1px 3px rgba(35, 42, 54, 0.07);
    }
    [class*="st-key-qcard-"] > div {
        background: #FFFDF9;
        transition: box-shadow 0.15s ease;
    }
    [class*="st-key-qcard-"] > div:hover {
        box-shadow: 0 4px 14px rgba(35, 42, 54, 0.08);
    }

    /* ---- upload dropzone ---- */
    [data-testid="stFileUploaderDropzone"] {
        border: 2px dashed #DDD0B5 !important;
        border-radius: 12px;
        background: #FBF7EF;
    }

    /* ---- buttons: a little lift instead of the flat default ---- */
    button[kind="primary"], [data-testid^="stBaseButton-primary"] {
        font-weight: 600;
        padding: 0.55rem 1.4rem;
        box-shadow: 0 2px 8px rgba(180, 83, 9, 0.25);
        transition: transform 0.12s ease, box-shadow 0.12s ease;
    }
    button[kind="primary"]:hover, [data-testid^="stBaseButton-primary"]:hover {
        transform: translateY(-1px);
        box-shadow: 0 4px 14px rgba(180, 83, 9, 0.35);
    }

    /* ---- bolder tab labels ---- */
    [data-testid="stTabs"] button[role="tab"] p {
        font-weight: 600;
    }
    </style>

    <div class="sb-topbar"></div>
    <div class="sb-header">
        <div class="sb-header__logo">📚</div>
        <div class="sb-header__text">
            <h1>StudyBuddy</h1>
            <p>Upload your notes, get quizzed, get real feedback.</p>
            <span class="sb-badge">✨ AI-powered</span>
        </div>
    </div>
    """,
    unsafe_allow_html=True,
)

# ---------------------------------------------------------------- session state
if "quiz" not in st.session_state:
    st.session_state.quiz = None
if "results" not in st.session_state:
    st.session_state.results = None


def reset_quiz():
    st.session_state.quiz = None
    st.session_state.results = None


def build_results_report(quiz, results) -> str:
    total = sum(r.score for _, r in results) / len(results)
    lines = ["# StudyBuddy results", "", f"**Overall score:** {total:.0f} / 100", ""]
    for q, r in results:
        lines.append(f"## Q{q.id}. {q.question}")
        lines.append(f"- Topic: {q.topic or 'General'} · Difficulty: {q.difficulty}")
        lines.append(f"- Your answer: {st.session_state.get(f'q_{q.id}', '')}")
        lines.append(f"- Correct answer: {q.correct_answer}")
        lines.append(f"- Score: {r.score}/100 ({'correct' if r.correct else 'incorrect'})")
        lines.append(f"- Feedback: {r.feedback}")
        lines.append("")
    return "\n".join(lines)

# ---------------------------------------------------------------- sidebar
# Only app-level info lives here now — the question-count setting moved
# next to the Generate button, where it's actually used.
with st.sidebar:
    st.subheader("About", icon=":material/info:")
    st.caption(
        "StudyBuddy turns your notes into a short quiz, then grades your "
        "answers with specific feedback."
    )
    st.space("small")
    st.markdown("**Setup**")
    st.caption(
        "Needs an `OPENAI_API_KEY` set in a `.env` file. "
        "See `.env.example` in the project folder."
    )

# ---------------------------------------------------------------- input
notes_text = ""
with st.container(border=True, key="input-card"):
    st.subheader("Add your material", icon=":material/upload_file:")
    tab_upload, tab_paste = st.tabs(["Upload PDF", "Paste text"])

    with tab_upload:
        uploaded = st.file_uploader("Lecture notes or textbook chapter (PDF)", type=["pdf"])
        if uploaded:
            notes_text = extract_text_from_pdf(uploaded.read())
            st.success(f"Extracted {len(notes_text):,} characters.")

    with tab_paste:
        pasted = st.text_area("Or paste your notes here", height=200)
        if pasted.strip():
            notes_text = pasted

    if notes_text.strip():
        total_chunks = len(chunk_text(notes_text))
        used_chunks = min(total_chunks, MAX_CHUNKS)
        if total_chunks > 1:
            st.caption(
                f":material/layers: {len(notes_text):,} characters, split into "
                f"{total_chunks} section(s) — the quiz will draw from "
                f"{used_chunks} of them."
            )
        else:
            st.caption(f":material/layers: {len(notes_text):,} characters.")

    st.space("small")
    col_generate, col_options = st.columns([4, 1], vertical_alignment="center")
    with col_generate:
        generate_clicked = st.button(
            "Generate quiz",
            icon=":material/bolt:",
            type="primary",
            disabled=not notes_text.strip(),
            width="stretch",
        )
    with col_options:
        with st.popover("Options", icon=":material/tune:", width="stretch"):
            num_questions = st.slider(
                "Number of questions", min_value=3, max_value=12, value=6
            )

if generate_clicked:
    with st.status("Generating your quiz...", expanded=True) as status:
        st.write("Reading your notes...")
        chunks = chunk_text(notes_text)[:MAX_CHUNKS]

        # Spread the requested question count across every chunk we're using
        # (at least 1 each) so long documents get covered end to end instead
        # of only their first section.
        base, remainder = divmod(num_questions, len(chunks))
        counts = [base + (1 if i < remainder else 0) for i in range(len(chunks))]

        try:
            all_questions = []
            for i, (piece, count) in enumerate(zip(chunks, counts), start=1):
                if count <= 0:
                    continue
                st.write(f"Writing questions from section {i} of {len(chunks)}...")
                partial_quiz = generate_quiz(piece, num_questions=count)
                all_questions.extend(partial_quiz.questions)

            for new_id, question in enumerate(all_questions, start=1):
                question.id = new_id

            st.session_state.quiz = Quiz(questions=all_questions)
            st.session_state.results = None
            status.update(label="Quiz ready", state="complete", expanded=False)
            st.toast("Quiz generated!", icon=":material/celebration:")
        except Exception as e:
            status.update(label="Generation failed", state="error", expanded=True)
            st.error(f"Couldn't generate the quiz: {e}")

# ---------------------------------------------------------------- quiz form
quiz = st.session_state.quiz
if quiz:
    with st.container(border=True, key="quiz-card"):
        col_title, col_reset = st.columns([5, 1], vertical_alignment="center")
        with col_title:
            st.subheader("Your quiz", icon=":material/quiz:")
        with col_reset:
            st.button(
                "Start over",
                icon=":material/restart_alt:",
                on_click=reset_quiz,
                key="reset_quiz_btn",
                width="stretch",
            )

        with st.form("quiz_form"):
            answers = {}
            difficulty_color = {"easy": "green", "medium": "orange", "hard": "red"}
            difficulty_hex = {"easy": "#1F7A5C", "medium": "#B45309", "hard": "#B3261E"}
            for q in quiz.questions:
                with st.container(border=True, key=f"qcard-{q.id}"):
                    accent = difficulty_hex.get(q.difficulty, "#9CA3AF")
                    st.markdown(
                        f'<div style="height:4px; width:2.5rem; border-radius:2px; '
                        f'background:{accent}; margin-bottom:0.6rem;"></div>',
                        unsafe_allow_html=True,
                    )
                    st.markdown(f"**{q.id}. {q.question}**")
                    with st.container(horizontal=True, vertical_alignment="center", key=f"meta-{q.id}"):
                        st.caption(q.topic or "General")
                        st.badge(
                            q.difficulty.capitalize(),
                            color=difficulty_color.get(q.difficulty, "gray"),
                        )
                    if q.type == "multiple_choice" and q.options:
                        answers[q.id] = st.radio(
                            "Choose one:", q.options, key=f"q_{q.id}", label_visibility="collapsed"
                        )
                    else:
                        answers[q.id] = st.text_area(
                            "Your answer:", key=f"q_{q.id}", label_visibility="collapsed"
                        )

            submitted = st.form_submit_button(
                "Submit answers", icon=":material/send:", type="primary", width="stretch"
            )

    if submitted:
        with st.status("Grading your answers...", expanded=True) as status:
            results = []
            for q in quiz.questions:
                result = grade_answer(q, answers.get(q.id, ""))
                results.append((q, result))
            st.session_state.results = results
            status.update(label="Grading complete", state="complete", expanded=False)
        st.toast("Graded! Check your results below.", icon=":material/task_alt:")

# ---------------------------------------------------------------- results
if st.session_state.results:
    results = st.session_state.results
    with st.container(border=True, key="results-card"):
        col_title, col_download, col_reset = st.columns([4, 2, 1.4], vertical_alignment="center")
        with col_title:
            st.subheader("Results", icon=":material/grading:")
        with col_download:
            st.download_button(
                "Download",
                data=build_results_report(quiz, results),
                file_name="studybuddy_results.md",
                mime="text/markdown",
                icon=":material/download:",
                width="stretch",
            )
        with col_reset:
            st.button(
                "Start over",
                icon=":material/restart_alt:",
                on_click=reset_quiz,
                key="reset_results_btn",
                width="stretch",
            )

        total = sum(r.score for _, r in results) / len(results)
        col_metric, col_bar = st.columns([1, 2], vertical_alignment="center")
        with col_metric:
            st.metric("Overall score", f"{total:.0f} / 100")
        with col_bar:
            st.progress(total / 100)

        summary_df = pd.DataFrame(
            [
                {
                    "Q": q.id,
                    "Topic": q.topic or "General",
                    "Difficulty": q.difficulty.capitalize(),
                    "Score": r.score,
                    "Correct": r.correct,
                }
                for q, r in results
            ]
        )
        st.dataframe(
            summary_df,
            hide_index=True,
            width="stretch",
            column_config={
                "Q": st.column_config.NumberColumn("Q#", width="small"),
                "Score": st.column_config.ProgressColumn(
                    "Score", min_value=0, max_value=100, format="%d"
                ),
                "Correct": st.column_config.CheckboxColumn("Correct", disabled=True),
            },
        )

        for q, r in results:
            icon = "✅" if r.correct else "❌"
            with st.expander(f"{icon} Q{q.id}: {q.question}  —  {r.score}/100"):
                st.write(f"**Your answer:** {st.session_state.get(f'q_{q.id}', '')}")
                answer_label = "Model answer" if q.type == "short_answer" else "Correct answer"
                st.write(f"**{answer_label}:** {q.correct_answer}")
                st.write(f"**Feedback:** {r.feedback}")
