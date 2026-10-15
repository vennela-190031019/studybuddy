import ast
from pathlib import Path

from sim.seeds import DEV_SEEDS, HELDOUT_SEEDS

SIM_DIR = Path(__file__).parent.parent / "sim"


def _imported_names_from_sim_seeds(path: Path) -> set[str]:
    tree = ast.parse(path.read_text())
    names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module == "sim.seeds":
            names.update(alias.name for alias in node.names)
    return names


def test_dev_and_heldout_seeds_are_disjoint():
    assert set(DEV_SEEDS) & set(HELDOUT_SEEDS) == set()


def test_dev_variants_script_never_imports_heldout_seeds():
    imported = _imported_names_from_sim_seeds(SIM_DIR / "variants_dev.py")
    assert "HELDOUT_SEEDS" not in imported
    assert imported == {"DEV_SEEDS"}


def test_final_report_script_never_imports_dev_seeds():
    imported = _imported_names_from_sim_seeds(SIM_DIR / "run_final_report.py")
    assert "DEV_SEEDS" not in imported
    assert imported == {"HELDOUT_SEEDS"}


def test_shared_simulation_core_never_imports_either_seed_set():
    # sim/engine_v2_sim.py is imported by both the dev harness and the
    # final report — it must never import sim.seeds at all, so neither
    # seed set can leak into it by accident.
    imported = _imported_names_from_sim_seeds(SIM_DIR / "engine_v2_sim.py")
    assert imported == set()
