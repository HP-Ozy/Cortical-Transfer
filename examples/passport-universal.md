# Passport, universal edition — the same skill for ANY assistant

[`passport-skill.md`](passport-skill.md) is the Claude Code packaging of the
passport idea. But a skill is just instructions in markdown — so the same
trick that makes the passport portable makes the *skill itself* portable:
paste the block below wherever your tool reads instructions, and if your
"tool" is a plain chatbot with no such place, paste it as a message. The
model now has the skill for that conversation. The file is the protocol,
all the way down.

## Where to install it

| Host | Location |
|------|----------|
| Claude Code | `~/.claude/skills/passport/SKILL.md` (add the frontmatter shown in [passport-skill.md](passport-skill.md)) |
| Claude.ai / Claude Desktop | Project instructions |
| ChatGPT | Custom Instructions, or a Custom GPT's instructions |
| Google Antigravity | `.agent/rules/passport.md` (workspace rules), or `AGENTS.md` |
| Gemini CLI | `GEMINI.md` |
| Cursor | `.cursor/rules/passport.mdc` |
| Windsurf | `.windsurf/rules/passport.md` |
| GitHub Copilot | `.github/copilot-instructions.md` |
| DeepSeek, Qwen, Mistral, local models, any web chat | paste the block below as a message: "adopt this skill for our session" |

The **receiving** side never needs any of this: the passport's own header is
the prompt that tells any model how to consume it.

## The skill, host-neutral

```markdown
# Skill: passport — portable memory across AI models

Adopt this skill for the rest of the session. Trigger: the user types
"/passport" or asks to "export the context" / "portable memory".

When triggered, distill the ENTIRE current conversation into one
self-describing markdown passport. Output it in full for copy-paste; if you
can write files, also save it as `PASSPORT.md` in the working directory
(overwrite — the passport is always the latest state).

## Writing rules

- Write the passport in English (maximum cross-model compatibility), but
  instruct the receiving model to reply in the user's language.
- Facts only, zero narrative: the receiver has seen nothing, every sentence
  must stand on its own. No references to "as said above" or to this
  assistant's internal tools.
- Absolute file paths, exact commands, exact versions. A vague detail is a
  lost detail.
- Include decisions MADE and their one-line why — this is what stops the new
  model from re-proposing already-rejected approaches.
- If you have persistent, cross-session memory about this user, distill the
  entries relevant to future work into the "Long-term memory" section;
  otherwise omit that section.
- Target length: the minimum that allows resumption. Usually < 80 lines.
- No real secrets (API keys, passwords): use `<REDACTED>`.

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
    Only if available: who the user is, ongoing projects, stable
    preferences — what makes the passport carry the whole relationship,
    not just this session.

    ## Next steps
    Numbered, concrete, in order. Step 1 is what the receiving model does
    first.

    ## Environment (only if relevant)
    OS, versions, paths, credential placeholders — never real secrets.

## After writing

Close with one line: "Paste it as the first message in the new chat, or
upload PASSPORT.md directly if the model supports file upload."
```
