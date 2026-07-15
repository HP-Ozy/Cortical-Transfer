# ADR 0006 — Redaction = squash history + prune, not per-commit rewrite

Status: accepted. Date: 2026-07-15.

`ct redact <node-id>` must make the content unrecoverable from the store
(GDPR erasure). Two candidate mechanisms:

1. **Rewrite every commit** dropping the content (git-filter-repo style):
   preserves history granularity, but means reimplementing tree rewriting or
   depending on an external tool that isn't installed by default, with subtle
   failure modes on Windows.
2. **Squash to a single redacted baseline** (orphan branch), then
   `reflog expire --expire=now --all` + `gc --aggressive --prune=now`:
   ~10 lines, provably leaves no unreachable objects (`git fsck --unreachable`
   is empty in tests).

Chosen: (2). Redaction is expected to be rare; trading history granularity
for a guaranteed, testable erasure is the right default. Also purged: raw
turns listed in the node's `source_refs`, and the derived `.rag/` index.

**Limits (also stated in SPEC §7 and README):** erasure applies to the local
store only. Packs already exported with `ct export`, repo clones, and
filesystem backups are out of our reach — that is a property of distributed
storage, not of this implementation.
