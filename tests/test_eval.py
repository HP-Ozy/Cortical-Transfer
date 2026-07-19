from cortical_transfer.eval import Question, Result, by_category, hit, run_eval
from cortical_transfer.schema import MemPack, SemanticNode


class FakeAdapter:
    name = "fake"
    answers = {
        "What is the user's first name?": "The user's name is Dana.",
        "Which orchestrator?": "<think>maybe Airflow? no, Prefect</think>I don't know.",
    }

    def complete(self, prompt: str, system: str | None = None, json_mode: bool = False) -> str:
        assert system and "BEGIN USER MEMORY" in system  # context actually injected
        return self.answers[prompt]


def test_hit_is_case_insensitive_any_of() -> None:
    assert hit("Archived to Backblaze B2.", ["b2", "backblaze"])
    assert not hit("Archived to S3.", ["b2", "backblaze"])


def test_hit_ignores_think_traces() -> None:
    assert not hit("<think>Prefect Prefect Prefect</think>No idea.", ["prefect"])


def test_run_eval_counts() -> None:
    pack = MemPack(identity=[SemanticNode(text="Name: Dana", salience=0.9)])
    questions: list[Question] = [
        {"question": "What is the user's first name?", "expected": ["dana"]},
        {"question": "Which orchestrator?", "expected": ["prefect"]},
    ]
    results = run_eval(pack, questions, FakeAdapter(), budget_tokens=500)
    assert [r["passed"] for r in results] == [True, False]


def test_by_category_breakdown() -> None:
    results: list[Result] = [
        {"question": "a", "answer": "", "passed": True, "category": "temporal"},
        {"question": "b", "answer": "", "passed": False, "category": "temporal"},
        {"question": "c", "answer": "", "passed": True, "category": ""},
    ]
    assert by_category(results) == {"temporal": (1, 2)}
