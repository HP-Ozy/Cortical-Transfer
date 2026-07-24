"""LoCoMo -> ct benchmark inputs, for the README "cross-model transport" table.

Downloads the LoCoMo dataset (snap-research/locomo, MIT-licensed research data)
next to this file, picks the sample with the most judgeable QA, and writes:

  locomo_history.jsonl      12 sessions as separate conversations (ct extract input)
  locomo_questions.raw.json QA with verbatim answers (category-mapped)

The shipped `locomo_questions.json` is the raw file with expected answers
hand-reduced to discriminative keywords — the substring judge can't match
verbatim phrase answers. Re-curate by hand if you regenerate.

Full run (writer x reader matrix, one cell):

  CT_MODEL=<writer> ct extract locomo_history.jsonl -p locomo-bench
  CT_MODEL=<reader> ct eval locomo_questions.json -p locomo-bench --budget 4000
"""

import json
import urllib.request
from datetime import datetime
from pathlib import Path

HERE = Path(__file__).parent
DATA = HERE / "locomo10.json"
URL = "https://raw.githubusercontent.com/snap-research/locomo/main/data/locomo10.json"
MAX_SESSIONS = 12
PER_CAT = 15  # questions per category cap
CAT = {4: "single-hop", 1: "multi-hop", 2: "temporal"}  # 5 (adversarial) needs an LLM judge


def session_ts(raw):
    # "1:56 pm on 8 May, 2023" -> ISO; None if the format drifts
    try:
        return datetime.strptime(raw, "%I:%M %p on %d %B, %Y").isoformat()
    except (ValueError, TypeError):
        return None


def sessions_of(conv):
    n = 1
    while f"session_{n}" in conv and n <= MAX_SESSIONS:
        yield n, conv[f"session_{n}"], session_ts(conv.get(f"session_{n}_date_time"))
        n += 1


def eligible_qa(sample):
    conv = sample["conversation"]
    a, b = conv["speaker_a"], conv["speaker_b"]
    max_s = sum(1 for _ in sessions_of(conv))
    out = []
    for q in sample["qa"]:
        if q.get("category") not in CAT:
            continue
        text = q["question"]
        # ct extracts USER memory; speaker_a plays the user, so keep only
        # questions purely about speaker_a
        if a.lower() not in text.lower() or b.lower() in text.lower():
            continue
        ev = q.get("evidence") or []
        try:
            if not ev or any(int(e.split(":")[0][1:]) > max_s for e in ev):
                continue  # answer must lie inside the ingested sessions
        except (ValueError, IndexError):
            continue
        out.append(q)
    return out


def main():
    if not DATA.exists():
        print(f"downloading {URL} ...")
        urllib.request.urlretrieve(URL, DATA)  # noqa: S310
    data = json.loads(DATA.read_text(encoding="utf-8"))
    sample = max(data, key=lambda s: len(eligible_qa(s)))
    conv = sample["conversation"]
    a = conv["speaker_a"]

    lines = []
    for n, turns, ts in sessions_of(conv):
        for t in turns:
            content = t.get("text") or ""
            if t.get("blip_caption"):
                content = f"{content} [shares a photo: {t['blip_caption']}]".strip()
            if not content:
                continue
            lines.append(
                json.dumps(
                    {
                        "role": "user" if t["speaker"] == a else "assistant",
                        "content": f"{t['speaker']}: {content}",
                        "timestamp": ts,
                        "conversation_id": f"locomo-s{n:02d}",
                        "turn_id": t["dia_id"],
                    },
                    ensure_ascii=False,
                )
            )
    (HERE / "locomo_history.jsonl").write_text("\n".join(lines), encoding="utf-8")

    per_cat = {}
    questions = []
    for q in eligible_qa(sample):
        cat = CAT[q["category"]]
        if per_cat.get(cat, 0) >= PER_CAT:
            continue
        per_cat[cat] = per_cat.get(cat, 0) + 1
        questions.append(
            {
                "question": q["question"],
                "expected": [str(q["answer"])],
                "category": cat,
            }
        )
    (HERE / "locomo_questions.raw.json").write_text(
        json.dumps(questions, indent=1, ensure_ascii=False), encoding="utf-8"
    )

    print(
        f"speaker_a={a}  sessions={sum(1 for _ in sessions_of(conv))}  "
        f"turns={len(lines)}  questions={per_cat}"
    )


if __name__ == "__main__":
    main()
