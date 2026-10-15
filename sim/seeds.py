"""
Two disjoint seed sets for stage 3b engine development.

DEV_SEEDS: use freely while developing and comparing v2 selector variants
(sim/variants_dev.py -> sim/variants_dev.md). Burn through these however
needed — rerun, inspect, pick a winner.

HELDOUT_SEEDS: reserved. Never run until sim/run_final_report.py, which
produces the numbers that actually judge whether v2 beats random. Running
them during development, or using them to help pick a variant, would
make the final numbers meaningless (grading your own homework) — no dev
code path may import HELDOUT_SEEDS, and sim/run_final_report.py never
imports DEV_SEEDS (enforced by tests/test_seeds.py via source inspection).
"""
from __future__ import annotations

DEV_SEEDS: tuple[int, ...] = tuple(range(1, 21))            # 1..20
HELDOUT_SEEDS: tuple[int, ...] = tuple(range(10001, 10021))  # 10001..10020

assert not set(DEV_SEEDS) & set(HELDOUT_SEEDS), "DEV_SEEDS and HELDOUT_SEEDS must be disjoint"
