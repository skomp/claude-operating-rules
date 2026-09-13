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

| Plugin | Skills | Install it if |
|---|---|---|
| **evidence-discipline** | `verifying-claims`, `completing-a-correction` | Always. Nothing in it is specific to Claude Code — it is "prove the check can fail before you trust that it passed", and "a fix is not done until every copy of the claim is fixed" |
| **agent-operations** | `parallel-sessions`, `writing-plans-and-dispatches`, `recovering-a-session` | You dispatch subagents or run git worktrees. Useless if you work alone in one session |
| **ticket-craft** | `tracking-work` | You want ASD-STE100 Simplified Technical English enforced on every ticket. Deliberately packaged alone, so wanting the verification rules never drags this in |
| **tone-roulette** | `tone` | You want a demonstration of what a plugin can do beyond skills — output styles, a `SessionStart` hook and a `UserPromptSubmit` hook, two shell handlers sharing common code — rather than another rule. It is a joke, not a lesson: it rolls a random conversational tone at session start and holds it for the session, and while the `impatient` tone holds, notes a real gap since your last message so it has something true to be impatient about. Skip it if you only want the operating rules |

## Install

```
/plugin marketplace add skomp/claude-operating-rules
/plugin install evidence-discipline
/plugin install agent-operations
/plugin install ticket-craft
/plugin install tone-roulette
```

## tone-roulette: the division of labour

Every tone in the catalogue is also a real Claude Code output style, so `/config` (under
**Output style**) already lists and switches between all of them instantly, with no model
turn, and Claude Code persists that choice in a settings file rather than the conversation —
it survives `/clear` and restart on its own. The plugin's `SessionStart` hook exists for the
one thing `/config` can't do: pick a tone at random. It checks first whether you've already
chosen a style; if you have, it does nothing at all, on every session start, resume, clear or
compact, not only the first one. Only when nothing is chosen does it roll, hold the roll in a
small per-session state file, and re-inject it across compaction. `/tone roll` is the only
`/tone` verb left that does its own work — switching to a specific tone, listing the
catalogue, and turning the tone off are all faster done through `/config` directly, and the
`tone` skill just points you there. See the row above and the design spec's Data flow section
for the mechanics.

A second hook, on `UserPromptSubmit`, backs the `impatient` tone with a real measurement
instead of leaving it to invent one: it times the gap since your previous message and, only
while `impatient` is the tone actually in force, notes it (`"...was 11 minutes ago"`) so the
tone can be pointedly impatient about something true rather than generically grumbling. It
fires on every prompt, in every session, for all twenty tones — so for the other nineteen, and
for anyone who has chosen a different style, it does nothing at all and costs nothing beyond
one cheap check. Gaps under two minutes go unremarked; the first prompt of a session has
nothing to compare against yet. Both hooks share their "is a style chosen, which tone is this
session's" detection from one file (`hooks-handlers/tone-common.sh`) rather than keeping two
copies of it.

## tone-roulette: known limitations

- **Subagents do not inherit the tone.** Forks inherit the parent's system prompt; other
  subagents run their own. Implementer and reviewer agents answer in the default voice.
- **Disabling the plugin mid-session does not retract a tone already injected.** The text
  is already in the conversation history. Choosing a different style via `/config` is the
  mid-session path; disabling the plugin is the between-sessions path.
- **Only `startup` rolls, and only when no output style is chosen.** A resumed session
  re-injects the stored *rolled* tone rather than rolling a new one, so `--resume` keeps
  whatever was already in play — but if you've chosen a style via `/config` since the last
  `startup`, the hook stands down instead, on every source, and neither rolls nor re-injects
  over your choice.
- **A `claude --settings` CLI override or an MDM-delivered policy can pick a style the hook
  can't see.** Both take effect over anything in a settings file, but neither is a file the
  hook can read, so on the rare machine where one is in play the hook may roll over a style
  that in fact takes effect. See the design spec's Known limitations for detail.
- **Tone adherence depends on the model.** Tested on Haiku and Sonnet: on Sonnet the tone
  lands reliably. On Haiku it frequently does not — the hook still fires, a tone is still
  rolled and written to the state file, but the model answers in the plain default voice
  anyway. The mechanism is working in that case; the model is not following the injected
  instruction. A Haiku user who sees no tone is looking at a model limitation, not a broken
  plugin. Other models have not been tested.
- **Four tones perform doubt or pessimism** — `negative-nancy`, `hedging-hannah`,
  `second-guess-sid` and `nervous-nellie`. Their hedging is a speech register, not a
  confidence signal: the underlying assessment is unchanged whether or not the tone is
  hedging it. If you need to know how confident the assistant actually is, ask directly or
  switch tones via `/config`.
- **Switching away from `impatient` and back loses the gap history.** The previous-prompt
  timestamp is only ever read or written while `impatient` is the active tone, so a detour
  through another tone and back is treated as a fresh session for gap purposes — the next
  prompt after switching back is never announced as a gap, even if the detour itself was long.

  This is deliberate: the alternative is tracking timestamps for every tone all the time,
  which is exactly the "cost nothing when not impatient" contract this hook exists to keep.

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
