# claude-operating-rules

Four Claude Code plugins. Three hold rules that were learned the expensive way — each one
traceable to a specific failure, with the measurement that exposed it kept intact. The
fourth, `tone-roulette`, is a demonstration rather than a rule; see its row in the table
below for what that means.

Nothing here is advice in the abstract. Every rule exists because something broke: a
security check that passed because its needle was empty, an agent that reverted a human's
work because it could not account for it, fourteen defects that all came from code written
into a plan document, a session that grew too large to reopen.

## The four plugins

| Plugin | Install it if | README |
|---|---|---|
| **evidence-discipline** | Always. Nothing in it is specific to Claude Code — it is "prove the check can fail before you trust that it passed", and "a fix is not done until every copy of the claim is fixed" | [plugins/evidence-discipline/README.md](plugins/evidence-discipline/README.md) |
| **agent-operations** | You dispatch subagents or run git worktrees. Useless if you work alone in one session | [plugins/agent-operations/README.md](plugins/agent-operations/README.md) |
| **ticket-craft** | You want ASD-STE100 Simplified Technical English enforced on every ticket. Deliberately packaged alone, so wanting the verification rules never drags this in | [plugins/ticket-craft/README.md](plugins/ticket-craft/README.md) |
| **tone-roulette** | You want a demonstration of what a plugin can do beyond skills — output styles, a `SessionStart` hook and a `UserPromptSubmit` hook, two shell handlers sharing common code — rather than another rule. It is a joke, not a lesson: it rolls a random conversational tone at session start and holds it for the session. Skip it if you only want the operating rules | [plugins/tone-roulette/README.md](plugins/tone-roulette/README.md) |

## Install

```
/plugin marketplace add skomp/claude-operating-rules
/plugin install evidence-discipline
/plugin install agent-operations
/plugin install ticket-craft
/plugin install tone-roulette
```

## Two rules to put in your own CLAUDE.md

Each skill's frontmatter `description` is its trigger — that is the mechanism that fires
it, and it needs no help from you.

But a description only *routes*; it is not itself an instruction that gets obeyed. Two
rules here have to hold even when the skill is never opened, because the cost of missing
them lands outside your session. Paste these into your `CLAUDE.md`:

```markdown
- Never `git add -A` or `git commit -a` while an agent of yours is live in the same
  checkout. Stage explicit paths you own.
- Every GitHub issue you create carries the `created-by-claude` label.
```

The second only applies if you install `ticket-craft`.

## On provenance

Project names are redacted — where a rule says "a GPU renderer project, 2026-08-20", the
original named a real repository. Dates, measurements, commands, error strings and version
numbers are unchanged, because those are the part that is worth anything. A redacted name
costs a reader nothing; a rounded measurement costs them the lesson.

A few passages are marked *"Recorded from a concurrent session"*. Those were written down
by one session observing another's failure, and have not been reviewed by the session that
lived it. They are flagged rather than quietly folded in, because an unmarked second-hand
account reads as settled practice to whoever comes next — which is itself one of the
failures documented here.

## Known limitation

These skills have not been tested against a live agent under pressure. They are faithful
records of failures that already happened, not instruments anyone has watched fire. The
untested property is retrieval: whether each `description` actually triggers at the moment
it should. If you find one that does not fire when it ought to, that is the most useful
issue you could open.

## License

MIT
