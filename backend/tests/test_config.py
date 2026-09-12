"""Settings parsing."""

from app.core.config import Settings


def test_blank_api_keys_count_as_unset(monkeypatch):
    # Docker Compose passes unset variables through as empty strings
    monkeypatch.setenv("GEMINI_API_KEY", "")
    monkeypatch.setenv("CEREBRAS_API_KEY", "  ")
    monkeypatch.setenv("GROQ_API_KEY", "gsk_example")
    settings = Settings(_env_file=None)
    assert settings.gemini_api_key is None
    assert settings.cerebras_api_key is None
    assert settings.groq_api_key is not None


def test_blank_gemini_allow_list_still_means_no_tenants(monkeypatch):
    monkeypatch.setenv("GEMINI_ALLOWED_TENANTS", "")
    assert Settings(_env_file=None).gemini_allowed_tenants == ""
