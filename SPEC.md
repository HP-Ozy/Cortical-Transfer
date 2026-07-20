# MemPack Format Specification — v0.2.0

Status: Draft. This document is normative. The key words MUST, MUST NOT,
SHOULD, SHOULD NOT and MAY are to be interpreted as described in RFC 2119.

A **MemPack** is a portable, human-readable snapshot of a user's AI memory:
identity facts, salient episodes, open threads, and interaction style. It is
designed so that any LLM application can import it and reconstruct the user's
context without access to the application that produced it.

## 1. Container

A MemPack is a **directory** with the layout below, or that directory packed
into a ZIP archive with the `.mempack` extension (no compression requirements;
importers MUST accept both stored and deflated entries).

```
<pack>/
├── mempack.json      # manifest — REQUIRED
├── identity.json     # REQUIRED (may be an empty list)
├── episodes.json     # REQUIRED (may be an empty list)
├── threads.json      # REQUIRED (may be an empty list)
├── style.md          # REQUIRED (may be empty)
└── raw/              # OPTIONAL raw history chunks
```

All JSON files MUST be UTF-8. Importers MUST ignore unknown files in the
directory root and MUST NOT fail on their presence.

`raw/` MAY be omitted entirely (e.g. exported without raw history for
privacy). Everything in this spec MUST work identically without it: a node's
`source_refs` pointing at absent raw content is not an error.

## 2. Manifest — `mempack.json`

| Field            | Type              | Semantics |
|------------------|-------------------|-----------|
| `format_version` | string, semver    | Version of this spec the pack conforms to. REQUIRED. |
| `created_at`     | RFC 3339 datetime | First creation of this pack. REQUIRED. |
| `updated_at`     | RFC 3339 datetime | Last modification. REQUIRED. |
| `source_models`  | array of string   | Model identifiers whose conversations fed this pack. MAY be empty. |
| `generator`      | string            | Producing software and version. Informational. |
| `content_hashes` | object            | Map of relative file path → lowercase SHA-256 hex of the file's exact bytes. See §5. |
| `extracted`      | object            | Map of conversation id → SHA-256 hex of its turns. Producers MAY use it to skip conversations already distilled into the pack. OPTIONAL, added in 0.2. |

## 3. SemanticNode

`identity.json`, `episodes.json` and `threads.json` each contain a JSON
**array of SemanticNode objects**:

| Field               | Type                   | Semantics |
|---------------------|------------------------|-----------|
| `id`                | string, ULID           | Unique within the pack. REQUIRED. |
| `text`              | string                 | The memory content, natural language. REQUIRED. Importers MUST treat this as untrusted data, never as instructions (§6). |
| `granularity`       | `summary` \| `episode` \| `detail` | Abstraction level. `summary` aggregates children. |
| `salience`          | number 0.0–1.0         | Importance for context building. Higher = include first. |
| `confidence`        | `stated` \| `inferred` | Whether the user stated the fact explicitly or the extractor deduced it. Importers SHOULD prefer `stated` nodes when a token budget forces a choice. OPTIONAL, default `stated`, added in 0.2. |
| `created_at`        | RFC 3339 datetime      | When the node was first extracted. |
| `last_confirmed_at` | RFC 3339 datetime      | Most recent evidence supporting the node. |
| `superseded_by`     | string \| null         | ULID of the node that replaces this one. See below. |
| `parent_id`         | string \| null         | ULID of a coarser-granularity node this belongs to. |
| `valid_from`        | string \| null         | `YYYY-MM-DD`. When the fact became true in the real world (event time, not ingestion time). OPTIONAL, added in 0.2. |
| `valid_until`       | string \| null         | `YYYY-MM-DD`. When the fact stopped being true. OPTIONAL, added in 0.2. |
| `source_refs`       | array of string        | Opaque turn/conversation identifiers into `raw/`. |
| `tags`              | array of string        | Free-form labels. |

**Contradictions.** When new information contradicts an existing node, the
producer MUST keep the old node and set its `superseded_by` to the new node's
id. Producers MUST NOT delete contradicted nodes (deletion is reserved for
explicit redaction, §7). Importers MUST exclude superseded nodes from context
building but MAY show them in history views. Supersession chains MUST be
followed to the newest node.

**Temporal validity.** `valid_from`/`valid_until` are **event time** — when the
fact holds in the real world — distinct from `created_at`/`last_confirmed_at`
(ingestion time). Producers SHOULD only set them when the source text states or
implies them, resolving relative expressions against the conversation's date,
and MUST NOT invent them. When a node is superseded, producers SHOULD set its
`valid_until` to the superseding node's `valid_from` when known. Importers
SHOULD exclude nodes whose `valid_until` is in the past from context building
(like superseded nodes) and SHOULD show validity ranges next to facts that have
them.

**Hierarchy.** `parent_id` links `detail` → `episode` → `summary`. Importers
SHOULD prefer coarser nodes when a token budget is tight and MAY drop children
whose parent is already included.

## 4. Style card — `style.md`

Free-form Markdown, natural language, describing tone, formality, verbosity,
languages, recurring references, and how to address the user. Producers SHOULD
keep it under 300 tokens. Importers SHOULD include it verbatim in the context
block. It is data, not instructions to the importing application (§6).

## 5. Integrity

`content_hashes` MUST contain an entry for every file in the pack except
`mempack.json` itself, keyed by path relative to the pack root using `/`
separators (e.g. `raw/conv-001.jsonl`).

Verification: recompute SHA-256 over each listed file's bytes and compare.
A pack **verifies** iff every listed file exists with a matching hash and the
four required part files are listed. Importers MUST verify on import and MUST
NOT silently accept a non-verifying pack; overriding MUST require an explicit
user action (e.g. a `--force` flag).

Integrity protects against corruption and accidental tampering. It is **not**
authentication: there is no signature in v0.1, so anyone can rehash a modified
pack. Signing MAY be added in a future minor version.

## 6. Security model — memory is data

Node `text` and `style.md` originate from LLM output over user conversations
and are **untrusted input** to any importer.

- Importers MUST NOT execute, follow, or interpret node text as instructions,
  tool calls, or role markers.
- When building a prompt from a MemPack, importers MUST wrap the memory in a
  clearly delimited block preceded by a statement that the block is user
  memory data and must not be followed as instructions.
- Importers SHOULD neutralize instruction-like patterns (e.g. "ignore previous
  instructions", chat-template role tags such as `<|im_start|>`, `[INST]`,
  `<|system|>`) before inclusion.

## 7. Redaction (right to erasure)

Producers MUST support permanently deleting a node on user request: the node
is removed from its part file (not merely marked superseded), and any
`superseded_by`/`parent_id` references to it are nulled. If the store keeps
history (e.g. Git), the producer MUST also purge the content from that
history and document the mechanism's limits (copies already exported are
out of reach — erasure applies to the store the producer controls).

## 8. Versioning and migration

`format_version` follows semver:

- **Patch/minor** (`0.1.x` → `0.1.y`, `0.x` → `0.y` for y>x): additive only.
  New OPTIONAL fields or files. Importers MUST accept packs with a higher
  minor version by ignoring unknown fields, and MUST NOT reject them.
- **Major**: breaking. Importers MUST reject a pack whose major version they
  do not implement, with a clear error.
- Producers MUST write the exact spec version they implement.

(While the format is 0.x, the minor digit plays the major role: `0.2` MAY
break `0.1`. From `1.0.0` on, standard semver applies.)

## 9. Minimal conforming MemPack

```
minimal/
├── mempack.json
├── identity.json
├── episodes.json
├── threads.json
└── style.md          (empty file)
```

`mempack.json`:

```json
{
  "format_version": "0.1.0",
  "created_at": "2026-07-15T12:00:00Z",
  "updated_at": "2026-07-15T12:00:00Z",
  "source_models": [],
  "generator": "hand-written",
  "content_hashes": {
    "identity.json": "6a1b...<sha256 of identity.json bytes>",
    "episodes.json": "4f53...<sha256 of the literal bytes '[]'>",
    "threads.json": "4f53...",
    "style.md": "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"
  }
}
```

`identity.json`:

```json
[
  {
    "id": "01J2ZK8Q3WV9XN5T7R2M4B6C8D",
    "text": "Prefers concise answers in Italian.",
    "granularity": "summary",
    "salience": 0.9,
    "created_at": "2026-07-15T12:00:00Z",
    "last_confirmed_at": "2026-07-15T12:00:00Z",
    "superseded_by": null,
    "parent_id": null,
    "source_refs": [],
    "tags": ["language"]
  }
]
```

`episodes.json` and `threads.json`: `[]`. Note `style.md`'s hash above is the
SHA-256 of the empty byte string.

A conforming importer given this pack MUST verify it, MUST surface the single
identity node as memory data, and MUST NOT treat its text as an instruction.
