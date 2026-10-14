#!/usr/bin/env python3
"""
Runs engine.grounding.MockGroundingVerifier against evals/grounding_cases.yaml
and reports precision/recall. Free to run — no API key, no network call.

Usage: python evals/run_grounding_eval.py
"""
import sys
from pathlib import Path

import yaml

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from engine.grounding import MockGroundingVerifier, Question  # noqa: E402

CASES_PATH = Path(__file__).parent / "grounding_cases.yaml"


def main() -> int:
    data = yaml.safe_load(CASES_PATH.read_text())
    cases = data["cases"]
    verifier = MockGroundingVerifier()

    tp = fp = tn = fn = 0
    mismatches = []

    for case in cases:
        q = Question(
            id=case["id"],
            question=case["question"],
            answer=case["answer"],
            citation=case.get("citation"),
        )
        expected = case["expected_grounded"]
        result = verifier.verify(q)
        predicted = result.grounded

        if expected and predicted:
            tp += 1
        elif not expected and predicted:
            fp += 1
        elif not expected and not predicted:
            tn += 1
        else:
            fn += 1

        if expected != predicted:
            mismatches.append((case["id"], expected, predicted, result.reason))

    precision = tp / (tp + fp) if (tp + fp) else float("nan")
    recall = tp / (tp + fn) if (tp + fn) else float("nan")

    print(f"Cases: {len(cases)}")
    print(f"TP={tp} FP={fp} TN={tn} FN={fn}")
    print(f"Precision: {precision:.2f}")
    print(f"Recall:    {recall:.2f}")

    if mismatches:
        print("\nMismatches (id, expected, predicted, reason):")
        for case_id, expected, predicted, reason in mismatches:
            print(f"  {case_id}: expected={expected} predicted={predicted} ({reason})")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
