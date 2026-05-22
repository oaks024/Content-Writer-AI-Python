# Content Writer AI — Python Edition Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Rebuild the Content Writer AI app (SEO competitor analysis + humanized content generation + Zero-AI detection) as a single-language Python application with a server-rendered UI.

**Architecture:** FastAPI serves Jinja2 templates. HTMX posts forms and swaps in HTML fragments; Alpine.js handles client-only UI state (tabs, drawer, editor toggle). Pure logic (heuristics, density, AI scoring) and the Groq API wrapper live in focused modules with unit tests. No build step — HTMX, Alpine, and Tailwind load from CDNs.

**Tech Stack:** Python 3.11+, FastAPI, Uvicorn, Jinja2, `groq` SDK, python-dotenv, HTMX, Alpine.js, Tailwind Play CDN, pytest.

> **Environment prerequisite:** Python 3.11+ must be installed before any `pytest`/`uvicorn` command in this plan can run. The dev machine currently has only the Microsoft Store Python stub. Install Python, then `python -m venv .venv` and activate it before Task 1.

---

## File Structure

| File | Responsibility |
|---|---|
| `requirements.txt` | Dependency pins |
| `.gitignore` / `.env.example` / `README.md` | Project meta |
| `app/__init__.py` | Marks package |
| `app/config.py` | Load `GROQ_API_KEY` from env |
| `app/analysis.py` | Pure heuristics: density, perplexity, burstiness, cliché + sentence flagging, AI score, markdown→blocks |
| `app/groq_client.py` | Groq client, model-fallback chain, retry/backoff, error formatting |
| `app/prompts.py` | Prompt-builder functions |
| `app/main.py` | FastAPI app, routes, pipeline orchestration |
| `templates/base.html` | Layout + CDN includes |
| `templates/index.html` | Config panel + empty workspace |
| `templates/partials/results.html` | Populated 4-tab workspace |
| `templates/partials/humanize.html` | Humanizer result fragment |
| `templates/partials/error.html` | Error fragment |
| `static/app.js` | Clipboard, download, apply-humanized, clear-clichés |
| `tests/test_analysis.py` | Unit tests for `analysis.py` |
| `tests/test_groq_client.py` | Unit tests for `groq_client.py` |
| `tests/test_routes.py` | FastAPI TestClient smoke tests |

---

## Task 1: Project scaffolding

**Files:**
- Create: `requirements.txt`, `.gitignore`, `.env.example`, `app/__init__.py`, `tests/__init__.py`

- [ ] **Step 1: Create `requirements.txt`**

```
fastapi==0.115.6
uvicorn[standard]==0.34.0
jinja2==3.1.5
python-multipart==0.0.20
groq==0.18.0
python-dotenv==1.0.1
pytest==8.3.4
httpx==0.28.1
```

- [ ] **Step 2: Create `.gitignore`**

```
.venv/
__pycache__/
*.pyc
.env
.pytest_cache/
```

- [ ] **Step 3: Create `.env.example`**

```
# Required for Groq API calls. Get a free key at https://console.groq.com/keys
GROQ_API_KEY="your-groq-api-key"

# Optional: port for local dev (default 8000)
PORT="8000"
```

- [ ] **Step 4: Create empty `app/__init__.py` and `tests/__init__.py`**

Both files are empty.

- [ ] **Step 5: Install dependencies and commit**

```bash
pip install -r requirements.txt
git add requirements.txt .gitignore .env.example app/__init__.py tests/__init__.py
git commit -m "chore: scaffold Python project"
```

---

## Task 2: Config module

**Files:**
- Create: `app/config.py`

- [ ] **Step 1: Write `app/config.py`**

```python
"""Environment configuration."""
import os

from dotenv import load_dotenv

load_dotenv()

GROQ_API_KEY: str = os.getenv("GROQ_API_KEY", "").strip()
PORT: int = int(os.getenv("PORT", "8000"))


def has_api_key() -> bool:
    """True when a non-empty Groq API key is configured."""
    return bool(GROQ_API_KEY)
```

- [ ] **Step 2: Commit**

```bash
git add app/config.py
git commit -m "feat: add config module"
```

---

## Task 3: Analysis module (pure heuristics)

**Files:**
- Create: `app/analysis.py`
- Test: `tests/test_analysis.py`

- [ ] **Step 1: Write the failing tests in `tests/test_analysis.py`**

```python
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
        heuristics={"perplexity": 10, "burstiness": 10, "cliche_words": [{"word": "delve"}]},
    )
    assert 0 <= score <= 99
    assert isinstance(message, str) and message


def test_markdown_to_blocks_classifies_lines():
    blocks = analysis.markdown_to_blocks("# Title\n\nA sentence here.\n- bullet one")
    kinds = [b["kind"] for b in blocks]
    assert "heading" in kinds
    assert "paragraph" in kinds
    assert "bullet" in kinds
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_analysis.py -v`
Expected: FAIL — `module 'app.analysis' has no attribute ...`

- [ ] **Step 3: Write `app/analysis.py`**

```python
"""Pure heuristics for keyword density and Zero-AI detection.

Ported from the original server.ts. No external calls — all functions are
deterministic given their inputs (except sentence-flag jitter, see note).
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
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_analysis.py -v`
Expected: PASS (5 tests)

- [ ] **Step 5: Commit**

```bash
git add app/analysis.py tests/test_analysis.py
git commit -m "feat: add analysis heuristics module with tests"
```

---

## Task 4: Groq client module

**Files:**
- Create: `app/groq_client.py`
- Test: `tests/test_groq_client.py`

- [ ] **Step 1: Write the failing tests in `tests/test_groq_client.py`**

```python
import pytest

from app import groq_client


def test_format_groq_error_quota():
    msg = groq_client.format_groq_error(Exception("Error 429 rate limit reached"))
    assert "Quota" in msg or "rate" in msg.lower()


def test_format_groq_error_plain():
    msg = groq_client.format_groq_error(Exception("something broke"))
    assert "something broke" in msg


def test_retry_with_backoff_succeeds_first_try():
    calls = []

    def action():
        calls.append(1)
        return "ok"

    assert groq_client.retry_with_backoff(action, retries=2, delay=0.01) == "ok"
    assert len(calls) == 1


def test_retry_with_backoff_retries_on_rate_limit():
    calls = []

    def action():
        calls.append(1)
        if len(calls) < 2:
            raise Exception("429 rate limit exceeded")
        return "ok"

    assert groq_client.retry_with_backoff(action, retries=3, delay=0.01) == "ok"
    assert len(calls) == 2


def test_retry_with_backoff_reraises_non_rate_limit():
    def action():
        raise ValueError("bad input")

    with pytest.raises(ValueError):
        groq_client.retry_with_backoff(action, retries=3, delay=0.01)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_groq_client.py -v`
Expected: FAIL — `module 'app.groq_client' has no attribute ...`

- [ ] **Step 3: Write `app/groq_client.py`**

```python
"""Groq API wrapper: client creation, model fallback, retry, error formatting."""
import time

from groq import Groq

from app import config

MODELS: list[str] = [
    "llama-3.3-70b-versatile",
    "mixtral-8x7b-32768",
    "llama-3.1-8b-instant",
]

_RATE_LIMIT_MARKERS = ("429", "rate limit", "quota", "exhausted", "rate exceeded")
_AUTH_MARKERS = ("api key not valid", "invalid api key", "unauthorized",
                 "incorrect api key", "invalid_api_key")


def get_client() -> Groq:
    """Return a Groq client or raise if no key is configured."""
    if not config.GROQ_API_KEY:
        raise RuntimeError(
            "GROQ_API_KEY is not configured. Add it to your environment "
            "or .env file. Get a free key at https://console.groq.com/keys"
        )
    return Groq(api_key=config.GROQ_API_KEY)


def retry_with_backoff(action, retries: int = 4, delay: float = 1.5):
    """Call `action`; retry rate-limit failures with exponential backoff."""
    try:
        return action()
    except Exception as error:  # noqa: BLE001 - intentional broad catch
        text = str(error).lower()
        is_rate_limit = any(m in text for m in _RATE_LIMIT_MARKERS)
        if is_rate_limit and retries > 0:
            time.sleep(delay)
            return retry_with_backoff(action, retries - 1, delay * 2)
        raise


def format_groq_error(error: Exception,
                      fallback: str = "Something went wrong during generation."
                      ) -> str:
    """Translate a Groq exception into a user-friendly message."""
    message = str(error) or fallback
    lowered = message.lower()
    if any(m in lowered for m in ("quota", "rate limit", "429", "exhausted")):
        return (f"Groq API quota exceeded: {message.strip()}. "
                "Wait a minute and retry, or check your key at "
                "https://console.groq.com/keys")
    return message


def safe_generate(prompt: str, json_mode: bool = False,
                  temperature: float | None = None) -> str:
    """Run a completion against the model-fallback chain. Returns the text.

    Raises the last error if every model fails. Auth errors short-circuit.
    """
    client = get_client()
    last_error: Exception | None = None

    for model in MODELS:
        try:
            options: dict = {
                "model": model,
                "messages": [{"role": "user", "content": prompt}],
            }
            if temperature is not None:
                options["temperature"] = temperature
            if json_mode:
                options["response_format"] = {"type": "json_object"}

            response = retry_with_backoff(
                lambda: client.chat.completions.create(**options)
            )
            return response.choices[0].message.content or ""
        except Exception as error:  # noqa: BLE001
            last_error = error
            if any(m in str(error).lower() for m in _AUTH_MARKERS):
                raise
            continue

    raise last_error if last_error else RuntimeError("All Groq models failed.")
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_groq_client.py -v`
Expected: PASS (5 tests)

- [ ] **Step 5: Commit**

```bash
git add app/groq_client.py tests/test_groq_client.py
git commit -m "feat: add Groq client with model fallback and retry"
```

---

## Task 5: Prompts module

**Files:**
- Create: `app/prompts.py`

- [ ] **Step 1: Write `app/prompts.py`**

```python
"""Prompt builders for the Groq calls. Ported verbatim in intent from server.ts."""


def search_prompt(page_title: str, company: str, keywords: list[str]) -> str:
    """Prompt for the competitive-landscape summary call."""
    return (
        f'Analyze top ranking guidelines, word counts, semantic structures, '
        f'FAQs and reader intents for: Topic: "{page_title}", '
        f'Company: "{company or "N/A"}", '
        f'Keywords: {", ".join(keywords[:4])}. '
        f'Identify gaps that make existing content sound generic or unhelpful.'
    )


def humanize_prompt(sentence: str) -> str:
    """Prompt for rewriting a single sentence to sound human."""
    return f'''You are an expert copyeditor who makes writing sound natural and authentic.
You hate typical "AI voice" (excessive adjectives, passive verbs, corporate fluff).

Re-write the following sentence to sound like an authority-expert writing casually.
Use active verbs, keep it punchy, and reduce uniform structure.

Sentence to rewrite: "{sentence}"

Return a valid JSON object with this schema:
{{
  "originalText": "...",
  "humanizedText": "One single perfect humanized version.",
  "improvedScore": 12,
  "explanation": "Brief one-sentence explanation of what changed."
}}'''


def builder_prompt(*, page_title: str, company: str, content_type: str,
                   primary: list[str], secondary: list[str], lsi: list[str],
                   tone: str, audience: str, word_count: int,
                   density: float, search_summary: str) -> str:
    """The large prompt that produces the full structured JSON result."""
    strategy = ("Value-Driven Authority Blog Post" if content_type == "blog"
                else "High-Converting Website Copy")
    return f'''You are a master Google SEO Content Architect.
Competitive search analysis context:
- Company/Client: "{company or "the Client"}"
- Target Page Title: "{page_title}"
- Content Strategy: "{strategy}"
- PRIMARY KEYWORDS: {", ".join(primary)} (place the primary keyword in the
  introduction, conclusion, and at least one subheading)
- SECONDARY KEYWORDS: {", ".join(secondary)}
- LSI KEYWORDS: {", ".join(lsi)}
- Writing Tone: "{tone or "conversational, human, approachable"}"
- Target Audience: "{audience or "general buyers seeking value"}"
- Target Word Count: {word_count} words
- Target Keyword Density: {density}% (natural, no keyword stuffing)

REAL-WORLD SEARCH INSIGHTS:
{search_summary}

RULES:
1. Never use these AI words: delve, embark, navigate, dive, tapestry,
   pivotal, demystify, furthermore, moreover, crucial, elevate.
2. Short sentences, plain words, active voice, concise paragraphs.
3. Explain what makes {company or "us"} genuinely different and helpful.
4. If a blog post, include exactly 5 FAQs; each answer 30-40 words.
5. Provide SEO fields: title, slug, metaDescription, googleNewsHeading,
   uniqueAngleAdded.

Return a SINGLE valid JSON object with exactly these keys:
{{
  "competitors": [
    {{"name": "", "url": "", "wordCount": 1100, "headings": [],
      "keywordDensity": {{"primary": 1.2}}, "strengths": [],
      "weaknesses": [], "structuralPattern": ""}}
  ],
  "gaps": [
    {{"title": "", "description": "", "importance": "High",
      "recommendedSubheadings": []}}
  ],
  "generatedContent": {{
    "title": "", "slug": "", "metaDescription": "",
    "googleNewsHeading": "", "uniqueAngleAdded": "",
    "markdown": "# Heading...", "wordCount": 1500,
    "headingsList": [{{"level": 1, "text": ""}}]
  }},
  "flaggedSentences": [
    {{"text": "", "score": 85, "category": "robotic",
      "reason": "", "suggestions": []}}
  ],
  "auditRecommendations": [
    {{"id": "originality", "criteria": "", "status": "pass",
      "description": "", "guideline": ""}}
  ]
}}
competitors must have exactly 3 items, gaps exactly 3, auditRecommendations
exactly 5. Output ONLY the JSON object, no markdown fences.'''
```

- [ ] **Step 2: Commit**

```bash
git add app/prompts.py
git commit -m "feat: add prompt builders"
```

---

## Task 6: FastAPI app, routes, and pipeline

**Files:**
- Create: `app/main.py`
- Test: `tests/test_routes.py`

- [ ] **Step 1: Write the failing tests in `tests/test_routes.py`**

```python
from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_index_renders():
    response = client.get("/")
    assert response.status_code == 200
    assert "Content Writer AI" in response.text


def test_health_reports_key_status():
    response = client.get("/health")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert "has_api_key" in body


def test_analyze_requires_title():
    response = client.post("/analyze-and-write", data={
        "page_title": "", "primary_keywords": "x",
    })
    assert response.status_code == 200
    assert "required" in response.text.lower() or "error" in response.text.lower()
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_routes.py -v`
Expected: FAIL — `cannot import name 'app' from 'app.main'`

- [ ] **Step 3: Write `app/main.py`**

```python
"""FastAPI app: routes, request parsing, and pipeline orchestration."""
import json

from fastapi import FastAPI, Form, Request
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from app import analysis, config, prompts
from app.groq_client import format_groq_error, safe_generate

app = FastAPI(title="Content Writer AI")
app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")

# Fallback grounding sources shown when live search returns nothing usable.
_FALLBACK_SOURCES = [
    {"title": "SEO Competitive Analysis Benchmark",
     "uri": "https://www.hubspot.com/seo-competitive-analysis"},
    {"title": "Google Helpful Content Guidelines",
     "uri": "https://developers.google.com/search/docs/fundamentals/creating-helpful-content"},
    {"title": "SEO Competitor Analysis Playbook",
     "uri": "https://ahrefs.com/blog/seo-competitor-analysis"},
]


def _split_keywords(raw: str) -> list[str]:
    return [k.strip() for k in (raw or "").split(",") if k.strip()]


def _parse_json(text: str) -> dict:
    """Parse model JSON, retrying once after stripping markdown fences."""
    text = (text or "").strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        cleaned = text.removeprefix("```json").removeprefix("```").removesuffix("```").strip()
        return json.loads(cleaned)


@app.get("/", response_class=HTMLResponse)
def index(request: Request):
    return templates.TemplateResponse(
        "index.html", {"request": request, "has_api_key": config.has_api_key()}
    )


@app.get("/health")
def health():
    return JSONResponse({"status": "ok", "has_api_key": config.has_api_key()})


@app.post("/analyze-and-write", response_class=HTMLResponse)
def analyze_and_write(
    request: Request,
    page_title: str = Form(""),
    company_name: str = Form(""),
    content_type: str = Form("blog"),
    primary_keywords: str = Form(""),
    secondary_keywords: str = Form(""),
    lsi_keywords: str = Form(""),
    tone: str = Form("Professional"),
    audience: str = Form("General Buyers"),
    target_word_count: int = Form(1500),
    target_density: float = Form(1.2),
):
    primary = _split_keywords(primary_keywords)
    secondary = _split_keywords(secondary_keywords)
    lsi = _split_keywords(lsi_keywords)
    all_keywords = primary + secondary + lsi

    if not page_title.strip():
        return _error(request, "Page Title / Topic Goal is required.")
    if not all_keywords:
        return _error(request, "Provide at least one keyword.")
    if not config.has_api_key():
        return _error(request, "GROQ_API_KEY is not configured on the server.")

    try:
        # Call 1: competitive-landscape summary (best effort).
        try:
            search_summary = safe_generate(
                prompts.search_prompt(page_title, company_name, all_keywords)
            )
        except Exception:  # noqa: BLE001 - fall back to a generic summary
            search_summary = "Standard online authority layouts."

        # Call 2: the structured JSON build.
        raw = safe_generate(
            prompts.builder_prompt(
                page_title=page_title, company=company_name,
                content_type=content_type, primary=primary,
                secondary=secondary, lsi=lsi, tone=tone, audience=audience,
                word_count=target_word_count, density=target_density,
                search_summary=search_summary,
            ),
            json_mode=True, temperature=0.82,
        )
        result = _parse_json(raw)
    except json.JSONDecodeError:
        return _error(request, "The model returned malformed content. "
                               "Try fewer or simpler keywords and retry.")
    except Exception as error:  # noqa: BLE001
        return _error(request, format_groq_error(error))

    # Fill missing competitor URLs from fallback sources.
    for i, comp in enumerate(result.get("competitors", [])):
        if not comp.get("url"):
            src = _FALLBACK_SOURCES[i] if i < len(_FALLBACK_SOURCES) else None
            comp["url"] = src["uri"] if src else f"https://example.com/competitor-{i+1}"

    content = result.get("generatedContent", {})
    markdown = content.get("markdown", "")

    density_table = analysis.keyword_density(markdown, all_keywords, target_density)
    heuristics = analysis.calculate_plagiarism_heuristics(markdown, all_keywords)
    flagged = analysis.flag_sentences(
        markdown, result.get("flaggedSentences", []), heuristics)
    score, message = analysis.overall_ai_score(flagged, heuristics)

    context = {
        "request": request,
        "competitors": result.get("competitors", []),
        "gaps": result.get("gaps", []),
        "content": content,
        "blocks": analysis.markdown_to_blocks(markdown),
        "markdown": markdown,
        "density_table": density_table,
        "audit": result.get("auditRecommendations", []),
        "ai": {
            "score": score, "message": message,
            "perplexity": heuristics["perplexity"],
            "burstiness": heuristics["burstiness"],
            "cliches": heuristics["cliche_words"],
            "flagged": flagged,
        },
        "target_density": target_density,
    }
    return templates.TemplateResponse("partials/results.html", context)


@app.post("/humanize-sentence", response_class=HTMLResponse)
def humanize_sentence(request: Request, sentence: str = Form("")):
    if not sentence.strip():
        return _error(request, "No sentence provided.")
    if not config.has_api_key():
        return _error(request, "GROQ_API_KEY is not configured on the server.")
    try:
        raw = safe_generate(prompts.humanize_prompt(sentence),
                            json_mode=True, temperature=0.9)
        data = _parse_json(raw)
    except Exception as error:  # noqa: BLE001
        return _error(request, format_groq_error(error, "Failed to edit sentence."))

    return templates.TemplateResponse("partials/humanize.html", {
        "request": request,
        "original": data.get("originalText", sentence),
        "humanized": data.get("humanizedText", sentence),
        "improved_score": data.get("improvedScore", 15),
        "explanation": data.get("explanation", ""),
    })


def _error(request: Request, message: str) -> HTMLResponse:
    return templates.TemplateResponse(
        "partials/error.html", {"request": request, "message": message})
```

- [ ] **Step 4: Run tests — they still fail (templates missing)**

Run: `pytest tests/test_routes.py -v`
Expected: FAIL — `jinja2.exceptions.TemplateNotFound`. Templates are built in Tasks 7-8; tests pass after Task 8.

- [ ] **Step 5: Commit**

```bash
git add app/main.py tests/test_routes.py
git commit -m "feat: add FastAPI routes and analysis pipeline"
```

---

## Task 7: Base layout and index page

**Files:**
- Create: `templates/base.html`, `templates/index.html`

- [ ] **Step 1: Write `templates/base.html`**

```html
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>Content Writer AI</title>
  <script src="https://cdn.tailwindcss.com"></script>
  <script src="https://unpkg.com/htmx.org@2.0.4"></script>
  <script defer src="https://unpkg.com/alpinejs@3.14.8/dist/cdn.min.js"></script>
  <script defer src="/static/app.js"></script>
</head>
<body class="bg-gray-50 text-gray-900 font-sans">
  <header class="bg-white border-b border-gray-200 px-6 py-4 flex items-center space-x-3">
    <div class="w-10 h-10 rounded-xl bg-gray-900 flex items-center justify-center text-yellow-400 font-bold">CW</div>
    <div>
      <h1 class="text-xl font-bold">Content Writer AI</h1>
      <p class="text-xs text-gray-500">SEO Auditor &amp; Zero-GPT Humanizer — Python Edition</p>
    </div>
  </header>
  {% block body %}{% endblock %}
</body>
</html>
```

- [ ] **Step 2: Write `templates/index.html`**

```html
{% extends "base.html" %}
{% block body %}
<div class="flex flex-col lg:flex-row">
  <aside class="w-full lg:w-[400px] bg-white border-r border-gray-200 p-6 space-y-4">
    <h2 class="font-semibold text-gray-800 border-b pb-2">SEO Configuration</h2>
    {% if not has_api_key %}
    <div class="p-3 bg-amber-50 border border-amber-200 rounded-lg text-amber-800 text-xs">
      <strong>GROQ_API_KEY missing.</strong> Add it to the server's environment.
      Get a free key at console.groq.com/keys
    </div>
    {% endif %}
    <form hx-post="/analyze-and-write" hx-target="#workspace" hx-indicator="#loading"
          class="space-y-3">
      <label class="block text-xs font-semibold uppercase text-gray-600">Company / Brand
        <input name="company_name" type="text" placeholder="e.g., EcoHeat HVAC"
               class="mt-1 w-full px-3 py-2 border border-gray-300 rounded-lg text-sm" />
      </label>
      <label class="block text-xs font-semibold uppercase text-gray-600">Content Type
        <select name="content_type" class="mt-1 w-full px-3 py-2 border border-gray-300 rounded-lg text-sm">
          <option value="blog">Blog Post</option>
          <option value="website">Website Page</option>
        </select>
      </label>
      <label class="block text-xs font-semibold uppercase text-gray-600">Page Title / Topic Goal *
        <input name="page_title" type="text" required placeholder="e.g., Guide to Geothermal Heating"
               class="mt-1 w-full px-3 py-2 border border-gray-300 rounded-lg text-sm" />
      </label>
      <label class="block text-xs font-semibold uppercase text-gray-600">Primary Keywords
        <input name="primary_keywords" type="text" placeholder="comma, separated"
               class="mt-1 w-full px-3 py-2 border border-gray-300 rounded-lg text-sm" />
      </label>
      <label class="block text-xs font-semibold uppercase text-gray-600">Secondary Keywords
        <input name="secondary_keywords" type="text" placeholder="comma, separated"
               class="mt-1 w-full px-3 py-2 border border-gray-300 rounded-lg text-sm" />
      </label>
      <label class="block text-xs font-semibold uppercase text-gray-600">LSI Keywords
        <input name="lsi_keywords" type="text" placeholder="comma, separated"
               class="mt-1 w-full px-3 py-2 border border-gray-300 rounded-lg text-sm" />
      </label>
      <label class="block text-xs font-semibold uppercase text-gray-600">Tone
        <input name="tone" type="text" value="Professional"
               class="mt-1 w-full px-3 py-2 border border-gray-300 rounded-lg text-sm" />
      </label>
      <label class="block text-xs font-semibold uppercase text-gray-600">Audience
        <input name="audience" type="text" value="General Buyers"
               class="mt-1 w-full px-3 py-2 border border-gray-300 rounded-lg text-sm" />
      </label>
      <label class="block text-xs font-semibold uppercase text-gray-600">Target Word Count
        <input name="target_word_count" type="number" value="1500" min="400" max="3000"
               class="mt-1 w-full px-3 py-2 border border-gray-300 rounded-lg text-sm" />
      </label>
      <label class="block text-xs font-semibold uppercase text-gray-600">Target Density (%)
        <input name="target_density" type="number" value="1.2" step="0.1" min="0.5" max="3.0"
               class="mt-1 w-full px-3 py-2 border border-gray-300 rounded-lg text-sm" />
      </label>
      <button type="submit"
              class="w-full py-3 bg-gray-900 hover:bg-gray-800 text-white rounded-xl font-medium">
        Analyze &amp; Write Humanized Content
      </button>
      <p id="loading" class="htmx-indicator text-center text-sm text-gray-500">
        Analyzing competitors and drafting content… (15-30s)
      </p>
    </form>
  </aside>
  <main id="workspace" class="flex-1 p-6">
    <div class="flex items-center justify-center h-full text-center text-gray-400 py-20">
      <div>
        <h3 class="text-2xl font-bold text-gray-700">SEO Content Blueprint Room</h3>
        <p class="mt-2 text-sm">Fill the form and generate competitor analysis,
          humanized copy, and a Zero-AI report.</p>
      </div>
    </div>
  </main>
</div>
{% endblock %}
```

- [ ] **Step 3: Commit**

```bash
git add templates/base.html templates/index.html
git commit -m "feat: add base layout and index page"
```

---

## Task 8: Result partials

**Files:**
- Create: `templates/partials/results.html`, `templates/partials/humanize.html`, `templates/partials/error.html`

- [ ] **Step 1: Write `templates/partials/error.html`**

```html
<div class="p-4 bg-red-50 border border-red-200 rounded-xl text-red-800 text-sm">
  <strong>Operation failed:</strong> {{ message }}
</div>
```

- [ ] **Step 2: Write `templates/partials/humanize.html`**

```html
<div class="space-y-3">
  <p class="text-xs uppercase font-bold text-emerald-600">Humanized version
    (AI likeness ~{{ improved_score }}%)</p>
  <p class="p-3 bg-emerald-50 border border-emerald-200 rounded-lg text-sm"
     data-humanized>{{ humanized }}</p>
  <p class="text-xs text-gray-500">{{ explanation }}</p>
  <button type="button"
          onclick="applyHumanized(this)"
          data-original="{{ original }}"
          data-new="{{ humanized }}"
          class="w-full py-2 bg-emerald-600 hover:bg-emerald-500 text-white rounded-lg text-xs font-semibold">
    Swap into content
  </button>
</div>
```

- [ ] **Step 3: Write `templates/partials/results.html`**

```html
<div x-data="{ tab: 'write', editMode: 'interactive', drawer: null }" class="space-y-4">
  <!-- Tab bar -->
  <div class="bg-white border border-gray-200 rounded-xl p-1.5 flex flex-wrap gap-1">
    <template x-for="t in [
        {id:'write',label:'Writing Room'},
        {id:'competitors',label:'Competitors & Gaps'},
        {id:'detector',label:'Zero AI Analytics'},
        {id:'audit',label:'SEO Audit'}]" :key="t.id">
      <button type="button" @click="tab = t.id"
              :class="tab === t.id ? 'bg-gray-900 text-white' : 'text-gray-600 hover:bg-gray-100'"
              class="px-4 py-2 rounded-lg text-sm font-medium" x-text="t.label"></button>
    </template>
  </div>

  <!-- 1. Writing Room -->
  <div x-show="tab === 'write'" class="space-y-4">
    <div class="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-4 gap-3">
      <div class="p-3 bg-white border rounded-lg">
        <p class="text-2xs font-bold uppercase text-gray-400">URL Slug</p>
        <code class="text-xs">/{{ content.slug }}</code>
      </div>
      <div class="p-3 bg-white border rounded-lg">
        <p class="text-2xs font-bold uppercase text-gray-400">Meta Description</p>
        <p class="text-xs text-gray-600">{{ content.metaDescription }}</p>
      </div>
      <div class="p-3 bg-white border rounded-lg">
        <p class="text-2xs font-bold uppercase text-gray-400">Google News Heading</p>
        <p class="text-xs text-gray-700">{{ content.googleNewsHeading }}</p>
      </div>
      <div class="p-3 bg-indigo-50 border border-indigo-200 rounded-lg">
        <p class="text-2xs font-bold uppercase text-indigo-500">Unique Angle</p>
        <p class="text-xs text-indigo-900">{{ content.uniqueAngleAdded }}</p>
      </div>
    </div>

    <div class="grid grid-cols-1 xl:grid-cols-3 gap-4">
      <div class="xl:col-span-2 bg-white border rounded-xl p-5">
        <div class="flex justify-between items-center border-b pb-2 mb-3">
          <h3 class="font-semibold">SEO Humanized Copy</h3>
          <div class="flex gap-1 text-xs">
            <button type="button" @click="editMode='interactive'"
                    :class="editMode==='interactive' ? 'bg-gray-900 text-white' : 'bg-gray-100'"
                    class="px-2 py-1 rounded">Interactive</button>
            <button type="button" @click="editMode='raw'"
                    :class="editMode==='raw' ? 'bg-gray-900 text-white' : 'bg-gray-100'"
                    class="px-2 py-1 rounded">Raw Markdown</button>
          </div>
        </div>

        <!-- Interactive view -->
        <div x-show="editMode==='interactive'" id="interactive-content"
             class="prose prose-sm max-w-none leading-relaxed">
          {% for block in blocks %}
            {% if block.kind == 'heading' %}
              <h{{ block.level }} class="font-bold mt-3">{{ block.text }}</h{{ block.level }}>
            {% elif block.kind == 'bullet' %}
              <li class="ml-5 list-disc">{{ block.text }}</li>
            {% elif block.kind == 'paragraph' %}
              <p class="my-2">
                {% for sentence in block.sentences %}
                  {% set flag = (ai.flagged | selectattr('text', 'equalto', sentence) | first) %}
                  {% if flag %}
                    <span class="bg-amber-100 hover:bg-amber-200 rounded cursor-pointer px-0.5"
                          @click="drawer = {{ flag | tojson | forceescape }}">{{ sentence }}</span>
                  {% else %}
                    <span>{{ sentence }}</span>
                  {% endif %}
                {% endfor %}
              </p>
            {% endif %}
          {% endfor %}
        </div>

        <!-- Raw view -->
        <textarea x-show="editMode==='raw'" id="raw-markdown"
                  class="w-full h-96 font-mono text-xs border rounded p-2">{{ markdown }}</textarea>

        <div class="flex gap-3 mt-3 text-xs">
          <button type="button" onclick="copyContent()"
                  class="px-3 py-1.5 bg-gray-100 rounded">Copy</button>
          <button type="button" onclick="downloadContent()"
                  class="px-3 py-1.5 bg-gray-100 rounded">Download .md</button>
          <span class="text-gray-400 self-center">Words: {{ content.wordCount }}</span>
        </div>
      </div>

      <!-- Density + outline sidebar -->
      <div class="space-y-4">
        <!-- Humanizer drawer -->
        <div x-show="drawer" class="bg-gray-900 text-white rounded-xl p-4 space-y-3">
          <div class="flex justify-between">
            <h4 class="font-semibold">Sentence Humanizer</h4>
            <button type="button" @click="drawer = null" class="text-xs">✕</button>
          </div>
          <p class="text-xs italic bg-gray-800 p-2 rounded" x-text="drawer?.text"></p>
          <form hx-post="/humanize-sentence" hx-target="#humanize-result">
            <input type="hidden" name="sentence" :value="drawer?.text" />
            <button type="submit"
                    class="w-full py-2 bg-white text-gray-900 rounded text-xs font-semibold">
              Run Colloquial Optimizer
            </button>
          </form>
          <div id="humanize-result"></div>
        </div>

        <div class="bg-white border rounded-xl p-4">
          <h4 class="font-semibold text-sm border-b pb-2 mb-2">Keyword Densities
            (target ~{{ target_density }}%)</h4>
          {% for row in density_table %}
          <div class="py-1.5 border-b last:border-0">
            <div class="flex justify-between text-xs">
              <span class="font-mono">"{{ row.keyword }}"</span>
              <span class="font-semibold
                {% if row.status=='Perfect' %}text-emerald-600
                {% elif row.status=='Over-stuffed' %}text-rose-600
                {% else %}text-amber-600{% endif %}">{{ row.status }}</span>
            </div>
            <p class="text-2xs text-gray-500">{{ row.count }}× — {{ row.density }}%</p>
          </div>
          {% endfor %}
        </div>

        <div class="bg-white border rounded-xl p-4">
          <h4 class="font-semibold text-sm border-b pb-2 mb-2">Structural Outline</h4>
          {% for h in content.headingsList %}
          <div class="text-xs py-0.5" style="padding-left: {{ (h.level - 1) * 12 }}px">
            <span class="font-mono text-gray-400">H{{ h.level }}</span> {{ h.text }}
          </div>
          {% endfor %}
        </div>
      </div>
    </div>
  </div>

  <!-- 2. Competitors & Gaps -->
  <div x-show="tab === 'competitors'" class="space-y-4">
    <div class="grid grid-cols-1 md:grid-cols-3 gap-4">
      {% for c in competitors %}
      <div class="bg-white border rounded-xl p-4 space-y-2">
        <p class="text-2xs font-bold text-gray-400">RANKED RESULT {{ loop.index }}</p>
        <h4 class="font-bold">{{ c.name }}</h4>
        <a href="{{ c.url }}" target="_blank" rel="noopener"
           class="text-xs text-blue-600 break-all">{{ c.url }}</a>
        <p class="text-xs"><strong>{{ c.wordCount }}</strong> words —
          {{ c.structuralPattern }}</p>
        <p class="text-2xs font-semibold uppercase text-emerald-600">Strengths</p>
        <ul class="text-xs list-disc ml-4">
          {% for s in c.strengths %}<li>{{ s }}</li>{% endfor %}
        </ul>
        <p class="text-2xs font-semibold uppercase text-amber-600">Weaknesses</p>
        <ul class="text-xs list-disc ml-4">
          {% for w in c.weaknesses %}<li>{{ w }}</li>{% endfor %}
        </ul>
      </div>
      {% endfor %}
    </div>
    <div class="bg-white border rounded-xl p-5">
      <h4 class="font-bold mb-3">Opportunities &amp; Gaps</h4>
      <table class="w-full text-left text-sm">
        <thead><tr class="text-xs uppercase text-gray-400 border-b">
          <th class="py-2">Gap</th><th>Priority</th><th>Description</th><th>Subheadings</th>
        </tr></thead>
        <tbody>
          {% for g in gaps %}
          <tr class="border-b">
            <td class="py-3 font-bold">{{ g.title }}</td>
            <td><span class="text-2xs px-2 py-0.5 rounded border">{{ g.importance }}</span></td>
            <td class="text-xs text-gray-500">{{ g.description }}</td>
            <td class="text-2xs font-mono">
              {% for s in g.recommendedSubheadings %}{{ s }}{% if not loop.last %} · {% endif %}{% endfor %}
            </td>
          </tr>
          {% endfor %}
        </tbody>
      </table>
    </div>
  </div>

  <!-- 3. Zero AI Analytics -->
  <div x-show="tab === 'detector'" class="space-y-4">
    <div class="grid grid-cols-1 md:grid-cols-3 gap-4">
      <div class="bg-white border rounded-xl p-5 text-center">
        <p class="text-xs uppercase text-gray-500">AI Probability</p>
        <p class="text-5xl font-bold mt-3
          {% if ai.score > 65 %}text-red-600
          {% elif ai.score > 35 %}text-amber-600
          {% else %}text-emerald-600{% endif %}">{{ ai.score }}%</p>
        <p class="text-xs text-gray-500 mt-3 italic">{{ ai.message }}</p>
      </div>
      <div class="bg-white border rounded-xl p-5 text-center">
        <p class="text-xs uppercase text-gray-500">Perplexity</p>
        <p class="text-4xl font-semibold mt-3">{{ ai.perplexity }}/100</p>
      </div>
      <div class="bg-white border rounded-xl p-5 text-center">
        <p class="text-xs uppercase text-gray-500">Burstiness</p>
        <p class="text-4xl font-semibold mt-3">{{ ai.burstiness }}/100</p>
      </div>
    </div>
    <div class="bg-white border rounded-xl p-5">
      <div class="flex justify-between items-center mb-3">
        <h4 class="font-bold">AI Cliché Finder</h4>
        {% if ai.cliches %}
        <button type="button" onclick="clearCliches(this)"
                data-cliches='{{ ai.cliches | tojson }}'
                class="text-xs px-3 py-1.5 bg-gray-900 text-white rounded">
          Replace All Clichés
        </button>
        {% endif %}
      </div>
      {% if ai.cliches %}
      <div class="grid grid-cols-2 md:grid-cols-3 gap-2">
        {% for c in ai.cliches %}
        <div class="p-2 border rounded text-xs">
          <strong>{{ c.word }}</strong> ({{ c.count }}×)
          <span class="block text-emerald-600">→ {{ c.alternatives.split(',')[0] }}</span>
        </div>
        {% endfor %}
      </div>
      {% else %}
      <p class="text-sm text-gray-500">No common AI clichés found. Clean copy.</p>
      {% endif %}
    </div>
    <div class="bg-white border rounded-xl p-5">
      <h4 class="font-bold mb-3">Flagged Sentences</h4>
      {% for f in ai.flagged %}
      <div class="p-3 border rounded-lg mb-2 cursor-pointer hover:border-gray-400"
           @click="tab='write'; drawer = {{ f | tojson | forceescape }}">
        <p class="text-2xs font-mono uppercase">{{ f.category }} — likeness {{ f.score }}%</p>
        <p class="text-sm italic">"{{ f.text }}"</p>
        <p class="text-xs text-gray-400">{{ f.reason }}</p>
      </div>
      {% else %}
      <p class="text-sm text-gray-500">No sentences flagged.</p>
      {% endfor %}
    </div>
  </div>

  <!-- 4. SEO Audit -->
  <div x-show="tab === 'audit'" class="space-y-3">
    <div class="bg-white border rounded-xl p-5">
      <h4 class="font-bold mb-3">Google Helpful Content Audit</h4>
      {% for rec in audit %}
      <div class="p-3 border rounded-lg mb-2
        {% if rec.status=='pass' %}border-emerald-200 bg-emerald-50/30
        {% else %}border-amber-200 bg-amber-50/30{% endif %}">
        <div class="flex justify-between">
          <strong class="text-sm">{{ rec.criteria }}</strong>
          <span class="text-2xs uppercase">{{ rec.status }}</span>
        </div>
        <p class="text-xs text-gray-500">{{ rec.description }}</p>
        <p class="text-2xs text-gray-400 italic mt-1">Rule: {{ rec.guideline }}</p>
      </div>
      {% endfor %}
    </div>
  </div>
</div>
```

- [ ] **Step 4: Run route tests to verify they pass**

Run: `pytest tests/test_routes.py -v`
Expected: PASS (3 tests) — templates now resolve.

- [ ] **Step 5: Commit**

```bash
git add templates/partials/
git commit -m "feat: add result, humanize, and error partials"
```

---

## Task 9: Static JS, README, and full verification

**Files:**
- Create: `static/app.js`, `README.md`

- [ ] **Step 1: Write `static/app.js`**

```javascript
// Client-only helpers: clipboard, download, and content mutations that
// must not trigger another AI call.

function getMarkdown() {
  const raw = document.getElementById("raw-markdown");
  return raw ? raw.value : "";
}

function copyContent() {
  navigator.clipboard.writeText(getMarkdown());
}

function downloadContent() {
  const blob = new Blob([getMarkdown()], { type: "text/markdown" });
  const a = document.createElement("a");
  a.href = URL.createObjectURL(blob);
  a.download = "seo-content.md";
  a.click();
  URL.revokeObjectURL(a.href);
}

// Swap a humanized sentence into both the raw textarea and interactive view.
function applyHumanized(button) {
  const oldText = button.dataset.original;
  const newText = button.dataset.new;
  const raw = document.getElementById("raw-markdown");
  if (raw) raw.value = raw.value.split(oldText).join(newText);

  document.querySelectorAll("#interactive-content span").forEach((span) => {
    if (span.textContent.trim() === oldText.trim()) {
      span.textContent = newText;
      span.classList.remove("bg-amber-100", "hover:bg-amber-200", "cursor-pointer");
    }
  });
}

// Replace every detected cliché with its first suggested alternative.
function clearCliches(button) {
  const cliches = JSON.parse(button.dataset.cliches);
  const raw = document.getElementById("raw-markdown");
  cliches.forEach((c) => {
    const alt = c.alternatives.split(",")[0].trim();
    const rx = new RegExp("\\b" + c.word + "\\b", "gi");
    if (raw) raw.value = raw.value.replace(rx, alt);
    document.querySelectorAll("#interactive-content p, #interactive-content li")
      .forEach((el) => { el.innerHTML = el.innerHTML.replace(rx, alt); });
  });
  button.disabled = true;
  button.textContent = "Clichés replaced";
}
```

- [ ] **Step 2: Write `README.md`**

```markdown
# Content Writer AI — Python Edition

SEO competitor analysis, humanized content generation, and Zero-AI detection.
Built with FastAPI, Jinja2, HTMX, Alpine.js, and the Groq API.

## Run locally

**Prerequisites:** Python 3.11+

1. Create and activate a virtual environment:
   `python -m venv .venv` then `.venv\Scripts\activate` (Windows) or
   `source .venv/bin/activate` (macOS/Linux)
2. Install dependencies: `pip install -r requirements.txt`
3. Copy `.env.example` to `.env` and set your `GROQ_API_KEY`
   (free key at https://console.groq.com/keys)
4. Run: `uvicorn app.main:app --reload`
5. Open http://localhost:8000

## Tests

`pytest`

## Project layout

- `app/` — FastAPI app, config, Groq client, heuristics, prompts
- `templates/` — Jinja2 server-rendered UI
- `static/` — client-side helpers
- `tests/` — unit and route tests
```

- [ ] **Step 3: Run the full test suite**

Run: `pytest -v`
Expected: PASS (13 tests across 3 files)

- [ ] **Step 4: Manual smoke test**

Run: `uvicorn app.main:app --reload`
Open http://localhost:8000, fill the form, submit. Verify all four tabs render
and the humanizer drawer works.

- [ ] **Step 5: Commit**

```bash
git add static/app.js README.md
git commit -m "feat: add client helpers and README"
```

---

## Task 10: Publish to GitHub and retire the old repo

**Prerequisite:** `gh auth login` completed. For Step 3, the token needs the
`delete_repo` scope (`gh auth refresh -h github.com -s delete_repo`).

- [ ] **Step 1: Create the new public repo and push**

```bash
gh repo create Content-Writer-AI-Python --public --source=. --remote=origin --push
```

- [ ] **Step 2: Verify the new repo**

Run: `gh repo view Content-Writer-AI-Python --web`
Confirm the code is present and the README renders.

- [ ] **Step 3: Delete the old repo (only after Step 2 confirms success)**

```bash
gh repo delete oaks024/Content-Writer-Ai --yes
```

---

## Self-Review

**Spec coverage:**
- Stack (spec §2) → Task 1 requirements.txt, Tasks 7-8 CDN includes ✓
- Project structure (spec §3) → File Structure table + Tasks 1-9 ✓
- Routes (spec §4) → Task 6 ✓
- Data flow (spec §5) → Task 6 pipeline + Task 8 templates ✓
- Ported logic (spec §6) → Tasks 3-4 ✓
- Four tabs (spec §7) → Task 8 results.html ✓
- Client interactivity (spec §8) → Task 8 drawer + Task 9 app.js ✓
- Error handling (spec §9) → Task 6 `_error`, `_parse_json`; Task 8 error.html ✓
- Config (spec §10) → Tasks 1-2 ✓
- Running/deploy (spec §11) → Task 9 README ✓
- Repo operations (spec §12) → Task 10 ✓

**Placeholder scan:** No TBD/TODO; every code step has complete code. ✓

**Type consistency:** `safe_generate`, `format_groq_error`, `retry_with_backoff`,
`calculate_plagiarism_heuristics`, `keyword_density`, `flag_sentences`,
`overall_ai_score`, `markdown_to_blocks` are used with the same signatures in
Task 6 as defined in Tasks 3-4. The `ai` context dict keys
(`score`, `message`, `perplexity`, `burstiness`, `cliches`, `flagged`) match
between Task 6 and Task 8. ✓

**Note on test ordering:** `tests/test_routes.py` is written in Task 6 but only
passes after Task 8 (templates exist). This is called out explicitly in Task 6
Step 4 and is intentional.
