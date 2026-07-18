"""Transfer-fidelity eval: quiz a model on the injected memory block.

The ds4-eval idea applied to memory portability: a curated question set with
expected-substring answers, run end to end (extract -> inject -> recall).
Output is one number — "recall N/M @ budget B" — fit for a README table and
for catching regressions in extract/inject.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import TypedDict

from cortical_transfer.adapters.base import Adapter
from cortical_transfer.inject import build_context
from cortical_transfer.schema import MemPack

SYSTEM_SUFFIX = (
    "\nAnswer the question using ONLY the user memory above. "
    "Reply in one short sentence."
)

# ponytail: deterministic substring judge, no LLM-as-judge. Works for the
# fact-shaped answers memory recall produces; revisit if questions get open-ended.
_THINK = re.compile(r"<think>.*?</think>", re.DOTALL)


class Question(TypedDict):
    question: str
    expected: list[str]  # pass if ANY appears in the answer (case-insensitive)


class Result(TypedDict):
    question: str
    answer: str
    passed: bool


def load_questions(path: Path) -> list[Question]:
    data: list[Question] = json.loads(path.read_text(encoding="utf-8"))
    return data


def hit(answer: str, expected: list[str]) -> bool:
    a = _THINK.sub("", answer).lower()  # don't score reasoning traces
    return any(e.lower() in a for e in expected)


def run_eval(
    pack: MemPack,
    questions: list[Question],
    adapter: Adapter,
    budget_tokens: int = 2000,
) -> list[Result]:
    context = build_context(pack, budget_tokens=budget_tokens)
    results: list[Result] = []
    for q in questions:
        ans = adapter.complete(q["question"], system=context + SYSTEM_SUFFIX)
        results.append(
            {"question": q["question"], "answer": ans, "passed": hit(ans, q["expected"])}
        )
    return results
