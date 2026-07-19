from __future__ import annotations

from typing import Protocol

from .schema import build_system_prompt

_MAX_OUTPUT_TOKENS = 1024


class LLMError(Exception):
    """Raised when SQL generation fails (empty response, provider error, etc.)."""

class Provider(Protocol):
    def generate_sql(self, question: str, department: str) -> str:
        """Return raw SQL (fences stripped) for `question`, scoped to `department`."""
        ...

class OpenAIProvider:
    def __init__(self, api_key: str, model: str, base_url: str | None = None):
        self._api_key = api_key
        self._model = model
        self._base_url = base_url

    def generate_sql(self, question: str, department: str) -> str:
        from openai import OpenAI  # only needed for this provider

        client = OpenAI(api_key=self._api_key, base_url=self._base_url)
        try:
            response = client.chat.completions.create(
                model=self._model,
                messages=[
                    {"role": "system", "content": build_system_prompt(department)},
                    {"role": "user", "content": question},
                ],
            )
        except Exception as e:
            raise LLMError(f"OpenAI request failed: {e}") from e

        content = response.choices[0].message.content
        return _require_sql(content)


class AnthropicProvider:
    def __init__(self, api_key: str, model: str, base_url: str | None = None):
        self._api_key = api_key
        self._model = model
        self._base_url = base_url

    def generate_sql(self, question: str, department: str) -> str:
        import anthropic  # only needed for this provider

        client = anthropic.Anthropic(api_key=self._api_key, base_url=self._base_url)
        try:
            response = client.messages.create(
                model=self._model,
                max_tokens=_MAX_OUTPUT_TOKENS,
                thinking={"type": "disabled"},
                system=build_system_prompt(department),
                messages=[{"role": "user", "content": question}],
            )
        except Exception as e:
            raise LLMError(f"Anthropic request failed: {e}") from e

        text = "".join(
            block.text for block in response.content if getattr(block, "type", None) == "text"
        )
        return _require_sql(text)


def make_provider(
    provider: str, api_key: str, model: str, base_url: str | None = None
) -> Provider:
    if provider == "openai":
        return OpenAIProvider(api_key=api_key, model=model, base_url=base_url)
    if provider == "anthropic":
        return AnthropicProvider(api_key=api_key, model=model, base_url=base_url)
    raise LLMError(f"Unknown provider: {provider!r}")


def _strip_sql_fences(text: str) -> str:
    stripped = text.strip()
    if not stripped.startswith("```"):
        return stripped

    lines = stripped.splitlines()
    lines = lines[1:]

    if lines and lines[-1].strip().startswith("```"):
        lines = lines[:-1]
    return "\n".join(lines).strip()


def _require_sql(content: str | None) -> str:
    if content is None:
        raise LLMError("Model returned an empty response")
    sql = _strip_sql_fences(content)
    if not sql:
        raise LLMError("Model returned an empty response")
    return sql