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
        cleaned = (text.removeprefix("```json").removeprefix("```")
                   .removesuffix("```").strip())
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
