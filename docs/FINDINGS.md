# StudyBuddy Adaptive — simulation findings

The honest story, in the order it happened. Every number below comes
from `sim/` (stage 3 → 3c); nothing here is tuned to make a particular
engine look good — several stages exist specifically because the
previous one didn't.

## 1. v1 (BKT + SM-2 + lowest-mastery) loses to random

v1 = `engine/mastery.py` (standard BKT, no forgetting term) +
`engine/scheduler.py` (SM-2) + `engine/selector.py`'s `select_next`
(pick lowest mastery among due concepts). Tested against a synthetic
learner population (`sim/learner.py`) deliberately built on different
mechanics than BKT (concave practice-driven growth, exponential
forgetting, a logistic answer-probability curve), so the comparison
can't be accused of baking in the answer.

| Budget | Adaptive final skill (95% CI) | Random final skill (95% CI) | Diff adaptive−random (95% CI) |
|---|---|---|---|
| 5 | 0.211 [0.207, 0.216] | 0.227 [0.222, 0.232] | −0.016 [−0.016, −0.015] |
| 10 | 0.253 [0.248, 0.258] | 0.275 [0.269, 0.280] | −0.021 [−0.022, −0.020] |
| 20 | 0.315 [0.307, 0.322] | 0.330 [0.323, 0.337] | −0.015 [−0.016, −0.014] |
| 40 | 0.354 [0.344, 0.364] | 0.372 [0.363, 0.382] | −0.018 [−0.019, −0.017] |
| 80 | 0.359 [0.348, 0.369] | 0.386 [0.377, 0.396] | −0.028 [−0.029, −0.026] |

**v1 is significantly worse than random at every budget tested** — the
95% CI on the paired difference sits entirely below zero every time.

**Why:** BKT has no forgetting term. Its posterior ratchets up toward
~0.9+ after just 1-2 practices on almost any concept, regardless of
whether the answer was correct, and then it stays there — even while the
concept's *true* skill is actively decaying from forgetting in the
synthetic learner. Once the estimate saturates, "pick lowest mastery"
stops being able to discriminate between concepts, and practice ends up
allocated less evenly across concepts than uniform random achieves just
by chance (confirmed directly: v1's worst-case per-concept skill is
~0.000 at every budget — it fully abandons some concept for some
learners — versus random's less severe but still uneven ~0.000-0.001).
Because skill growth is concave (diminishing returns), uneven allocation
costs mean final skill. Full numbers: `sim/results_v1.md`.

## 2. v2 (forgetting-aware mastery + coverage-aware selection): a mixed result

v2 = `engine/mastery_v2.py` (BKT posterior, decayed toward the prior over
elapsed time with a generic, non-simulator-derived 0.05/day rate) +
`engine/selector_v2.py` (priority = (1 − decayed mastery) − coverage
penalty for concepts already heavily practiced). Variant `sqrt` was
chosen from three tried on DEV_SEEDS (`sim/variants_dev.md`); the numbers
below are its first and only run on HELDOUT_SEEDS (`sim/results_v2_final.md`).

| Budget | v2:sqrt final skill (95% CI) | Diff vs random (95% CI) |
|---|---|---|
| 5 | 0.231 [0.228, 0.234] | **+0.007** [+0.006, +0.007] |
| 10 | 0.279 [0.275, 0.283] | **+0.010** [+0.009, +0.010] |
| 20 | 0.329 [0.323, 0.334] | **+0.009** [+0.008, +0.009] |
| 40 | 0.359 [0.352, 0.366] | **+0.002** [+0.001, +0.003] |
| 80 | 0.371 [0.364, 0.378] | **−0.001** [−0.001, −0.00003] |

**v2 wins slightly over random at low-to-mid budgets (5, 10, 20, 40) and
is slightly worse at budget 80** — the budget-80 loss is statistically
real (CI excludes zero) but tiny in absolute terms (~0.0008, right at
the edge of zero with N=2000). v2's coverage is also far more even than
v1's at every budget (worst-case per-concept skill 0.003–0.028 vs v1's
~0.000), which is exactly the mechanism it was built to fix.

## 3. round_robin beats everything except a tie with v2 at budget 5

`round_robin_selector` (`engine/selector.py`) — fixed-order cycling, no
due-gating, no mastery estimate, not even randomness — was added purely
as a baseline (stage 3c) to check whether the adaptive machinery was
earning its complexity. The held-out comparison, same seeds and budgets
as above (full table from `sim/results_round_robin.md`):

| Budget | Policy | Mean final true skill (95% CI) | Diff vs round_robin (95% CI) | Mean min-per-concept | Worst-case min-per-concept |
|---|---|---|---|---|---|
| 5 | random | 0.224 [0.221, 0.228] | -0.007 [-0.007, -0.006] | 0.119 | 0.000 |
| 5 | round_robin | 0.231 [0.228, 0.235] | — | 0.119 | 0.000 |
| 5 | v1 | 0.210 [0.207, 0.213] | -0.021 [-0.022, -0.021] | 0.119 | 0.000 |
| 5 | v2:sqrt | 0.231 [0.228, 0.235] | +0.000 [+0.000, +0.000] | 0.119 | 0.000 |
| 10 | random | 0.269 [0.265, 0.273] | -0.011 [-0.012, -0.011] | 0.121 | 0.000 |
| 10 | round_robin | 0.281 [0.276, 0.285] | — | 0.208 | 0.040 |
| 10 | v1 | 0.249 [0.246, 0.253] | -0.031 [-0.032, -0.030] | 0.093 | 0.000 |
| 10 | v2:sqrt | 0.279 [0.275, 0.283] | -0.002 [-0.002, -0.002] | 0.184 | 0.028 |
| 20 | random | 0.320 [0.315, 0.325] | -0.016 [-0.016, -0.015] | 0.164 | 0.001 |
| 20 | round_robin | 0.336 [0.330, 0.341] | — | 0.289 | 0.070 |
| 20 | v1 | 0.306 [0.301, 0.312] | -0.030 [-0.030, -0.029] | 0.122 | 0.000 |
| 20 | v2:sqrt | 0.329 [0.323, 0.334] | -0.007 [-0.007, -0.007] | 0.218 | 0.016 |
| 40 | random | 0.357 [0.351, 0.363] | -0.017 [-0.017, -0.016] | 0.210 | 0.001 |
| 40 | round_robin | 0.374 [0.367, 0.381] | — | 0.326 | 0.069 |
| 40 | v1 | 0.342 [0.336, 0.349] | -0.032 [-0.033, -0.031] | 0.168 | 0.000 |
| 40 | v2:sqrt | 0.359 [0.352, 0.365] | -0.015 [-0.015, -0.014] | 0.229 | 0.008 |
| 80 | random | 0.372 [0.364, 0.379] | -0.016 [-0.017, -0.016] | 0.232 | 0.001 |
| 80 | round_robin | 0.388 [0.381, 0.395] | — | 0.343 | 0.066 |
| 80 | v1 | 0.345 [0.338, 0.353] | -0.043 [-0.044, -0.042] | 0.160 | 0.000 |
| 80 | v2:sqrt | 0.371 [0.364, 0.379] | -0.017 [-0.018, -0.017] | 0.253 | 0.003 |

**round_robin beats v1, v2, and random at every budget except budget 5,
where it ties v2:sqrt exactly** (diff 0.000 — not rounding; confirmed in
the raw JSON. At budget 5 with 6 concepts, v2's concept_id tie-break and
round_robin's cycle happen to visit concepts in the identical order
before any practice history exists to tell them apart.) At every larger
budget, round_robin wins outright, and the gap over v2:sqrt widens as
the budget grows (−0.002 → −0.007 → −0.015 → −0.017).

**Why:** in the frozen learner model, skill growth is concave (every
additional practice on the same concept helps less than the one before),
identical in form across concepts (same growth equation, just different
sampled rates per *learner*, not per *concept*), and independent of
whether the answer was correct. Under those conditions, the optimal use
of a fixed question budget is to split it as evenly as possible across
concepts — there is no concept that's harder to learn than another, so
there's nothing for an estimate to usefully discriminate. round_robin
achieves *perfectly* even coverage by construction (it cannot do
anything else); random achieves even coverage only in expectation, with
sampling variance; v2 achieves it only approximately, via a soft
continuous penalty. Perfectly even beats approximately even beats
accidentally even, in exactly that order — which is exactly the order
the results come out in.

## What this simulation cannot show

This is a simulation of a model I built, not a study of real learners.
Specifically, it cannot show:

- Whether real students' forgetting, logistic answer probability, or
  practice-driven growth actually look like `sim/learner.py`'s equations
  — those are modeling choices, not measurements.
- Whether adaptive selection would help in a world where it has
  something real to discriminate on (see below) — this simulation's
  learner model has no such structure, so "no concept is harder than
  another, and round-robin wins" is close to true *by construction*,
  not a general verdict on adaptive learning.
- Anything about engagement, motivation, time-of-day effects, multi-day
  retention outside what's modeled, or any UI/UX factor — none of that
  exists in this model at all.

## What a fair test of adaptivity would need (future work — not run)

Listed, not attempted, per instruction:

1. **Concepts of different difficulty.** The current learner model samples
   learning rate, forgetting rate, and starting skill *per learner*, but
   applies the same values to every concept that learner has. A fair
   test needs per-concept difficulty (e.g. concept-level growth-rate or
   logistic-midpoint variation), so there's something for a mastery
   estimate to legitimately discriminate between concepts on.
2. **Learning that depends on correctness.** Right now practice grows
   skill regardless of whether the answer was right or wrong. A model
   where growth (or decay resistance) depends on correctness would make
   the selector's choice of *which* concept to ask actually change the
   learning trajectory, not just the measurement opportunity.
3. **A pre-registered hypothesis.** Decide in advance what would count as
   adaptive selection "working" (effect size, budget range, which metric)
   before looking at results, to remove any residual room for
   post-hoc rationalization of whichever variant happens to win.
4. **Fresh seeds.** Both DEV_SEEDS and HELDOUT_SEEDS used so far would be
   burned; a next round needs a new disjoint held-out set never touched
   until its own final report.

These are listed as candidate next steps only. None of them have been run.

## Stage 5: the real-LLM question path is not tested against the real API

`adaptive_quiz.logic.build_llm_grounded_quiz()` (used by the Adaptive
Quiz page when `OPENAI_API_KEY` is set and notes are supplied) calls the
existing, real `src.quiz_generator.generate_quiz()` — the same function
`app.py`'s main quiz uses — then runs every generated question through
the free, deterministic `MockGroundingVerifier` before anything reaches
the quiz. **This project's automated tests and CI never call the real
API.** Every test in `tests/test_adaptive_quiz_logic.py` that exercises
`build_llm_grounded_quiz` injects an explicit `generate_quiz_fn` stub —
none of them let it fall back to the real `generate_quiz`, so no test
makes a network call. This is stated in both the module docstring in
`adaptive_quiz/logic.py` and here, deliberately, so it isn't mistaken for
"verified against OpenAI" — it's only verified against a stub that
matches the real function's interface.

### Manual test checklist (run once, with your own key)

1. Put a real key in `.env` (`OPENAI_API_KEY=...`), then run:
   ```bash
   streamlit run app.py
   ```
   and open the **Adaptive Quiz** page from the sidebar nav.
2. Confirm the page shows **"Questions from the LLM, checked against
   your notes"**, not the demo-mode banner.
3. Paste a short, factual passage you know well enough to judge — e.g.
   2-3 paragraphs from a textbook chapter or a Wikipedia summary on a
   topic you understand. Avoid pasting anything sensitive; it gets sent
   to the LLM.
4. Click **Build quiz** and record:
   - **N generated** — the number shown in the summary line.
   - **N kept** — how many questions appear in the quiz below.
   - **N dropped** — how many appear in the "Dropped questions" expander.
5. For every dropped question, read its assigned passage and reason, and
   judge for yourself: **was it actually unsupported by your notes**, or
   did the grounding verifier reject something that was genuinely
   answerable from the passage (a false rejection)? Record both counts
   (true unsupported vs. false rejection) — `MockGroundingVerifier`'s
   keyword-overlap heuristic has known false positives/negatives (see
   `evals/grounding_cases.yaml` and its reported precision/recall from
   stage 1), so some disagreement is expected; the question is whether
   it's within that expected range or clearly broken.
6. Separately, try to break the error path: temporarily set
   `OPENAI_API_KEY` to an invalid value and click **Build quiz** again.
   Confirm the page shows a clear `st.error(...)` message and does **not**
   fall back to template questions or crash.
