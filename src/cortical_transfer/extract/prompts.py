"""Extraction prompts. Versioned constants — bump the suffix, never edit in place."""

PROMPT_VERSION = "v1"

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
