from pathlib import Path

from engine.concepts import extract_concepts

FIXTURE = Path(__file__).parent / "fixtures" / "sample_doc.txt"


def test_extracts_recurring_concepts_with_passages():
    text = FIXTURE.read_text()
    concepts = extract_concepts(text)

    by_name = {c.name.lower(): c for c in concepts}
    assert "mitochondria" in by_name
    assert "photosynthesis" in by_name

    mito = by_name["mitochondria"]
    assert len(mito.passages) == 3
    assert all("mitochondria" in p.lower() for p in mito.passages)
    assert any("powerhouse" in p.lower() for p in mito.passages)

    photo = by_name["photosynthesis"]
    assert len(photo.passages) == 2
    assert all("photosynthesis" in p.lower() for p in photo.passages)


def test_single_occurrence_terms_are_dropped():
    text = FIXTURE.read_text()
    concepts = extract_concepts(text)
    names = {c.name.lower() for c in concepts}
    # "ATP" only appears once in the fixture, so it shouldn't qualify.
    assert "atp" not in names


def test_concept_ids_are_stable_slugs():
    text = FIXTURE.read_text()
    concepts = extract_concepts(text)
    by_name = {c.name.lower(): c for c in concepts}
    assert by_name["mitochondria"].id == "mitochondria"
