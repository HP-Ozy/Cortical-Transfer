# ADR 0002 — A profile's Git worktree IS the MemPack

Status: accepted. Date: 2026-07-15.

`~/.cortical-transfer/<profile>/` is a Git repo whose working tree is exactly
the MemPack directory layout. Consequences:

- Export = archive the worktree (minus `.git`); import = write files + commit.
  No serialization layer between "stored" and "portable" forms.
- `ct diff` parses the part files at two revisions and diffs nodes by id —
  semantic diff, not line diff.
- `ct checkout <rev>` restores old content **as a new commit** instead of
  moving HEAD. History stays linear and append-only; nothing is ever lost by
  going back (redaction is the one sanctioned destructive path, ADR later).
- `CT_HOME` env var overrides the root for tests; no config file.

Rejected: separate storage format inside the repo (pointless indirection),
detached-HEAD checkout (confusing state for users).
