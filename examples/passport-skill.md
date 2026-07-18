# The passport skill — Cortical-Transfer's mechanism in one file

This is the smallest working demonstration of the idea behind Cortical-Transfer:
an agent skill (for Claude Code, but the pattern is tool-agnostic) that
distills a live session — plus the assistant's long-term, cross-session
memory — into a single self-describing `PASSPORT.md`. Paste that file as the
first message into DeepSeek, Qwen, ChatGPT, Gemini or any local model, and it
resumes the work: who you are, what you asked, decisions made, current state,
next steps.

No APIs, no embeddings, no code. The file's header is itself a prompt for the
receiving model. The file **is** the protocol. MemPack (see
[SPEC.md](../SPEC.md)) is this same mechanism made rigorous: versioned schema,
integrity manifest, Git history, token budgeting, prompt-boundary sanitizing.

A host-neutral edition of this same skill — installable in ChatGPT, Google
Antigravity, Gemini, Cursor, Windsurf, Copilot, or pasted as a message into
any chat model — is in [passport-universal.md](passport-universal.md).

The skill, verbatim:

---

```markdown
---
name: passport
description: Generates a portable "context passport" — a self-describing
  markdown file that transfers user identity, original request, work state
  and next steps to ANY other model (DeepSeek, Qwen, ChatGPT, Gemini...).
  The user pastes it as the first message in the new chat and the model
  resumes where you left off. Trigger: "/passport", "export the context",
  "portable memory".
---

# Passport — portable memory across models

When invoked, distill the ENTIRE current conversation into a single
`PASSPORT.md` file in the working directory, then print it in full for
copy-paste.

## Writing rules

- Write the passport in **English** (maximum cross-model compatibility),
  but instruct the receiving model to reply in the user's language.
- Facts only, zero narrative: the receiver has seen nothing, every sentence
  must stand on its own. No references to "as said above" or to the
  exporting assistant's internal tools.
- Absolute file paths, exact commands, exact versions. A vague detail is a
  lost detail.
- Include decisions MADE and their one-line why — this is what stops the new
  model from re-proposing already-rejected approaches.
- Target length: the minimum that allows resumption. Usually < 80 lines.

## File format

    # CONTEXT PASSPORT
    > INSTRUCTIONS FOR THE RECEIVING MODEL: You are taking over an ongoing
    > task from a previous AI assistant. Everything below is verified
    > context. Read it all, do NOT re-ask for information already here, and
    > continue the work from "Next steps". Reply in the user's language.

    ## User
    Who they are, expertise level, relevant preferences (2-4 lines).

    ## Original request
    The task as the user stated it, plus any scope changes since.

    ## Decisions made (and why)
    - decision — one-line reason

    ## Work completed
    What is DONE and verified. File paths touched, commands that worked.

    ## Current state
    What is in progress, what is broken, exact error messages if any.

    ## Long-term memory (persistent, cross-session)
    Distilled from the assistant's memory: who the user is, their ongoing
    projects, stable preferences. Only entries relevant to future work —
    this is what makes the passport carry the whole relationship, not just
    this session.

    ## Next steps
    Numbered, concrete, in order. Step 1 is what the receiving model does
    first.

    ## Environment (only if relevant)
    OS, versions, paths, credential placeholders — never real secrets.

## After writing

1. Save as `PASSPORT.md` in the cwd (overwrite if present: the passport is
   always the latest state).
2. Print the full content in the reply for frictionless copy-paste.
3. Close with one line: "Paste it as the first message in the new chat, or
   upload PASSPORT.md directly if the model supports file upload."

## What NOT to do

- No real secrets (API keys, passwords): use `<REDACTED>`.
- No import/resume mode: to come back, paste the same file — it is
  self-describing. Export-only until pasting proves insufficient.
```
