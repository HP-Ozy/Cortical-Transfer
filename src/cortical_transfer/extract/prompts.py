"""Extraction prompts. Versioned constants — bump the suffix, never edit in place."""

PROMPT_VERSION = "v2"

SYSTEM_V1 = (
    "You extract long-term memory about the USER from a chat transcript. "
    "Output strict JSON only, no prose, no markdown fences."
)

EXTRACT_NODES_V1 = """\
From the conversation below, extract memory about the user in JSON:

{{"identity": [...], "episodes": [...], "threads": [...]}}

- identity: stable facts about the user (profession, preferences, environment, languages).
- episodes: salient events or decisions from this conversation.
- threads: topics left open or unresolved.

Each item: {{"text": "<one self-contained sentence>", "granularity": "summary"|"episode"|"detail",
"salience": <0.0-1.0>, "tags": ["..."]}}.
Extract only what the conversation supports. Empty lists are fine.

CONVERSATION (id={conversation_id}):
{transcript}
"""

EXTRACT_NODES_V2 = """\
From the conversation below, extract memory about the user in JSON:

{{"identity": [...], "episodes": [...], "threads": [...]}}

- identity: stable facts about the user (profession, preferences, environment, languages).
- episodes: salient events or decisions from this conversation.
- threads: topics left open or unresolved.

Each item: {{"text": "<one self-contained sentence>", "granularity": "summary"|"episode"|"detail",
"salience": <0.0-1.0>, "tags": ["..."],
"valid_from": "YYYY-MM-DD"|null, "valid_until": "YYYY-MM-DD"|null}}.

Quality rules:
- Each text stands alone: name its subject explicitly, no pronouns that need
  the conversation to be resolved.
- Keep concrete details exactly as stated (names, numbers, versions, titles);
  never generalize them.
- If the assistant merely repeats what the user said, extract it once.
- Extract only what the conversation supports — no outside knowledge, no guesses.

Temporal rules (this conversation happened on: {conversation_date}):
- valid_from / valid_until = when the fact is true in the real world.
- Resolve relative expressions ("yesterday", "until March") against the
  conversation date above, never against today.
- If the text states no explicit time, set both to null. Do not infer dates
  from unrelated events.

CONVERSATION (id={conversation_id}):
{transcript}
"""

RESOLVE_V1 = """\
Below is a numbered list of memory statements about one user.

Return JSON: {{"duplicates": [[keep, drop], ...], "contradictions": [[older, newer], ...]}}

- duplicates: pairs where two statements say the same thing (keep the better-phrased index).
- contradictions: pairs where the statements cannot both be true now; `newer` is the one
  that appears currently true.
- Indices refer to the list below. No pair may appear in both lists. Empty lists are fine.

STATEMENTS:
{numbered}
"""

RESOLVE_V2 = """\
Below is a numbered list of memory statements about one user.

Return JSON: {{"duplicates": [[keep, drop], ...], "contradictions": [[older, newer], ...]}}

- duplicates: pairs where two statements say the same thing (keep the better-phrased index).
- contradictions: pairs where the statements cannot both be true now; `newer` is the one
  that appears currently true. A statement giving a different current value for the
  same fact (job, tool, city, plan) is a contradiction, NOT a duplicate.
- Indices refer to the list below. No pair may appear in both lists. Empty lists are fine.

STATEMENTS:
{numbered}
"""

MERGE_V1 = """\
Below are EXISTING memory statements about one user, and NEW candidate statements
from a recent conversation.

Return JSON: {{"duplicates": [[existing, new], ...], "contradictions": [[existing, new], ...]}}

- duplicates: the NEW statement repeats an EXISTING one (same fact, possibly more detail).
- contradictions: the NEW statement gives a different current value for the same fact
  (job, tool, city, plan...) so the EXISTING one is no longer true. NOT a duplicate.
- A NEW statement about a fact not covered by any EXISTING one belongs in neither list.
- Indices refer to the two numbered lists. Empty lists are fine.

EXISTING:
{existing}

NEW:
{new}
"""

HIERARCHY_V1 = """\
Below is a numbered list of episode memories about one user. Group related episodes
under short summary headlines.

Return JSON: {{"groups": [{{"summary": "<one sentence>", "members": [<indices>]}}, ...]}}

Only group episodes that clearly belong together; leave loners out. Empty list is fine.

EPISODES:
{numbered}
"""

STYLE_V1 = """\
From the user messages below, write a short interaction style card in Markdown
(under 250 words): tone, formality, verbosity, languages used, recurring references,
how the user likes to be addressed. Describe the USER's style, do not give instructions.

USER MESSAGES:
{messages}
"""
