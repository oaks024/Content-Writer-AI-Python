"""Groq API wrapper: client creation, model fallback, retry, error formatting."""
import logging
import time

from groq import Groq

from app import config

logger = logging.getLogger("content_writer")

# Fallback chain of currently-active Groq models, best first.
MODELS: list[str] = [
    "llama-3.3-70b-versatile",
    "llama-3.1-8b-instant",
    "gemma2-9b-it",
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
                  temperature: float | None = None,
                  max_tokens: int | None = None) -> str:
    """Run a completion against the model-fallback chain. Returns the text.

    Raises the last error if every model fails. Auth errors short-circuit.
    Logs the finishing reason so truncated responses are visible.
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
            if max_tokens is not None:
                options["max_tokens"] = max_tokens
            if json_mode:
                options["response_format"] = {"type": "json_object"}

            response = retry_with_backoff(
                lambda opts=options: client.chat.completions.create(**opts)
            )
            choice = response.choices[0]
            content = choice.message.content or ""
            finish = getattr(choice, "finish_reason", None)
            logger.info("Groq model=%s finish_reason=%s chars=%d",
                        model, finish, len(content))
            if finish == "length":
                logger.warning(
                    "Groq output for model=%s hit the token limit; "
                    "increase max_tokens.", model)
            return content
        except Exception as error:  # noqa: BLE001
            last_error = error
            if any(m in str(error).lower() for m in _AUTH_MARKERS):
                raise
            continue

    raise last_error if last_error else RuntimeError("All Groq models failed.")
