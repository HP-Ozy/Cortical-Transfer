"""OpenAI-compatible chat/completions adapter (covers most hosted and local vendors)."""

from __future__ import annotations

import os

from cortical_transfer.adapters.base import logged_call, post_json


class OpenAICompatAdapter:
    name = "openai"

    def __init__(self) -> None:
        self.base_url = os.environ.get("CT_BASE_URL", "https://api.openai.com/v1").rstrip("/")
        self.model = os.environ.get("CT_MODEL", "gpt-4o-mini")
        self.api_key = os.environ.get("CT_API_KEY", "")

    def complete(self, prompt: str, system: str | None = None, json_mode: bool = False) -> str:
        messages = ([{"role": "system", "content": system}] if system else []) + [
            {"role": "user", "content": prompt}
        ]
        payload: dict[str, object] = {"model": self.model, "messages": messages, "temperature": 0}
        if json_mode:
            payload["response_format"] = {"type": "json_object"}
        headers = {"Authorization": f"Bearer {self.api_key}"} if self.api_key else {}

        def call() -> str:
            out = post_json(f"{self.base_url}/chat/completions", payload, headers)
            return str(out["choices"][0]["message"]["content"])

        return logged_call(self.name, self.model, prompt, call)
