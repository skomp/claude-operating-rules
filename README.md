# claude-operating-rules

Five Claude Code plugins, of three kinds. Three hold rules that were learned the
expensive way — each one traceable to a specific failure, with the measurement that
exposed it kept intact. `session-relay` is a design, specified and built in one session
on 2026-09-13, with no incident behind it. `tone-roulette` is neither: a demonstration
of what a plugin can do beyond skills, and a joke. Each row in the table below says
which kind it is, because the three are not interchangeable and the difference is the
point.

Nothing in the first three is advice in the abstract. Every rule there exists because
something broke: a security check that passed because its needle was empty, an agent that
reverted a human's work because it could not account for it, fourteen defects that all came
from code written into a plan document, a session that grew too large to reopen.
`session-relay` has no such failure yet — what its build session found instead, in one
sentence: a check whose planted fault could not fail and an addressing rule that could not
reach one live session in four, both measured on the day and fixed before the plugin
shipped, plus a guard that would have rejected every real signal if the transport wraps
what it delivers. That last one was reasoned about, not observed — the guard now strips the
wrapper before it matches, but no live signal has yet been seen, and the verification item
that would record the wrapper's real shape has not run.

## The five plugins

| Plugin | Install it if | README |
|---|---|---|
| **evidence-discipline** | Always. Nothing in it is specific to Claude Code — it is "prove the check can fail before you trust that it passed", and "a fix is not done until every copy of the claim is fixed" | [plugins/evidence-discipline/README.md](plugins/evidence-discipline/README.md) |
| **agent-operations** | You dispatch subagents or run git worktrees. Useless if you work alone in one session | [plugins/agent-operations/README.md](plugins/agent-operations/README.md) |
| **ticket-craft** | You want ASD-STE100 Simplified Technical English enforced on every ticket. Deliberately packaged alone, so wanting the verification rules never drags this in | [plugins/ticket-craft/README.md](plugins/ticket-craft/README.md) |
| **session-relay** | Your project spans multiple repositories, each with its own live Claude session, and you track work in GitHub issues. Skip it if you work in one repository alone, or that repository tracks work on a `TODO.md` — both are hard preconditions the protocol refuses to run without | [plugins/session-relay/README.md](plugins/session-relay/README.md) |
| **tone-roulette** | You want a demonstration of what a plugin can do beyond skills — output styles, a `SessionStart` hook and a `UserPromptSubmit` hook, two shell handlers sharing common code — rather than another rule. It is a joke, not a lesson: it rolls a random conversational tone at session start and holds it for the session. Skip it if you only want the operating rules | [plugins/tone-roulette/README.md](plugins/tone-roulette/README.md) |

## Install

```
/plugin marketplace add skomp/claude-operating-rules
/plugin install evidence-discipline
/plugin install agent-operations
/plugin install ticket-craft
/plugin install session-relay
/plugin install tone-roulette
```

## tone-roulette: known limitations

- **Subagents do not inherit the tone.** Forks inherit the parent's system prompt; other
  subagents run their own. Implementer and reviewer agents answer in the default voice.
- **Disabling the plugin mid-session does not retract a tone already injected.** The text
  is already in the conversation history. `/tone off` is the mid-session path; disabling
  the plugin is the between-sessions path.
- **Only `startup` rolls.** A resumed session re-injects the stored tone rather than
  rolling a new one, so `--resume` keeps whatever tone was already in play.
- **Tone adherence depends on the model.** Tested on Haiku and Sonnet: on Sonnet the tone
  lands reliably. On Haiku it frequently does not — the hook still fires, a tone is still
  rolled and written to the state file, but the model answers in the plain default voice
  anyway. The mechanism is working in that case; the model is not following the injected
  instruction. A Haiku user who sees no tone is looking at a model limitation, not a broken
  plugin. Other models have not been tested.

## Three rules to put in your own CLAUDE.md

Each skill's frontmatter `description` is its trigger — that is the mechanism that fires
it, and it needs no help from you.

But a description only *routes*; it is not itself an instruction that gets obeyed. Three
rules here have to hold even when the skill is never opened, because the cost of missing
them lands outside your session. Paste these into your `CLAUDE.md`:

```markdown
- Never `git add -A` or `git commit -a` while an agent of yours is live in the same
  checkout. Stage explicit paths you own.
- Every GitHub issue you create carries the `created-by-claude` label.
- Never agree a coordination convention with another session — a freeze, a handoff word,
  an ownership map. Send facts about your own state; ask me for anything more.
```

The second only applies if you install `ticket-craft`. The third is the one a session
breaks before it would ever open a skill: it is already composing the message.

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

These skills have not been tested against a live agent under pressure. The first six, in
`evidence-discipline`, `agent-operations` and `ticket-craft`, are faithful records of
failures that already happened, not instruments anyone has watched fire. `session-relay`
is not a record of anything — it is a design, and its two skills have not yet run against
a live fleet of sessions. That run is scheduled, not done: this section narrows for
`session-relay` only once the run has actually happened.

The untested property, for all five plugins, is retrieval: whether each `description`
actually triggers at the moment it should. If you find one that does not fire when it
ought to, that is the most useful issue you could open.

## License

MIT
