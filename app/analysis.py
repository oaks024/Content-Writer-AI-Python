"""Pure heuristics for keyword density and Zero-AI detection.

Ported from the original server.ts. No external calls — all functions are
deterministic given their inputs.
"""
import re

AI_CLICHES: list[dict[str, str]] = [
    {"word": "delve", "alternatives": "explore, look into, examine"},
    {"word": "embark", "alternatives": "start, begin, set off"},
    {"word": "navigate", "alternatives": "handle, manage, work through"},
    {"word": "dive", "alternatives": "look at, explore, review"},
    {"word": "testament", "alternatives": "proof, demonstration, sign"},
    {"word": "tapestry", "alternatives": "blend, combination, mixture"},
    {"word": "moreover", "alternatives": "also, what's more, and"},
    {"word": "crucial", "alternatives": "key, vital, important"},
    {"word": "demystify", "alternatives": "explain, clarify, unlock"},
    {"word": "furthermore", "alternatives": "also, in addition"},
    {"word": "pivotal", "alternatives": "important, critical, main"},
    {"word": "beacon", "alternatives": "guide, example"},
    {"word": "essentially", "alternatives": "basically, in short"},
    {"word": "treasure trove", "alternatives": "collection, source"},
    {"word": "elevate", "alternatives": "boost, improve"},
]


def calculate_plagiarism_heuristics(text: str, keywords: list[str]) -> dict:
    """Return perplexity (0-100), burstiness (0-100), and found clichés."""
    sentences = [s.strip() for s in re.split(r"[.!?]+", text) if len(s.strip()) > 5]
    if not sentences:
        return {"perplexity": 50, "burstiness": 50, "cliche_words": []}

    lower = text.lower()
    found: list[dict] = []
    for item in AI_CLICHES:
        count = len(re.findall(rf"\b{re.escape(item['word'])}\b", lower))
        if count > 0:
            found.append({"word": item["word"], "count": count,
                          "alternatives": item["alternatives"]})

    lengths = [len(s.split()) for s in sentences]
    avg = sum(lengths) / len(lengths)
    variance = sum((n - avg) ** 2 for n in lengths) / len(lengths)
    std_dev = variance ** 0.5
    burstiness = min(round(std_dev * 8), 100)

    words = re.findall(r"\b\w+\b", lower)
    ttr = len(set(words)) / len(words) if words else 1.0
    starts = [s.split()[0].lower() for s in sentences if s.split()]
    start_div = len(set(starts)) / len(starts) if starts else 1.0
    perplexity = min(round(ttr * 60 + start_div * 40), 100)

    return {"perplexity": perplexity, "burstiness": burstiness, "cliche_words": found}


def keyword_density(text: str, keywords: list[str], target_density: float) -> list[dict]:
    """Per-keyword occurrence count, density %, and optimization status."""
    total_words = len(re.findall(r"\b\w+\b", text.lower())) or 1
    target_min = max(0.5, target_density - 0.5)
    target_max = target_density + 0.5
    table: list[dict] = []
    for kw in keywords:
        count = len(re.findall(rf"\b{re.escape(kw)}\b", text, re.IGNORECASE))
        density = round((count / total_words) * 100, 2)
        if density < target_min:
            status = "Under-optimized"
        elif density > target_max:
            status = "Over-stuffed"
        else:
            status = "Perfect"
        table.append({"keyword": kw, "count": count,
                      "density": density, "status": status})
    return table


def flag_sentences(markdown: str, prompt_flagged: list[dict],
                   heuristics: dict) -> list[dict]:
    """Merge model-flagged sentences with heuristic detection. Max 5 results."""
    sentences = [s.strip() for s in re.split(r"(?<=[.!?])\s+", markdown)
                 if len(s.strip()) > 8
                 and not s.strip().startswith("#")
                 and not s.strip().startswith("-")]
    cliche_words = {c["word"] for c in heuristics["cliche_words"]}
    flagged: list[dict] = []

    for idx, s in enumerate(sentences):
        match = next(
            (pf for pf in prompt_flagged
             if s.lower() in str(pf.get("text", "")).lower()
             or str(pf.get("text", "")).lower() in s.lower()),
            None,
        )
        if match:
            flagged.append({
                "id": f"flag-{idx}",
                "text": s,
                "score": match.get("score", 85),
                "category": match.get("category", "robotic"),
                "reason": match.get("reason", "Predictive pacing."),
                "suggestions": match.get("suggestions",
                                         ["Better active alternative.",
                                          "Smooth natural version."]),
            })
            continue

        is_cliche = any(w in s.lower() for w in cliche_words)
        word_count = len(s.split())
        is_ai_style = word_count > 18 and ("," in s or "not only" in s or is_cliche)
        if is_ai_style and len(flagged) < 5:
            flagged.append({
                "id": f"flag-{idx}",
                "text": s,
                "score": 80,
                "category": "warning",
                "reason": ("Contains common filler AI vocab." if is_cliche
                           else "Long sentence with multiple clauses."),
                "suggestions": [
                    "Make it shorter and write in active voice.",
                    f"Simply say: {s[:40]}... styled organically.",
                ],
            })
    return flagged


def overall_ai_score(flagged: list[dict], heuristics: dict) -> tuple[int, str]:
    """Weighted AI-likeness score (0-99) and a human-readable message."""
    if flagged:
        avg = sum(f["score"] for f in flagged) / len(flagged)
    else:
        avg = 20
    cliche_penalty = min(len(heuristics["cliche_words"]) * 10, 30)
    score = min(round(
        avg * 0.6
        + cliche_penalty
        + (100 - heuristics["burstiness"]) * 0.2
        + (100 - heuristics["perplexity"]) * 0.2
    ), 99)

    if score > 75:
        message = ("High AI probability. Uses boilerplate marketing "
                   "terminology and uniform transitions.")
    elif score > 40:
        message = ("Moderate AI signs. Good vocabulary range but steady "
                   "transition patterns.")
    else:
        message = "Excellent human-like layout with natural rhythm and variation."
    return score, message


def count_words(text: str) -> int:
    """Count real word tokens, ignoring markdown punctuation."""
    return len(re.findall(r"\b\w+\b", text))


def markdown_to_blocks(markdown: str) -> list[dict]:
    """Split markdown into renderable blocks for the interactive editor.

    Each block: {"kind": "heading"|"paragraph"|"bullet"|"blank",
                 "level": int, "text": str, "sentences": list[str]}.
    """
    blocks: list[dict] = []
    for line in markdown.split("\n"):
        stripped = line.strip()
        if not stripped:
            blocks.append({"kind": "blank", "level": 0, "text": "", "sentences": []})
        elif stripped.startswith("#"):
            level = len(re.match(r"^#+", stripped).group(0))
            blocks.append({"kind": "heading", "level": min(level, 3),
                           "text": re.sub(r"^#+\s*", "", stripped), "sentences": []})
        elif stripped.startswith(("- ", "* ")):
            text = re.sub(r"^[-*]\s*", "", stripped)
            blocks.append({"kind": "bullet", "level": 0, "text": text,
                           "sentences": _split_sentences(text)})
        else:
            blocks.append({"kind": "paragraph", "level": 0, "text": stripped,
                           "sentences": _split_sentences(stripped)})
    return blocks


def _split_sentences(text: str) -> list[str]:
    """Split a line into sentences, keeping terminal punctuation."""
    parts = re.split(r"(?<=[.!?])\s+", text)
    return [p.strip() for p in parts if p.strip()]
