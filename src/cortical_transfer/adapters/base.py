"""Provider-agnostic LLM adapter layer. Every call is logged."""

from __future__ import annotations

import json
import logging
import os
import time
import urllib.request
from typing import Any, Protocol

log = logging.getLogger("cortical_transfer.llm")


class Adapter(Protocol):
    name: str

    def complete(self, prompt: str, system: str | None = None, json_mode: bool = False) -> str:
        """Single-turn completion. json_mode requests strict-JSON output where supported."""
        ...


def post_json(url: str, payload: dict[str, Any], headers: dict[str, str]) -> dict[str, Any]:
    req = urllib.request.Request(
        url,
        data=json.dumps(payload).encode(),
        headers={"Content-Type": "application/json", **headers},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=600) as resp:  # noqa: S310
        return dict(json.loads(resp.read()))


def logged_call(adapter_name: str, model: str, prompt: str, fn: Any) -> str:
    t0 = time.monotonic()
    out: str = fn()
    log.info(
        "llm call adapter=%s model=%s prompt_chars=%d response_chars=%d elapsed=%.1fs",
        adapter_name, model, len(prompt), len(out), time.monotonic() - t0,
    )
    return out


def get_adapter() -> Adapter:
    """Adapter from env: CT_ADAPTER = ollama (default) | openai | anthropic."""
    kind = os.environ.get("CT_ADAPTER", "ollama")
    if kind == "ollama":
        from cortical_transfer.adapters.ollama import OllamaAdapter

        return OllamaAdapter()
    if kind == "openai":
        from cortical_transfer.adapters.openai_compat import OpenAICompatAdapter

        return OpenAICompatAdapter()
    if kind == "anthropic":
        from cortical_transfer.adapters.anthropic import AnthropicAdapter

        return AnthropicAdapter()
    raise ValueError(f"unknown CT_ADAPTER: {kind}")
