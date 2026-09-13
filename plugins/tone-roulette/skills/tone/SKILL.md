---
name: tone
description: User-invoked control for the tone-roulette conversational tone - report the current tone and how it was set, point the user at Claude Code's own /config output-style picker to choose or list tones, or roll a fresh one at random. Only fires on an explicit /tone typed by the user, never on the model's own judgement.
disable-model-invocation: true
argument-hint: "[roll]"
allowed-tools: Read, Bash
---

## What this is

`tone-roulette` rolls a random conversational tone at session start and holds it for the
session by re-injecting it, via a small per-session state file, on every `resume`, `clear`
and `compact`. That is the one thing nothing native can do: nothing else in Claude Code
picks a tone at random.

Choosing a tone deliberately is a different job, and Claude Code already does it — every
tone in this plugin's catalogue is a real Claude Code output style, shipped through the
plugin's manifest. `/config`, under **Output style**, lists and switches between all of them
(built-in styles and every installed plugin's styles together) with no model turn at all,
and the choice is written to a settings file, so it survives `/clear` and restart on its own
— nothing per-session to re-inject. Once you have chosen a style that way, the `SessionStart`
hook detects it and stands down entirely: it never rolls and never re-injects over your
choice again, for the rest of that setting's life.

This skill is the user's way to inspect the current tone, or to roll a fresh one at random.
For everything that is "choose a specific tone" or "see the full list," it points at
`/config` rather than re-implementing a slower copy of what `/config` already does instantly.

Never invoke this skill on your own initiative. It fires only when the user types `/tone`
themselves.

## Where things live

**The catalogue.** Tones are the `.md` files in the plugin's `output-styles/` directory —
`${CLAUDE_PLUGIN_ROOT}/output-styles/*.md` (fall back to the `output-styles/` directory next
to this skill's plugin root if that variable is unset). Each file's frontmatter has `name`
and `description`; the body has a `## Ground rules` section (shared, prose-only, byte-identical
across every tone) and a `## Voice` section (the tone-specific instructions). `/tone roll` is
the only verb that still needs to enumerate this directory.

**The state file.** `${HOME}/.claude/tone-roulette/<session_id>`, a single line holding
exactly the tone name and nothing else. This is the *same* file the `SessionStart` hook reads
and writes — it is what makes `resume`, `clear` and `compact` re-inject a *rolled* tone
instead of rolling a new one. It has never held anything but a rolled tone's name (or the
legacy `__off__` token some existing state files may still carry from before this skill
stopped writing it — see `/tone` below).

Determine `<session_id>` the way the hook does: prefer the running session's id, available
in this environment as `$CLAUDE_CODE_SESSION_ID`; if that is unset, fall back to the current
working directory sanitised the same way the hook sanitises it — every character outside
`A-Za-z0-9_.-` replaced with `_`. Using any other id talks to the wrong file: a different
session's tone could be misread, or worse, overwritten.

**Whether a tone was chosen.** Claude Code stores an explicitly chosen output style in the
`outputStyle` key of a settings file — `/config` writes it to `.claude/settings.local.json`,
and it can also be set by hand in any settings file. Check, in this order, stopping at the
first file that actually sets a non-empty `outputStyle`:

1. Managed settings — `/Library/Application Support/ClaudeCode/managed-settings.json` on
   macOS, `/etc/claude-code/managed-settings.json` on Linux.
2. `$CLAUDE_PROJECT_DIR/.claude/settings.local.json` (fall back to `$PWD` if
   `$CLAUDE_PROJECT_DIR` is unset).
3. `$CLAUDE_PROJECT_DIR/.claude/settings.json`.
4. `${HOME}/.claude/settings.json`.

If any of these sets `outputStyle`, a tone is **chosen** — report that value, not the state
file, and say tone-roulette is standing down for this session. This is the same check, in the
same order, that `hooks-handlers/session-start.sh` runs before deciding whether to roll; a
`claude --settings` CLI override or an MDM-delivered policy is invisible to both, a known gap
documented in the design spec.

## Invocations

### `/tone` (no argument)

First check whether a tone is **chosen** (see above). If so, report the chosen style's name
and say plainly that it was chosen, not rolled, and that tone-roulette has nothing active
this session because Claude Code's own output-style mechanism owns the tone now.

Otherwise, read the state file. If it holds a real tone name, report it as **rolled**:
say it was rolled at session start unless a `/tone roll` ran earlier in *this* session, in
which case say it was re-rolled mid-session instead (rolled-at-start and rolled-mid-session
are not the same claim). If the state file holds the legacy `__off__` token (left over from
a version of this skill that used to write it), say the tone is off for this session and
point at `/tone roll` or `/config` to pick one. If the state file is missing or empty, say no
tone is currently held and suggest `/tone roll`.

### `/tone roll`

Pick a tone at random from the catalogue — uniformly, using shell randomness (`$RANDOM`, the
same mechanism the `SessionStart` hook uses; nothing depends on `shuf` being installed), not
a choice you make. Adopt it from your next reply on, write it to the state file (replacing
whatever it held), and announce which tone was rolled.

This is the one verb that still does its own work instead of pointing elsewhere: rolling at
random is not something `/config` or any other native command can do, so there is no faster
native path to defer to. It never touches the `outputStyle` setting — a roll is not a choice,
and it must never look like one to the `SessionStart` hook or to `/config`'s picker.

### Choosing, listing, or turning tones off

These are no longer this skill's job — the harness already does them, instantly and with no
model turn, and keeping a slower copy here would just give the two mechanisms something to
disagree about (see "What this is" above). If the user asks for one of these, tell them the
native path directly rather than performing an equivalent action yourself:

- **Switch to a specific tone:** run `/config`, select **Output style**, and pick it from the
  menu (or set `"outputStyle": "<name>"` directly in `.claude/settings.local.json` for the
  same effect without opening the menu). Either way it takes effect from your very next
  message and survives `/clear`, compaction and restart on its own — nothing to hold or
  re-inject.
- **See the full list of tones:** run `/config` and open **Output style** — it lists every
  built-in style and every installed plugin's styles, including this catalogue, together.
- **Turn the tone off / return to the default style:** run `/config`, select **Output
  style**, and choose **Default**.

(The standalone `/output-style` command existed in older Claude Code releases and is
deprecated as of v2.1.73, removed as of v2.1.91 — `/config` is the current path. If a user's
version still has it, `/output-style <name>` / bare `/output-style` / `/output-style Default`
do the same three things even faster; point at whichever actually works for their version.)
