from app import analysis


def test_keyword_density_counts_and_status():
    text = "Solar power is great. Solar power saves money. " * 5
    table = analysis.keyword_density(text, ["solar power"], target_density=1.5)
    row = table[0]
    assert row["keyword"] == "solar power"
    assert row["count"] == 10
    assert row["status"] in ("Under-optimized", "Perfect", "Over-stuffed")


def test_heuristics_detects_cliche():
    text = "We will delve into this. Let us delve again deeply now."
    result = analysis.calculate_plagiarism_heuristics(text, [])
    words = [c["word"] for c in result["cliche_words"]]
    assert "delve" in words
    assert 0 <= result["perplexity"] <= 100
    assert 0 <= result["burstiness"] <= 100


def test_heuristics_empty_text():
    result = analysis.calculate_plagiarism_heuristics("", [])
    assert result == {"perplexity": 50, "burstiness": 50, "cliche_words": []}


def test_overall_ai_score_is_capped():
    score, message = analysis.overall_ai_score(
        flagged=[{"score": 90}, {"score": 95}],
        heuristics={"perplexity": 10, "burstiness": 10,
                    "cliche_words": [{"word": "delve"}]},
    )
    assert 0 <= score <= 99
    assert isinstance(message, str) and message


def test_markdown_to_blocks_classifies_lines():
    blocks = analysis.markdown_to_blocks("# Title\n\nA sentence here.\n- bullet one")
    kinds = [b["kind"] for b in blocks]
    assert "heading" in kinds
    assert "paragraph" in kinds
    assert "bullet" in kinds
