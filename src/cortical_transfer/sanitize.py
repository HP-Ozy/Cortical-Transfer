"""Injection-safety filters. Node text and style cards are DATA (SPEC §6);
anything that looks like an instruction, role marker, or tool call is neutralized."""

from __future__ import annotations

import re

from cortical_transfer.schema import MemPack

NEUTRALIZED = "[neutralized]"

_PATTERNS = [
    # instruction-override phrasing
    r"(?i)\b(ignore|disregard|forget|override)\s+(all\s+|any\s+)?"
    r"(previous|prior|above|earlier|preceding|system)\s+(instructions?|prompts?|context|rules?)",
    r"(?i)\bnew\s+(system\s+)?instructions?\s*:",
    r"(?i)\byou\s+(are|must)\s+now\b.{0,40}?(act|behave|respond)\s+as\b",
    # chat-template role markers
    r"(?i)<\|[a-z_]+\|>",  # <|im_start|>, <|system|>, <|endoftext|>, ...
    r"\[/?INST\]|<<\/?SYS>>",
    r"(?im)^\s*#{0,4}\s*(system|assistant|developer|tool)\s*:",
    # tool-call / function-call syntax
    r"(?i)</?\s*(tool_call|tool_use|function_call|antml:invoke|invoke|tool)\b[^>]*>",
    r'(?i)"(tool_calls|function_call)"\s*:',
]

_RX = [re.compile(p) for p in _PATTERNS]


def sanitize_text(text: str) -> str:
    for rx in _RX:
        text = rx.sub(NEUTRALIZED, text)
    return text


def sanitize_pack(pack: MemPack) -> MemPack:
    """In-place neutralization of every text field that reaches a prompt."""
    for node in pack.all_nodes():
        node.text = sanitize_text(node.text)
    pack.style = sanitize_text(pack.style)
    return pack
