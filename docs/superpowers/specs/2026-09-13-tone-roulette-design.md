# tone-roulette — design

**Date:** 2026-09-13
**Status:** approved, ready for implementation
**Plugin:** `plugins/tone-roulette/`

## Purpose

A deliberately frivolous plugin that demonstrates what a Claude Code plugin can actually
do. On session start it rolls a random conversational tone, announces which one it rolled,
and holds that tone for the rest of the session.

It is the first plugin in this marketplace that is not skill-only: it combines an output
style catalogue, a `SessionStart` hook, a shell handler and a skill. The demonstration
value is the combination — no single component can deliver the behaviour alone.

## Requirements

1. The tone is selected **randomly**, not chosen by the model.
2. Selection happens **when the plugin is enabled**, that is at session start — not only
   when a command is typed.
3. The selected tone is **announced** to the user.
4. The tone **holds for the rest of the session**, including across context compaction.
5. The user can **change the tone** mid-session.
6. The user can **return to the default tone**, by command mid-session or by disabling the
   plugin between sessions.
7. The tone governs **conversational prose only**. Code, commit messages, file contents,
   issue bodies and tool arguments are never affected.

## Verified mechanism facts

Everything below was confirmed against Claude Code 2.1.259 on disk, not from documentation.

| Fact | Evidence |
|---|---|
| `hooks/hooks.json` is auto-discovered; `plugin.json` needs no `hooks` key | `learning-output-style/.claude-plugin/plugin.json` carries no hooks key, yet its hook fires |
| A `SessionStart` hook runs a shipped script via `${CLAUDE_PLUGIN_ROOT}` | `learning-output-style/hooks/hooks.json` |
| Instructions are injected as `{"hookSpecificOutput":{"hookEventName":"SessionStart","additionalContext":"..."}}` | `learning-output-style/hooks-handlers/session-start.sh` |
| `SessionStart` accepts `matcher: "startup\|clear\|compact"` | `superpowers/6.3.0/hooks/hooks.json` |
| Hook stdin JSON includes `session_id` | hook documentation embedded in the 2.1.259 binary |
| `systemMessage` displays a message to the user, for all hook events | same |
| `outputStyles` is a valid plugin manifest key | manifest key list in the 2.1.259 binary |
| `force-for-plugin` exists but applies only to plugin output styles | binary carries the guard string `" has force-for-plugin set, but this option only applies to plugin output styles. Ignoring."` |

`commands/*.md` is documented in `example-plugin` as the legacy layout; new plugins should
use `skills/<name>/SKILL.md`. Both load identically.

## Architecture

Two jobs that need different mechanisms:

- **Holding** a tone is what output styles are for. They sit at system-prompt level,
  `/output-style <name>` switches between them, and disabling the plugin removes them.
  Requirements 4, 5 and 6 come free.
- **Rolling** a tone is what output styles cannot do. A static Markdown file cannot pick
  randomly. That is the `SessionStart` script's job.

The join: **one tone is one file, read two ways.** Each `output-styles/*.md` file is loaded
natively by Claude Code *and* read by the roll script, which picks one at random, strips the
frontmatter and emits the body as `additionalContext`. There is no second catalogue, and no
tone text that exists in two places.

```
plugins/tone-roulette/
├── .claude-plugin/plugin.json        # "outputStyles": "./output-styles/"
├── hooks/hooks.json                  # SessionStart, matcher: startup|clear|compact
├── hooks-handlers/session-start.sh   # roll, persist, announce, inject
├── output-styles/
│   ├── noir-detective.md
│   ├── drill-sergeant.md
│   ├── golden-retriever.md
│   ├── victorian-naturalist.md
│   ├── corporate-bureaucrat.md
│   ├── sports-commentator.md
│   ├── conspiracy-theorist.md
│   └── medieval-herald.md
└── skills/tone/SKILL.md              # /tone, /tone <name>, /tone off, /tone list
```

`force-for-plugin` is deliberately **not** used. It force-applies a single style, which is
the opposite of rolling one, and avoiding it removes the design's only dependency on a field
that could not be confirmed against a working example.

## Data flow

`SessionStart` fires with a matcher value in its stdin JSON:

- **`startup`** — roll. Pick a file from `output-styles/` at random, write the chosen tone
  name to the state file, emit `systemMessage` announcing it and `additionalContext`
  carrying the file body.
- **`clear` / `compact`** — do not roll. Read the state file, re-emit the same tone's
  `additionalContext`. This is what satisfies requirement 4: compaction can drop the
  injected instruction, so it is re-injected unchanged rather than re-rolled.
- **`resume` / `clear` / `compact` emit nothing when the state file holds `__off__`.** The
  `/tone off` command writes this literal token instead of deleting the state file, so
  absence keeps meaning "roll" and "off" gets its own explicit representation. `startup`
  alone ignores a leftover `__off__` and always rolls a fresh tone — switching off is
  per-session, and it must never leak into a new one.

State lives at `~/.claude/tone-roulette/<session_id>`, a single line holding the tone name.
`session_id` comes from the hook's stdin JSON. If the state file is missing when `clear` or
`compact` fires, the script rolls a fresh tone rather than failing.

## Tone file format

```markdown
---
name: noir-detective
description: World-weary 1940s private eye narrating your codebase
---

## Ground rules

<the shared prose-only block, byte-identical in every tone file>

## Voice

<tone-specific instructions>
```

The ground-rules block enforces requirement 7 and must appear in every file, because a file
selected natively through `/output-style` is never seen by the script and so cannot have the
rules prepended to it. That means eight copies of the same paragraph, which is a drift
hazard. It is accepted deliberately and guarded by a test asserting that every tone file
contains the block byte-for-byte.

## The `/tone` skill

| Invocation | Behaviour |
|---|---|
| `/tone` | Report the current tone and how it was selected |
| `/tone <name>` | Switch to a named tone, and update the state file |
| `/tone roll` | Re-roll at random |
| `/tone off` | Drop the tone and return to default for the rest of the session |
| `/tone list` | List the catalogue |

Frontmatter sets `disable-model-invocation: true`, so the skill fires only when the user
types it. A tone plugin that re-rolled itself because the model thought it relevant would be
a bug.

## Error handling

| Condition | Behaviour |
|---|---|
| `output-styles/` missing or empty | Emit nothing, exit 0. The session proceeds untoned |
| State file unreadable, or holds an unknown tone name | Roll fresh; do not fail |
| State file holds the literal value `__off__` | On `resume`/`clear`/`compact`: emit nothing, exit 0, session stays untoned. On `startup`: ignore it and roll fresh, same as any other source |
| `session_id` absent from stdin | Fall back to a single state file keyed by working directory |
| Tone file missing its frontmatter `name` | Skip that file when building the catalogue |

Every failure path exits 0. A hook belonging to a fun plugin must never degrade a session.

## Verification

- `claude plugin details tone-roulette` reports 8 output styles, 1 hook and 1 skill.
- The handler script, run directly with crafted stdin JSON, emits valid JSON for each
  matcher value — asserted with `jq`, not by eye.
- Rolling repeatedly across many runs yields more than one distinct tone. This proves the
  roll is real and not a fixed pick.
- `clear` and `compact` with an existing state file return the *same* tone the state file
  holds.
- Every tone file contains the ground-rules block byte-for-byte.
- Live check, needs a human: enable the plugin, start a session, confirm the announcement
  appears and the tone holds, and confirm `/output-style` lists all eight.

## Known limitations

- **Subagents do not inherit the tone.** Forks inherit the parent's system prompt; other
  subagents run their own. Implementer and reviewer agents answer in the default voice.
  This is not fixable from a plugin, and is documented in the README.
- **Disabling the plugin mid-session does not retract the tone.** Text already injected is
  in the conversation history. `/tone off` is the mid-session path; disabling the plugin is
  the between-sessions path.
- **Only `startup` rolls.** `resume`, `clear` and `compact` all re-inject the stored tone
  from the state file without re-rolling. `fork` is deliberately excluded from the matcher:
  if a fork gets a new `session_id` the handler would find no state file and roll a second,
  different tone with its own announcement; if a fork shares the parent's `session_id` the
  resume path would re-emit the same `additionalContext` into a context that already
  contains it. Both outcomes are wrong, so `fork` never fires the hook.

## Out of scope

Dialect and language are orthogonal to tone and are not addressed here. Claude Code already
has a `language` setting for the former.
