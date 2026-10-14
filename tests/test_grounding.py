from engine.grounding import MockGroundingVerifier, Question, filter_grounded

MITO_PASSAGE = (
    "Mitochondria generate most of the cell's supply of adenosine "
    "triphosphate (ATP), used as a source of chemical energy."
)

PHOTOSYNTHESIS_PASSAGE = (
    "Photosynthesis is the process plants use to convert light energy "
    "into chemical energy. Chlorophyll inside the chloroplast absorbs "
    "sunlight."
)


def test_grounded_question_passes():
    verifier = MockGroundingVerifier()
    q = Question(
        id="q1",
        question="What molecule do mitochondria produce to supply the cell with energy?",
        answer="ATP (adenosine triphosphate)",
        citation=MITO_PASSAGE,
    )
    result = verifier.verify(q)
    assert result.grounded is True


def test_ungrounded_question_is_dropped():
    verifier = MockGroundingVerifier()
    q = Question(
        id="q2",
        question="What pigment absorbs sunlight during photosynthesis?",
        answer="Chlorophyll in the chloroplast.",
        citation=MITO_PASSAGE,  # wrong passage — unrelated to the question
    )
    result = verifier.verify(q)
    assert result.grounded is False


def test_question_with_no_citation_is_rejected():
    verifier = MockGroundingVerifier()
    q = Question(
        id="q3",
        question="What molecule do mitochondria produce?",
        answer="ATP",
        citation=None,
    )
    result = verifier.verify(q)
    assert result.grounded is False
    assert "no citation" in result.reason


def test_filter_grounded_splits_kept_and_dropped():
    verifier = MockGroundingVerifier()
    grounded_q = Question(
        id="q1",
        question="What molecule do mitochondria produce to supply the cell with energy?",
        answer="ATP (adenosine triphosphate)",
        citation=MITO_PASSAGE,
    )
    ungrounded_q = Question(
        id="q2",
        question="What pigment absorbs sunlight during photosynthesis?",
        answer="Chlorophyll in the chloroplast.",
        citation=MITO_PASSAGE,
    )
    no_citation_q = Question(id="q3", question="What molecule do mitochondria produce?", answer="ATP")

    kept, dropped = filter_grounded([grounded_q, ungrounded_q, no_citation_q], verifier)

    assert kept == [grounded_q]
    dropped_ids = {q.id for q, _reason in dropped}
    assert dropped_ids == {"q2", "q3"}
