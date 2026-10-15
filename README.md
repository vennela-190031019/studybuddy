# StudyBuddy

A notes-to-quiz app: paste or upload notes, get a quiz generated from them,
and every generated question is checked against the notes before you see
it. Each question shows the specific sentence it's based on, and
questions the notes don't actually support are rejected rather than
shown.

<!-- screenshots go here -->

## What's in it

- **Grounded-question engine** (`engine/concepts.py`, `engine/grounding.py`) —
  extracts concepts and source passages from a document, and verifies
  that a generated question is answerable from its cited passage alone
  before it reaches a quiz.
- **Verifier + eval** (`evals/`) — the free, deterministic verifier used
  in tests and CI checks question/answer/passage overlap by keyword
  matching. Measured on 20 hand-written cases (`evals/grounding_cases.yaml`,
  written by me, not an existing benchmark): **precision 0.91, recall
  1.00** (`evals/run_grounding_eval.py` output). Being a keyword-overlap
  check, it has a real false-positive rate — see Honest limits below.
- **Evidence view** (`adaptive_quiz/logic.py`, `pages/1_Adaptive_Quiz.py`) —
  locates the cited sentence inside your original notes (exact match,
  falling back to a whitespace-normalized match, otherwise none — never
  a guess) and highlights it next to the question.
- **Mastery estimate and scheduling** (`engine/mastery.py`,
  `engine/scheduler.py`) — a Bayesian Knowledge Tracing (BKT) estimate
  per concept, and SM-2 spaced-repetition scheduling.
- **Simulation harness** (`sim/`) — a synthetic-learner simulation used to
  test whether the adaptive selection logic actually helps, before
  trusting it on real learners.

## The simulation finding

The simulation (`sim/`, full tables and methodology in
[`docs/FINDINGS.md`](docs/FINDINGS.md)) compared question-selection
policies against a synthetic learner model I built for this purpose.
The BKT-and-lowest-mastery policy (v1) lost to picking questions at
random. A revised version with a forgetting-aware estimate and a
coverage penalty (v2) closed most of that gap. A plain round-robin
policy — just cycling through concepts in a fixed order, with no
estimate at all — beat all of them at every budget tested. The reason,
as far as I can tell: in this simulated learner, skill growth is
concave, identical in form across concepts, and independent of whether
an answer was correct, so splitting practice evenly is optimal by
construction and nothing beats doing that exactly. This is a property
of my own learner model, not a result about real students — see
`docs/FINDINGS.md` for what the simulation can and can't show.

## Quickstart

```bash
python -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -r requirements.txt
.venv/bin/python -m streamlit run app.py
```

Run it as `.venv/bin/python -m streamlit run app.py`, not plain
`streamlit run app.py` — that guarantees the `streamlit` you installed
into `.venv` is the one that runs, instead of whatever `streamlit`
happens to resolve to first on your `PATH`.

Copy `.env.example` to `.env` and add an `OPENAI_API_KEY` to generate
real questions from your own notes. Without a key, the **Adaptive Quiz**
page (in the sidebar nav) runs in demo mode: a bundled sample document
and template-generated questions, no key and no API cost.

## Tests and CI

```bash
pip install -r requirements-dev.txt
pytest -q
```

Current count: **88 passed, 1 xfailed**. The one `xfail` is
`tests/test_sim.py::test_adaptive_is_not_significantly_worse_than_random`,
marked `xfail(strict=True)` — it documents the confirmed v1-loses-to-random
result (`sim/results_v1.md`) and is written so that if a future engine
change makes it pass unexpectedly, CI fails loudly rather than staying
silently green.

`.github/workflows/ci.yml` runs this same test suite on every push.

## Honest limits

- The grounding verifier is a word-overlap heuristic, not real
  entailment checking. It can and does reject valid questions, and it
  can pass invalid ones (see the 1 false positive out of 20 cases above).
- Demo mode's questions are template-generated directly from the
  document's own passages, so they're grounded by construction — they
  don't exercise the verifier the way LLM-generated questions do.
- The LLM question-generation path (`adaptive_quiz.logic.build_llm_grounded_quiz`,
  used when a key is set) is not exercised against the real API by any
  automated test or by CI — every test stubs the generator. See
  `docs/FINDINGS.md`'s manual test checklist to verify it with your own key.
- The BKT parameters (`engine/mastery.py`) are representative literature-style
  defaults, not values fitted to real learner data.
- The simulation can show properties of the specific model I built; it
  cannot show whether any of this would help a real student.

## Project structure

```
studybuddy/
├── app.py                  # original Streamlit UI — the entry point
├── pages/
│   └── 1_Adaptive_Quiz.py  # notes -> grounded quiz -> evidence view -> mastery chart
├── adaptive_quiz/
│   ├── logic.py            # page logic (Streamlit-free, unit-tested)
│   └── fixtures/           # bundled demo document + questions
├── engine/
│   ├── concepts.py         # concept + passage extraction
│   ├── grounding.py        # question/citation verifier (mock + untested LLM adapter)
│   ├── mastery.py           # BKT mastery estimate
│   ├── mastery_v2.py        # forgetting-aware mastery estimate
│   ├── scheduler.py         # SM-2 spaced repetition
│   ├── selector.py          # lowest-mastery, random, round-robin selection
│   └── selector_v2.py       # coverage-aware selection
├── sim/                     # synthetic-learner simulation harness and results
├── evals/                   # grounding verifier eval set + script
├── docs/
│   └── FINDINGS.md          # the simulation story, in full, including the negative results
├── tests/
├── src/
│   ├── extract.py          # PDF text extraction + chunking
│   ├── llm_client.py       # LLM API wrapper
│   ├── quiz_generator.py   # prompt + schema for quiz generation
│   ├── grader.py           # instant MCQ grading + LLM short-answer grading
│   └── schemas.py          # Pydantic models — the structured output contract
├── requirements.txt
└── requirements-dev.txt
```
