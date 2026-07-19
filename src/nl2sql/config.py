from __future__ import annotations

import os
from dataclasses import dataclass

from dotenv import load_dotenv

_VALID_PROVIDERS = ("openai", "anthropic")

# Env var holding the API key, per provider.
_API_KEY_VAR = {
    "openai": "OPENAI_API_KEY",
    "anthropic": "ANTHROPIC_API_KEY",
}

# Env var holding the optional base URL, per provider.
_BASE_URL_VAR = {
    "openai": "OPENAI_BASE_URL",
    "anthropic": "ANTHROPIC_BASE_URL",
}

# Default model, per provider.
_DEFAULT_MODEL = {
    "openai": "gpt-4o",
    "anthropic": "claude-sonnet-5",
}

_DEFAULT_DB_PATH = "employees.db"

SENSITIVE_COLUMNS = frozenset({"SalaryAmount", "YearlyBonusAmount", "RemainingBalance"})

_TRUE_VALUES = {"1", "true", "yes", "on"}


@dataclass(frozen=True)
class Config:
    provider: str
    api_key: str
    model: str
    db_path: str
    base_url: str | None
    mask_sensitive: bool


def load_config() -> Config:
    """Read and validate configuration from the environment (and a .env file)."""
    load_dotenv()

    provider = os.getenv("NL2SQL_PROVIDER", "openai").strip().lower()
    if provider not in _VALID_PROVIDERS:
        raise RuntimeError(
            f"Unknown NL2SQL_PROVIDER {provider!r}; "
            f"expected one of {', '.join(_VALID_PROVIDERS)}"
        )

    key_var = _API_KEY_VAR[provider]
    api_key = os.getenv(key_var)
    if not api_key:
        raise RuntimeError(f"Missing {key_var} for provider {provider!r}")

    model = os.getenv("NL2SQL_MODEL") or _DEFAULT_MODEL[provider]
    db_path = os.getenv("NL2SQL_DB_PATH") or _DEFAULT_DB_PATH
    base_url = os.getenv(_BASE_URL_VAR[provider]) or None
    mask_sensitive = os.getenv("NL2SQL_MASK_SENSITIVE", "").strip().lower() in _TRUE_VALUES

    return Config(
        provider=provider,
        api_key=api_key,
        model=model,
        db_path=db_path,
        base_url=base_url,
        mask_sensitive=mask_sensitive,
    )