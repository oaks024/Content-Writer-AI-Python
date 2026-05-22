# Content Writer AI — Python Edition (Design Spec)

**Date:** 2026-05-23
**Status:** Approved
**Author:** brainstorming session

## 1. Goal

Rewrite the existing full-stack "Content Writer AI" app (an SEO competitor
analyzer + humanized content generator + Zero-AI detector) as a single-language
Python application. The current app is a React/Vite/TypeScript frontend with an
Express/TypeScript backend calling the Groq API. The rewrite replaces both with
a Python stack and a server-rendered UI.

The new project ships to a fresh public GitHub repo `Content-Writer-AI-Python`.
The old repo `Content-Writer-Ai` is deleted **only after** the new repo is
pushed and the Python app is confirmed working.

## 2. Stack

| Concern | Choice |
|---|---|
| Web framework | FastAPI |
| ASGI server | Uvicorn |
| AI provider | Groq (official `groq` Python SDK) |
| Templating | Jinja2 |
| Server round-trips | HTMX (via CDN) |
| Client-side UI state | Alpine.js (via CDN) |
| Styling | Tailwind CSS Play CDN |
| Config | `python-dotenv` |

No build step. No Node.js. Python 3.11+ only.

## 3. Project structure

```
Content-Writer-AI-Python/
├── app/
│   ├── __init__.py
│   ├── main.py          # FastAPI app instance + route handlers
│   ├── config.py        # settings, GROQ_API_KEY loading
│   ├── groq_client.py   # Groq client wrapper + model-fallback chain + retry
│   ├── analysis.py      # heuristics: density, perplexity, burstiness, flagging
│   └── prompts.py       # prompt-builder functions
├── templates/
│   ├── base.html        # HTML layout, CDN script/style includes, header
│   ├── index.html       # config panel (left) + empty workspace shell (right)
│   └── partials/
│       ├── results.html   # populated 4-tab workspace (swapped in by HTMX)
│       ├── humanize.html  # single humanized-sentence result fragment
│       └── error.html     # error message fragment
├── static/              # optional small custom css/js (clipboard, download)
├── requirements.txt
├── .env.example
├── .gitignore
├── README.md
└── docs/superpowers/specs/2026-05-23-content-writer-python-rewrite-design.md
```

## 4. Routes

All POST routes consume HTML form data and return **HTML fragments** (HTMX
swaps them into the page) rather than JSON.

| Method | Path | Purpose | Returns |
|---|---|---|---|
| GET | `/` | Render full page: config form + empty workspace | `index.html` |
| GET | `/health` | Liveness + key check | JSON `{status, has_api_key}` |
| POST | `/analyze-and-write` | Run the full Groq pipeline | `partials/results.html` (or `error.html`) |
| POST | `/humanize-sentence` | Rewrite one sentence | `partials/humanize.html` (or `error.html`) |

## 5. Data flow

1. User fills the config form (company name, content type, page title, primary
   / secondary / LSI keywords, tone, audience, target word count, target
   density).
2. The "Analyze & Write" button issues `hx-post="/analyze-and-write"` with
   `hx-target="#workspace"` and an `hx-indicator` loading state.
3. Server pipeline:
   a. Parse and split keyword strings.
   b. Call Groq for a grounded competitive-search summary (best-effort; on
      failure, fall back to an internal summary string).
   c. Call Groq with the large JSON-builder prompt; request a JSON object
      response.
   d. Parse the JSON safely (with a markdown-fence cleanup retry).
   e. Compute the keyword-density table over the generated markdown.
   f. Compute plagiarism heuristics (perplexity, burstiness, clichés).
   g. Build the merged flagged-sentence list and the overall AI-detection
      result.
   h. Render `results.html` with all four tabs populated.
4. `results.html` renders the four tabs; Alpine.js (`x-data`) controls the
   active tab, the humanizer drawer, and the raw/interactive editor toggle.
5. Clicking a flagged sentence span opens the Alpine drawer; its "Humanize"
   button issues `hx-post="/humanize-sentence"`.
6. Copy and download use a small amount of JavaScript (clipboard API + Blob
   download).

## 6. Logic ported 1:1 from `server.ts`

These are pure functions that translate directly to Python:

- **Model-fallback chain** — try `llama-3.3-70b-versatile`, then
  `mixtral-8x7b-32768`, then `llama-3.1-8b-instant`. Auth/invalid-key errors
  short-circuit instead of falling through.
- **Retry with exponential backoff** — 4 retries, 1500 ms base delay, doubling,
  triggered by rate-limit / 429 / quota errors.
- **`calculate_plagiarism_heuristics`** — cliché word list with alternatives;
  burstiness from sentence-length standard deviation; perplexity from
  type-token ratio and sentence-start diversity.
- **Keyword-density table** — per-keyword count, density %, and
  Under-optimized / Perfect / Over-stuffed status relative to the target.
- **Sentence flagging** — merge model-flagged sentences with heuristic checks
  (long sentences with parentheticals or clichés).
- **Overall AI score** — weighted average of flagged-sentence scores, cliché
  penalty, and inverse burstiness/perplexity, capped at 99.
- **Groq error formatting** — translate API errors into user-friendly messages,
  with special handling for quota / 429.

## 7. Feature parity — the four tabs

`results.html` reproduces all four tabs of the current app:

1. **Writing Room** — SEO metadata cards (slug, meta description, Google News
   heading, unique angle); the generated copy in either an interactive
   sentence view or a raw-markdown textarea; keyword-density tracker; structural
   outline.
2. **Competitors & Gaps** — three competitor cards + the gaps opportunity table.
3. **Zero AI Analytics** — AI-probability gauge, perplexity and burstiness
   cards, cliché finder, flagged-sentence list.
4. **Google SEO Audit** — the helpful-content audit checklist.

## 8. Client-side interactivity (most complex piece)

Two interactions in the current React app mutate generated content without
re-calling the AI. These are reproduced **client-side with Alpine.js** so they
stay instant and free:

- **Humanize a sentence** — the drawer's result fragment comes from the server
  (`/humanize-sentence`); applying it does a client-side string replace in the
  rendered markdown held in Alpine state.
- **Replace all clichés** — client-side regex replacement over the Alpine-held
  markdown, using the first suggested alternative for each cliché.

This is the area most likely to differ subtly from the React original; it is
called out explicitly so reviewers check it closely.

## 9. Error handling

- Missing `GROQ_API_KEY` — `/health` reports `has_api_key: false`; the page
  shows a warning banner; POST routes return `error.html` with a clear message.
- Groq API failure after the full fallback chain — return `error.html` with the
  formatted error (quota/429 messaged specially).
- Malformed JSON from the model — one cleanup retry (strip markdown fences),
  then a friendly "try simpler keywords" error.
- Network/transient errors — covered by retry-with-backoff.

## 10. Configuration

- `.env` with `GROQ_API_KEY` (loaded via `python-dotenv`).
- `.env.example` documents the key and links to `console.groq.com/keys`.
- `.gitignore` excludes `.env`, `__pycache__/`, `.venv/`.

## 11. Running and deployment

- Local: `pip install -r requirements.txt` then
  `uvicorn app.main:app --reload`.
- Deployable to any Python host (Render, Railway, Fly, Vercel Python runtime).
- Single required env var: `GROQ_API_KEY`.

## 12. Repo operations

1. Create new **public** GitHub repo `Content-Writer-AI-Python` under the user's
   account.
2. Commit and push the Python project.
3. After the new repo is pushed and the app is confirmed working, **permanently
   delete** the old `Content-Writer-Ai` repo (user explicitly confirmed).

Both operations require `gh` CLI authentication; the deletion additionally
requires the `delete_repo` scope.

## 13. Known constraints / out of scope

- **Python is not installed** on the development machine (only the Microsoft
  Store stub). All code can be written, but it cannot be executed or verified
  locally until Python 3.11+ is installed.
- **`gh` CLI is not authenticated.** Repo creation and deletion are blocked
  until the user runs `gh auth login`.
- No database, no authentication, no user accounts — the app is stateless, the
  same as the current version.
- The Microsoft AI Studio deployment of the old app is not migrated or touched;
  it is being abandoned in favor of this fresh repo.
- Automated tests: unit tests for the pure logic in `analysis.py` and
  `groq_client.py` (heuristics, density, fallback selection). The Groq API
  calls themselves are not integration-tested in CI.
