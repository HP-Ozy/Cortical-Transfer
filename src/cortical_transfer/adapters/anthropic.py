"""Anthropic Messages API adapter (stdlib HTTP, per ADR 0003)."""

from __future__ import annotations

import os

from cortical_transfer.adapters.base import logged_call, post_json


class AnthropicAdapter:
    name = "anthropic"

    def __init__(self) -> None:
        self.base_url = os.environ.get("CT_BASE_URL", "https://api.anthropic.com").rstrip("/")
        self.model = os.environ.get("CT_MODEL", "claude-opus-4-8")
        self.api_key = os.environ.get("CT_API_KEY", "")

    def complete(self, prompt: str, system: str | None = None, json_mode: bool = False) -> str:
        if json_mode:
            # ponytail: Messages API has no response_format; prompt-level is enough here
            prompt += "\nRespond with valid JSON only, no markdown fences."
        payload: dict[str, object] = {
            "model": self.model,
            "max_tokens": 2048,
            "messages": [{"role": "user", "content": prompt}],
        }
        if system:
            payload["system"] = system
        headers = {"x-api-key": self.api_key, "anthropic-version": "2023-06-01"}

        def call() -> str:
            out = post_json(f"{self.base_url}/v1/messages", payload, headers)
            blocks = out["content"]
            return "".join(b["text"] for b in blocks if b["type"] == "text")

        return logged_call(self.name, self.model, prompt, call)
