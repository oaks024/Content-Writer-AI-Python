"""Prompt builders for the Groq calls. Ported in intent from server.ts."""


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


def article_prompt(*, page_title: str, company: str, content_type: str,
                   primary: list[str], secondary: list[str], lsi: list[str],
                   tone: str, audience: str, word_count: int,
                   density: float, search_summary: str) -> str:
    """Dedicated prompt that produces ONLY the long-form Markdown article.

    Isolating the article in its own call is what makes the model write the
    full requested length instead of abbreviating it inside a large JSON.
    """
    strategy = ("an in-depth, value-driven blog post" if content_type == "blog"
                else "high-converting website page copy")
    faq_rule = (
        "- End with exactly 5 FAQs under an H2 'Frequently Asked Questions'; "
        "each answer must be 30-40 words.\n"
        if content_type == "blog" else "")
    return f'''Write {strategy} of AT LEAST {word_count} words on the topic below.
This length is a HARD REQUIREMENT. The finished article MUST reach at least
{word_count} words. Do not stop early. Do not write an outline or a summary —
write the entire, fully developed article.

TOPIC / TITLE GOAL: "{page_title}"
COMPANY / BRAND: "{company or "the client"}"
PRIMARY KEYWORDS: {", ".join(primary) or "(none)"}
SECONDARY KEYWORDS: {", ".join(secondary) or "(none)"}
LSI KEYWORDS: {", ".join(lsi) or "(none)"}
TONE: {tone or "professional, clear, human"}
AUDIENCE: {audience or "general readers"}
PRIMARY KEYWORD DENSITY: about {density}% — natural, never stuffed.

COMPETITIVE INSIGHTS TO BEAT:
{search_summary}

REQUIREMENTS:
- Output ONLY the article as clean Markdown. No preamble, no JSON, no commentary.
- Start with one H1 title, then use H2 and H3 subheadings throughout.
- Put the primary keyword in the H1, the introduction, at least one H2, and
  the conclusion.
- Short sentences, plain words, active voice, concise paragraphs.
- Develop every section fully with specific, useful detail and examples.
- Never use these AI-cliche words: delve, embark, navigate, dive, tapestry,
  pivotal, demystify, furthermore, moreover, crucial, elevate.
{faq_rule}Write the complete article now. Minimum {word_count} words.'''


def analysis_prompt(*, page_title: str, company: str, primary: list[str],
                    secondary: list[str], lsi: list[str], article: str,
                    search_summary: str) -> str:
    """Prompt that analyzes an already-written article into a compact JSON.

    Carries no long-form content, so this JSON is small and reliable.
    """
    return f'''You are an SEO analyst. A finished article is provided below.
Analyze it and its competitive landscape.

TOPIC: "{page_title}"
COMPANY: "{company or "the client"}"
PRIMARY KEYWORDS: {", ".join(primary) or "(none)"}
SECONDARY KEYWORDS: {", ".join(secondary) or "(none)"}
LSI KEYWORDS: {", ".join(lsi) or "(none)"}

COMPETITIVE INSIGHTS:
{search_summary}

THE ARTICLE:
"""
{article}
"""

Return a SINGLE valid JSON object, no markdown fences, with exactly these keys:
{{
  "competitors": [
    3 objects: {{"name": "", "url": "", "wordCount": 1100,
      "structuralPattern": "", "strengths": [], "weaknesses": []}}
  ],
  "gaps": [
    3 objects: {{"title": "", "description": "",
      "importance": "High|Medium|Low", "recommendedSubheadings": []}}
  ],
  "seo": {{
    "title": "click-worthy SEO title for THE ARTICLE",
    "slug": "lowercase-hyphenated-url-slug",
    "metaDescription": "compelling meta description under 160 chars",
    "googleNewsHeading": "news-style headline",
    "uniqueAngleAdded": "one sentence on what makes this article different"
  }},
  "flaggedSentences": [
    up to 3 objects, each "text" an EXACT sentence copied from THE ARTICLE:
    {{"text": "", "score": 70, "category": "robotic|warning",
      "reason": "", "suggestions": []}}
  ],
  "auditRecommendations": [
    exactly 5 objects: {{"id": "", "criteria": "", "status": "pass|warn",
      "description": "", "guideline": ""}}
  ]
}}'''
