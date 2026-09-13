---
name: tone
description: User-invoked control for the tone-roulette conversational tone - report the current tone, list the catalogue, switch to a named tone, roll a fresh one at random, or turn the tone off for the rest of the session. Only fires on an explicit /tone typed by the user, never on the model's own judgement.
disable-model-invocation: true
argument-hint: "[tone-name|list|roll|off]"
allowed-tools: Read, Bash
---

## What this is

`tone-roulette` rolls a random conversational tone at session start, holds it for the
session, and re-injects the same tone on every `resume`, `clear` and `compact` by reading a
small state file. This skill is the user's way to inspect or change that tone mid-session.
It has no logic of its own beyond reading and writing that one file — everything else is
this prose.

Never invoke this skill on your own initiative. It fires only when the user types `/tone`
themselves.

## Where things live

**The catalogue.** Tones are the `.md` files in the plugin's `output-styles/` directory —
`${CLAUDE_PLUGIN_ROOT}/output-styles/*.md` (fall back to the `output-styles/` directory next
to this skill's plugin root if that variable is unset). Each file's frontmatter has `name`
and `description`; the body has a `## Ground rules` section (shared, prose-only, byte-identical
across every tone) and a `## Voice` section (the tone-specific instructions).

**Enumerate this directory every time you need the list of tones.** Do not hardcode the tone
names in this skill or anywhere else — the catalogue is the only source of truth for what
tones exist, and it can grow without this file changing.

**The state file.** `${HOME}/.claude/tone-roulette/<session_id>`, a single line holding
exactly the tone name and nothing else. This is the *same* file the `SessionStart` hook reads
and writes — it is what makes `resume`, `clear` and `compact` re-inject the held tone instead
of rolling a new one.

Determine `<session_id>` the way the hook does: prefer the running session's id, available
in this environment as `$CLAUDE_CODE_SESSION_ID`; if that is unset, fall back to the current
working directory sanitised the same way the hook sanitises it — every character outside
`A-Za-z0-9_.-` replaced with `_`. Using any other id talks to the wrong file: a different
session's tone could be misread, or worse, overwritten.

## The rule every tone-changing invocation must follow

**`/tone <name>`, `/tone roll` and `/tone off` all change the live tone, and all three must
write that change to the state file before finishing.** The `SessionStart` hook does not know
about a tone change unless the state file says so. If the live tone moves but the state file
still names the old one, the very next `/clear` or context compaction reads the stale file and
silently re-injects the tone the user just moved away from — the switch appears to work and
then quietly reverts. Never report a tone change as complete until the state file has been
updated (or, for `off`, removed) to match.

## Invocations

### `/tone` (no argument)

Read the state file and report the tone it names. If the state file is missing or empty, say
that no tone is currently held (the catalogue may be empty, or nothing has rolled yet) and
suggest `/tone roll`.

Describe how the reported tone came to be held: if this is the first `/tone` invocation of
the session and no `/tone <name>`, `/tone roll` or `/tone off` has run yet, say it was rolled
at session start. If a `/tone <name>` or `/tone roll` ran earlier in this session, say instead
that it was switched mid-session (rolling-at-start and switched-mid-session are not the same
claim — don't say "rolled at session start" for a tone that was actually chosen by a later
`/tone` command).

### `/tone list`

Enumerate the catalogue directory and read each file's frontmatter. Report each tone's `name`
and `description`, one per line. Do not read or repeat the `## Voice` bodies for this — the
frontmatter `description` is enough.

### `/tone <name>`

Treat `<name>` as a catalogue basename (e.g. `noir-detective`). If it does not match any file
in the catalogue, say so and point at `/tone list` rather than guessing a close match.

If it matches: read that tone file, adopt its `## Ground rules` and `## Voice` starting with
your very next reply, and write `<name>` to the state file, replacing whatever it held. Then
confirm the switch to the user. Apply the state-file rule above — the write is not optional.

### `/tone roll`

Pick a tone at random from the catalogue — uniformly, using shell randomness (`$RANDOM`, the
same mechanism the `SessionStart` hook uses; nothing depends on `shuf` being installed), not
a choice you make. Adopt it from your next reply on, write it to the state file, and announce
which tone was rolled. Apply the state-file rule above.

### `/tone off`

Stop applying any tone-roulette voice for the rest of the session — return to plain,
unaffected register from your next reply on — and remove the state file entirely.

Tell the user two things they need to know about this: `/output-style <name>` is the other,
independent way to switch tones (it changes Claude Code's built-in output style directly
rather than going through this state file, so it won't be preserved by the anti-reversion
rule above — prefer `/tone <name>` when the switch needs to survive a later `/clear` or
compaction); and disabling the `tone-roulette` plugin entirely returns to the default tone
starting the next session, not this one.

Also be honest about a limitation of `off` itself: it stops the tone for as long as this
context lives untouched, but the `SessionStart` hook rolls a fresh tone whenever it finds no
state file — so a `/clear` or compaction after `/tone off` starts a new tone rather than
staying off. If the user wants to stay tone-free across a compaction, say that disabling the
plugin is the only path that survives one; `/tone off` is a same-context measure.
