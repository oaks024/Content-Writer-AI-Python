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
