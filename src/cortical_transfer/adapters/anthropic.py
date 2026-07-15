"""Anthropic adapter — stub for v0.1.

The OpenAI-compatible adapter does not cover the Anthropic Messages API shape;
a native adapter is planned. Until then this stub fails loudly.
"""

from __future__ import annotations


class AnthropicAdapter:
    name = "anthropic"

    def complete(self, prompt: str, system: str | None = None, json_mode: bool = False) -> str:
        raise NotImplementedError(
            "Anthropic adapter is a v0.1 stub. Use CT_ADAPTER=openai with an "
            "OpenAI-compatible gateway, or CT_ADAPTER=ollama for local models."
        )
