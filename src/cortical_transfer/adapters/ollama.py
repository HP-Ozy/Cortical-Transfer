"""Local Ollama adapter (default)."""

from __future__ import annotations

import os

from cortical_transfer.adapters.base import logged_call, post_json


class OllamaAdapter:
    name = "ollama"

    def __init__(self) -> None:
        self.base_url = os.environ.get("CT_BASE_URL", "http://localhost:11434")
        self.model = os.environ.get("CT_MODEL", "llama3.1:8b")

    def complete(self, prompt: str, system: str | None = None, json_mode: bool = False) -> str:
        payload: dict[str, object] = {
            "model": self.model,
            "prompt": prompt,
            "stream": False,
            "options": {"temperature": 0},
        }
        if system:
            payload["system"] = system
        if json_mode:
            payload["format"] = "json"

        def call() -> str:
            return str(post_json(f"{self.base_url}/api/generate", payload, {})["response"])

        return logged_call(self.name, self.model, prompt, call)
