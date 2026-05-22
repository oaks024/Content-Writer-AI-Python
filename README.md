# Content Writer AI — Python Edition

SEO competitor analysis, humanized content generation, and Zero-AI detection.
Built with FastAPI, Jinja2, HTMX, Alpine.js, and the Groq API.

## Run locally

**Prerequisites:** Python 3.11+

1. Create and activate a virtual environment:
   - `python -m venv .venv`
   - Windows: `.venv\Scripts\activate`
   - macOS/Linux: `source .venv/bin/activate`
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

## How it works

1. You enter a page title, keywords, tone, audience, and density targets.
2. The server asks Groq for a competitive-landscape summary, then for a full
   structured result (competitors, content gaps, humanized copy, SEO metadata).
3. Pure-Python heuristics compute keyword density, perplexity, burstiness,
   cliché detection, and an overall AI-likeness score.
4. Results render across four tabs: Writing Room, Competitors & Gaps,
   Zero AI Analytics, and SEO Audit.
5. Click any flagged sentence to rewrite it, or replace all clichés at once.

## Tech notes

- No build step — HTMX, Alpine.js, and Tailwind load from CDNs.
- Stateless — no database, no accounts.
- Groq calls use a model-fallback chain
  (`llama-3.3-70b-versatile` → `mixtral-8x7b-32768` → `llama-3.1-8b-instant`)
  with exponential-backoff retry on rate limits.
