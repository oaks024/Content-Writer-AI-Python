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
