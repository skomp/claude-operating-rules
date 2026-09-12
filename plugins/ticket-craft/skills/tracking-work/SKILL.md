---
name: tracking-work
description: "Read BEFORE writing or editing any ticket. Load when you are about to write a GitHub issue, a sub-issue, a user story, acceptance criteria, or a `TODO.md` entry; edit the body of an existing issue; file a ticket for work you are deferring; label an issue you created; or decide where this project tracks its work."
---

# Tracking Work

Two questions, one moment: **where does this get written down, and how is it worded.**

## Part 1 — Where it goes

Capture next steps and known gaps somewhere durable, not only in chat.

Two options: a `TODO.md` file, or GitHub issues (preferred in general, but overkill for very small projects). Task tracking is a **per-project choice**:

1. Check that project's `CLAUDE.md` for an existing tracking preference and follow it.
2. If none is recorded, **ask the user which to use (GitHub issues vs. `TODO.md`) before writing anything**, then record the answer in that project's `CLAUDE.md` so future sessions don't need to ask again.

Write down anything deliberately deferred — an entry in the project's chosen tracker, or a deferral comment marker your project already uses (`TODO:`, `FIXME:`, or your own) — instead of leaving it implicit.

### Label every issue Claude creates

Label every GitHub issue Claude creates with `created-by-claude`, so automatically created issues are identifiable. If the repo doesn't have the label yet, create it first:

```bash
gh label create created-by-claude --description "Issue created automatically by Claude" --color D97706
```

Worth a one-line tripwire in your `CLAUDE.md` as well, because an unlabelled issue is outward-facing. **CLAUDE.md carries the bare obligation; this skill carries the command and the reasoning.**

## Part 2 — How it is worded

Every ticket you write uses **ASD-STE100 Simplified Technical English**: GitHub issue titles and bodies, sub-issues, user stories, `TODO.md` entries, acceptance criteria, and edits to an existing issue body.

**Why:** the readers include people with no context on the change and non-native English speakers, and STE removes the ambiguity that otherwise costs a clarifying round-trip.

The rules that earn the most:

- **One instruction per sentence.** Keep procedural steps under 20 words and descriptive sentences under 25.
- **Active voice, with a named actor.** "The API returns 404" — not "A 404 is returned".
- **One word, one meaning, every time.** Do not alternate "ticket"/"issue"/"task" or "user"/"caller"/"client" in one document. Choose one term and repeat it.
- **Simple approved verbs.** "remove", not "get rid of"; "start", not "kick off"; "change", not "touch up". Avoid phrasal verbs.
- **Simple present, past or future only.** "when the cache expires", not "on the cache expiring". Avoid `-ing` forms used as verbs.
- **Keep the articles.** "Add the flag to the config file", never "Add flag to config".
- **No noun stack longer than three words.** "the timeout for the token refresh", not "the token refresh timeout config value".
- **One topic per paragraph**, short paragraphs, and a list for any set of steps or conditions.
- **Say what to do, not what to avoid**, and put a warning before the step it applies to.

### Precision wins

Where STE and precision conflict, **precision wins**: identifiers, file paths, commands, error strings and API names stay verbatim, however long or unapproved the words are. **Never simplify a symbol name to make a sentence read better.**

### Scope

This is about tickets. Chat replies, commit messages, code comments and design docs keep their normal voice.

One rule reaches further, because it governs all prose including chat: **always qualify an issue or PR reference with the repo.** Never write a bare `#123`; write `PR: <repo>#<number>` for a pull request (`PR: repo-b#56`) and `repo#123` for an issue (`repo-a#81`). It applies to every ticket you write here too.
