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
| `SessionStart`'s matcher is tested against a `source` field whose observed values are `startup`, `resume`, `clear`, `compact`, `fork` | the binary's `matcherMetadata` for `SessionStart`: `fieldToMatch:"source", values:["startup","resume","clear","compact","fork"]` |
| Hook stdin JSON includes `session_id` | hook documentation embedded in the 2.1.259 binary |
| `systemMessage` displays a message to the user, for all hook events | same |
| `outputStyles` is a valid plugin manifest key | manifest key list in the 2.1.259 binary |
| `force-for-plugin` exists but applies only to plugin output styles | binary carries the guard string `" has force-for-plugin set, but this option only applies to plugin output styles. Ignoring."` |

`commands/*.md` is documented in `example-plugin` as the legacy layout; new plugins should
use `skills/<name>/SKILL.md`. Both load identically.

## Architecture

Two jobs that need different mechanisms:

- **Holding** a tone is what output styles are for. They sit at system-prompt level,
  `/config` → Output style switches between them, and disabling the plugin removes them.
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
├── hooks/hooks.json                  # SessionStart, matcher: startup|resume|clear|compact
├── hooks-handlers/session-start.sh   # roll, persist, announce, inject
├── output-styles/
│   ├── noir-detective.md
│   ├── drill-sergeant.md
│   ├── golden-retriever.md
│   ├── victorian-naturalist.md
│   ├── corporate-bureaucrat.md
│   ├── sports-commentator.md
│   ├── conspiracy-theorist.md
│   ├── medieval-herald.md
│   ├── pirate.md
│   ├── victorian-explorer.md
│   ├── telemarketer.md
│   ├── korinthenkacker.md
│   ├── chain-smoking-defender.md
│   ├── laconic.md
│   └── twenty-questions.md
└── skills/tone/SKILL.md              # /tone, /tone <name>, /tone off, /tone list
```

`force-for-plugin` is deliberately **not** used. It force-applies a single style, which is
the opposite of rolling one, and avoiding it removes the design's only dependency on a field
that could not be confirmed against a working example.

## Data flow

Every tone in the catalogue is also a real Claude Code output style (shipped via the
manifest's `"outputStyles"` key), and Claude Code's own `outputStyle` settings key already
holds a **chosen** style — instantly, via `/config`, with no model turn — and persists it in
a settings file rather than the transcript, so it survives compaction and restart on its own.
The handler's own state file only ever needs to hold one thing beyond that: a **rolled** tone,
since nothing native can pick one at random. So before anything else, on every source
(`startup`, `resume`, `clear`, `compact` — `fork` never reaches the handler at all, see Known
limitations), the handler checks whether a style has been explicitly chosen:

- **An output style is set** (`outputStyle` is a non-empty value in any settings file the
  handler can read — see "Detecting a chosen style" below) — stand down completely. Print
  nothing, exit 0. The state file is not read, not rolled, not rewritten; Claude Code's own
  mechanism owns the tone for the rest of that setting's life, on every source, not just
  `startup`. This is what stops the two mechanisms fighting: before this check existed,
  picking a style and then hitting `/clear` or letting the context compact would silently
  re-inject whatever the state file still held, reverting the user's own choice.
- **No output style is set**, `SessionStart` fires with a matcher value in its stdin JSON:
  - **`startup`** — roll. Pick a file from `output-styles/` at random, write the chosen tone
    name to the state file, emit `systemMessage` (`"🎲 Tone rolled: <name>"`) and
    `additionalContext` carrying the file body.
  - **`resume` / `clear` / `compact`, with a still-valid tone in the state file** — do not
    roll. Read the state file, re-emit that same tone's `additionalContext`, and also emit a
    `systemMessage` — but worded `"🎲 Tone held: <name>"`, not `"rolled"`, because nothing was
    rolled this run. This is what satisfies requirement 4: compaction can drop the injected
    instruction, so it is re-injected unchanged rather than re-rolled, and the message is kept
    (not dropped) because the user may not remember which tone is active after a `/clear`.
  - **`resume` / `clear` / `compact` emit nothing when the state file holds `__off__`.** This
    token is a legacy artifact: an earlier version of the `/tone off` command wrote it
    instead of deleting the state file, so absence kept meaning "roll" and "off" got its own
    explicit representation. The skill no longer writes it — turning the tone off is now
    `/config` → Output style → Default, which the output-style check above already handles —
    but the handler still honors a leftover `__off__` from a state file written before this
    change, or from manual editing. `startup` alone ignores a leftover `__off__` and always
    rolls a fresh tone — switching off was always per-session, and it must never leak into a
    new one.

### Detecting a chosen style

`outputStyle` is a plain top-level string key that can live in any Claude Code settings file.
The handler checks the same precedence order Claude Code itself applies (highest first),
stopping at the first file that actually sets the key:

1. Managed settings (organization policy) — the file-based form only:
   `/Library/Application Support/ClaudeCode/managed-settings.json` on macOS,
   `/etc/claude-code/managed-settings.json` on Linux. An MDM profile (macOS) or an
   HKLM/HKCU registry value (Windows) is not a file this script can read, and neither is a
   `claude --settings` CLI override for this session — see Known limitations.
2. Project local settings (`.claude/settings.local.json`) — the file `/config` itself writes
   to.
3. Shared project settings (`.claude/settings.json`).
4. User settings (`~/.claude/settings.json`).

`$CLAUDE_PROJECT_DIR` is what Claude Code itself sets in a command hook's environment for the
project root (confirmed by reading the installed `claude` binary's strings: hook subprocesses
are spawned with `CLAUDE_PROJECT_DIR` already in their env); `$PWD` is the fallback for a
standalone or test invocation where it is unset.

The extraction is the same grep+sed pull already used for `session_id`/`source`, not `jq` or
`python` (Global Constraint 3 forbids both in the handler). It is exact, not a heuristic:
Claude Code constrains an `outputStyle` value to `^[a-z][a-z0-9_-]*$` (a plugin style's
catalogue name — confirmed against the same schema string that validates plugin manifest
names in the 2.1.259 binary) or one of five capitalized built-in names (`Default`,
`Proactive`, `Concise`, `Explanatory`, `Learning`), so the value can never contain a quote or
span multiple lines, and every real-world settings file checked against this writes one key
per line.

The hook's own stdin JSON was checked first and does **not** carry the active output style at
all (confirmed against the `SessionStart` schema embedded in the 2.1.259 binary: `session_id`,
`transcript_path`, `cwd`, `prompt_id`, `permission_mode`, `agent_id`, `agent_type`, `source`,
`model`, `session_title`, and three resume/fork-only cache-cost fields — no `outputStyle` or
`output_style` field anywhere), so reading settings files is not a fallback, it is the only
way.

State lives at `~/.claude/tone-roulette/<session_id>`, a single line holding the tone name.
`session_id` comes from the hook's stdin JSON. If the state file is missing when `resume` /
`clear` / `compact` fires, the script rolls a fresh tone rather than failing.

**Pruning stale state files (issue #6).** After a `startup` roll persists, the handler
removes other files directly under the state directory whose mtime is older than 30 days,
via `find <state_dir> -maxdepth 1 -type f -mtime +30 ! -name <this session's file> -exec rm
-f {} +`. This runs only on `startup`, never on `resume`/`clear`/`compact` — those paths only
read state for what may still be a live session, and a prune racing that read is how a live
session loses its tone. The current session's own file is excluded by name and is never
removed regardless of age. Age is the only available signal (session ids are UUIDs; the
handler has no way to ask whether a session ended), and 30 days is generous specifically
because `resume`/`clear`/`compact` never rewrite the state file, so a long-running session's
file keeps its original `startup` mtime for as long as the session stays open.

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
selected natively through `/config` is never seen by the script and so cannot have the
rules prepended to it. That means nineteen copies of the same paragraph, which is a drift
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
| An output style is explicitly set (`outputStyle` in any settings file the handler can read) | Emit nothing, exit 0. Checked first, before the catalogue or the state file, on every source — not only `startup` |
| `output-styles/` missing or empty | Emit nothing, exit 0. The session proceeds untoned |
| State file unreadable, or holds an unknown tone name | Roll fresh; do not fail |
| State file holds the literal value `__off__` | On `resume`/`clear`/`compact`: emit nothing, exit 0, session stays untoned. On `startup`: ignore it and roll fresh, same as any other source |
| `session_id` absent from stdin | Fall back to a single state file keyed by working directory |
| Pruning the state directory fails (permission denied, race, etc.) | Swallowed (`2>/dev/null`); the session's own roll/announce/inject already completed and is unaffected |

Every failure path exits 0. A hook belonging to a fun plugin must never degrade a session.

## Verification

- `claude plugin details tone-roulette` reports 19 output styles, 1 hook and 1 skill.
- The handler script, run directly with crafted stdin JSON, emits valid JSON for each
  matcher value — asserted with `jq`, not by eye.
- Rolling repeatedly across many runs yields more than one distinct tone. This proves the
  roll is real and not a fixed pick.
- `resume`, `clear` and `compact` with an existing state file return the *same* tone the
  state file holds.
- Every tone file contains the ground-rules block byte-for-byte.
- Live check, needs a human: enable the plugin, start a session, confirm the announcement
  appears and the tone holds, and confirm `/config` → Output style lists all nineteen.

## Known limitations

- **A `claude --settings` CLI override and MDM-delivered policy (a macOS configuration
  profile, or a Windows registry value) are invisible to the stand-down check.** Both can set
  `outputStyle` at a higher precedence than every file the handler reads, but neither is a
  file the handler reads: a CLI override is never written to disk or exposed to a hook's
  stdin or environment, and MDM policy lives in a plist or the registry, not
  `managed-settings.json`. In both cases the handler can wrongly conclude no style is chosen
  and roll over one that in fact takes effect. This is a narrow, rare gap — most machines
  running this plugin have neither in play — documented rather than silently accepted.
- **The standalone `/output-style` command is gone.** It was deprecated in Claude Code
  v2.1.73 and removed in v2.1.91 (confirmed against the installed 2.1.259 binary: running it
  now prints "`/output-style` moved → Output style in `/config`" and does nothing else).
  `/config` → **Output style** is the current way to choose or list a style with no model
  turn; this plugin's skill and README point at `/config`, not at the old command, for
  exactly that reason. A user on an older release where `/output-style` still works can use
  it interchangeably — the `outputStyle` settings key the handler checks is the same either
  way.
- **Subagents do not inherit the tone.** Forks inherit the parent's system prompt; other
  subagents run their own. Implementer and reviewer agents answer in the default voice.
  This is not fixable from a plugin, and is documented in the README.
- **Disabling the plugin mid-session does not retract the tone.** Text already injected is
  in the conversation history. `/tone off` is the mid-session path; disabling the plugin is
  the between-sessions path.
- **Only `startup` rolls unconditionally.** `resume`, `clear` and `compact` re-inject the
  stored tone from the state file without re-rolling *when the state file names a still-valid
  tone*. When it doesn't — missing, unreadable, or naming a tone no longer in the catalogue —
  they roll fresh exactly as `startup` would (see Error handling); `resume` with no state file
  is not an error case, it is this same fallback. `fork` is deliberately excluded from the
  matcher:
  if a fork gets a new `session_id` the handler would find no state file and roll a second,
  different tone with its own announcement; if a fork shares the parent's `session_id` the
  resume path would re-emit the same `additionalContext` into a context that already
  contains it. Both outcomes are wrong, so `fork` never fires the hook.
- **Tone adherence depends on the model.** Tested on Haiku and Sonnet: on Sonnet the tone
  lands reliably; on Haiku it frequently does not, even though the hook still fires and a
  tone is still rolled and written to the state file — the mechanism works, the model just
  doesn't follow the injected instruction. Other models have not been tested.
- **Four tones perform doubt or pessimism** (`negative-nancy`, `hedging-hannah`,
  `second-guess-sid`, `nervous-nellie`), and their hedging is a speech register, not a
  confidence signal — the underlying assessment is unchanged, and each file's `## Voice`
  section says so explicitly. A reader who does not know this can mistake the performance
  for the substance: "I think the tests maybe passed?" reads as uncertainty about the test
  result, when the result itself was never in doubt. Anyone who needs the assistant's actual
  confidence should ask directly or switch tones with `/tone <name>`.

## Out of scope

Dialect and language are orthogonal to tone and are not addressed here. Claude Code already
has a `language` setting for the former.
