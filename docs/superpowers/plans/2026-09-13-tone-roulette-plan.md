# tone-roulette — implementation plan

**Spec:** `docs/superpowers/specs/2026-09-13-tone-roulette-design.md` (the binding authority;
this plan argues from it)
**Branch:** `worktree-dialect-plugin`
**Repo:** `skomp/claude-operating-rules`

> **Superseded during implementation — controller ruling R3:** every matcher value below
> written as `startup|clear|compact` (lines 34, 46 and 133 as originally written) was
> corrected to `startup|resume|clear|compact`. Task 2's Step 0 probe found that the binary's
> `matcherMetadata` for `SessionStart` lists `source` values `startup`, `resume`, `clear`,
> `compact`, `fork` — a fifth value, `resume`, that this plan did not anticipate. R3 added
> `resume` to the shipped `hooks.json` so the spec's documented resume behaviour (re-inject
> the stored tone) is enforced by the hook actually firing, rather than depending on
> unverified session-history replay; `fork` stays excluded. This plan is left as originally
> written below — the correction lives in the spec
> (`docs/superpowers/specs/2026-09-13-tone-roulette-design.md`) and in the shipped
> `hooks/hooks.json`, not here.

> **Superseded since this plan was written:** the two references below to the standalone
> `/output-style` command — "the other way to switch" in the `/tone` skill task, and
> "confirming... `/output-style` lists all eight" in Verification — describe a command that
> was deprecated in Claude Code v2.1.73 and removed in v2.1.91. Choosing or listing a style
> now lives in `/config` → Output style. This plan's text is left as originally written
> below — it is a historical record of what was true when the plan was drafted, not a live
> instruction — and the correction lives in the spec
> (`docs/superpowers/specs/2026-09-13-tone-roulette-design.md`, Known limitations).

## Global constraints

1. **No tone text exists in two places.** Each tone lives in exactly one file under
   `plugins/tone-roulette/output-styles/`. The hook handler reads those same files. Any
   second catalogue, lookup table or hardcoded tone list in the handler is a defect.
2. **Every failure path exits 0.** The hook belongs to a fun plugin and must never degrade
   or block a session. A handler that exits non-zero, or emits invalid JSON, is a defect.
3. **The handler must not depend on `jq`, `python`, or any non-POSIX tool being installed.**
   It runs on a user's machine with unknown tooling. `bash` + coreutils only. `jq` may be
   used in *tests*, never in the handler.
4. **The ground-rules block is byte-identical across all tone files.** Its exact text is in
   Task 1 and is the single source. A test asserts this.
5. **Follow the repository's existing plugin conventions**, read from
   `plugins/ticket-craft/.claude-plugin/plugin.json` and `.claude-plugin/marketplace.json`:
   same manifest field set, same author/homepage/repository/license shape, version `0.1.0`.
6. Prose in shipped Markdown follows the repo's register — plain, declarative, no hype.

## Already measured — do not re-derive

Every line below was verified against Claude Code 2.1.259 and shipped Anthropic plugins on
this machine. Treat these as facts; do not spend turns rediscovering them.

| Fact | Where it was verified |
|---|---|
| `hooks/hooks.json` at the plugin root is auto-discovered. `plugin.json` needs **no** `hooks` key | `~/.claude/plugins/marketplaces/claude-plugins-official/plugins/learning-output-style/` — its `plugin.json` has only name/version/description/author, yet its hook fires |
| Hook entry shape | `{"hooks":{"SessionStart":[{"matcher":"...","hooks":[{"type":"command","command":"bash \"${CLAUDE_PLUGIN_ROOT}/hooks-handlers/session-start.sh\""}]}]}}` |
| `matcher` accepts alternation | `"startup\|clear\|compact"` — `superpowers/6.3.0/hooks/hooks.json` |
| Handler stdout contract | `{"hookSpecificOutput":{"hookEventName":"SessionStart","additionalContext":"..."}}` — `learning-output-style/hooks-handlers/session-start.sh` |
| `systemMessage` is a **top-level** output field, documented as "Display a message to the user (all hooks)" | hook documentation embedded in the 2.1.259 binary |
| Hook **stdin** JSON contains `session_id` | same |
| `outputStyles` is a valid plugin manifest key | manifest key list in the 2.1.259 binary |
| Skill frontmatter fields | `name`, `description`, `allowed-tools`, `argument-hint`, `model`, `disable-model-invocation`, `user-invocable` |
| `commands/*.md` is the **legacy** layout; `skills/<name>/SKILL.md` is preferred and loads identically | `example-plugin/commands/example-command.md` says so in its own body |

**Unverified, and deliberately unused:** `force-for-plugin`. It exists as a string in the
binary but no shipped plugin uses it. Do not use it.

**Not yet measured — Task 2 must establish it:** the exact stdin field name carrying the
matcher value (`startup` / `clear` / `compact`). Task 2's first step is a probe; do not
guess it.

---

## Task 1 — Tone catalogue

**Files you own:** `plugins/tone-roulette/output-styles/*.md`,
`plugins/tone-roulette/tests/test-tone-files.sh`

Create eight output-style files. Each is Markdown with YAML frontmatter.

**Contract — frontmatter:** exactly `name` and `description`. `name` must equal the filename
without `.md`. No other keys — specifically not `force-for-plugin`.

**Contract — body structure:** a `## Ground rules` section whose content is the block below
**byte-for-byte**, then a `## Voice` section carrying the tone-specific instruction.

The ground-rules block, verbatim and identical in all eight files:

```
This tone governs conversational prose only — what you say to the user in chat.

It never touches code, identifiers, comments, commit messages, pull request descriptions,
issue titles and bodies, file contents, shell commands, or tool arguments. Those stay in
normal professional English.

The tone never costs accuracy. If staying in character would require vagueness, hedging or
invention, drop the voice for that sentence and be plain. Being right outranks the bit.
```

**The eight tones** (filename → the character to write):

| File | Voice |
|---|---|
| `noir-detective.md` | World-weary 1940s private eye. Short sentences. The codebase is a city that let you down |
| `drill-sergeant.md` | Barking, clipped, relentless. Addresses the user as a recruit. Never cruel, always loud |
| `golden-retriever.md` | Boundless delight. Everything is the best news. Genuinely helpful, exhaustingly happy |
| `victorian-naturalist.md` | Observing code as exotic fauna. Latin binomials, field-journal cadence, gentle wonder |
| `corporate-bureaucrat.md` | Committee language, passive voice, process references. Deadpan, never breaks character |
| `sports-commentator.md` | Live play-by-play, present tense, rising excitement over mundane events |
| `conspiracy-theorist.md` | Everything connects, meaningfully. Sees patterns in the dependency graph. Paranoid about `node_modules`, never about people |
| `medieval-herald.md` | Proclamation register. Announces test results as decrees from the realm |

Each `## Voice` section is roughly 80–150 words: what the register sounds like, two or three
concrete verbal habits, and one explicit "even in this voice, do X plainly" line. Write them
to be funny when read, not merely labelled — this plugin's whole value is that the tones
land.

**Tests** — `tests/test-tone-files.sh`, POSIX sh or bash, exits non-zero on failure:

1. Exactly eight `.md` files exist in `output-styles/`.
2. Every file's frontmatter `name` equals its basename without `.md`.
3. Every file contains the ground-rules block byte-for-byte. Extract the block once from a
   constant in the test and compare; do not re-type it per file.
4. No file contains the string `force-for-plugin`.
5. Every file has a non-empty `## Voice` section.

**Done when:** `bash plugins/tone-roulette/tests/test-tone-files.sh` passes and prints what
it checked.

---

## Task 2 — Manifest, hook and handler

**Files you own:** `plugins/tone-roulette/.claude-plugin/plugin.json`,
`plugins/tone-roulette/hooks/hooks.json`,
`plugins/tone-roulette/hooks-handlers/session-start.sh`,
`plugins/tone-roulette/tests/test-handler.sh`

**Step 0 — probe, before writing the handler.** The stdin field carrying the matcher value is
not yet measured. Determine its real name rather than guessing: inspect the hook
documentation strings in the Claude Code binary, which on a local npm install sits at
`<npm root>/@anthropic-ai/claude-code/bin/claude.exe` — resolve it with
`readlink -f "$(command -v claude)"` rather than hardcoding a path
(`strings -n 6 <binary> | grep -n 'SessionStart' | cut -c1-300`, and search near the
`"session_id": "abc123"` example), and read any `SessionStart` handler shipped under
`~/.claude/plugins/marketplaces/`. **Write what you find into your report**, including the
case where the field does not exist. If it genuinely cannot be established, implement the
documented fallback: treat "state file exists for this session" as meaning resume/compact,
and "no state file" as meaning roll. That fallback is correct behaviour either way — which is
why it is safe to ship without the field.

**`plugin.json` contract:** repo-conventional fields (see Global Constraint 5) plus
`"outputStyles": "./output-styles/"`. Name `tone-roulette`, version `0.1.0`. No `hooks` key —
`hooks/hooks.json` is auto-discovered.

**`hooks.json` contract:** one `SessionStart` entry, matcher `startup|clear|compact`, running
`bash "${CLAUDE_PLUGIN_ROOT}/hooks-handlers/session-start.sh"`. Shape is in the measurements
table above.

**`session-start.sh` contract:**

- Reads the hook JSON from stdin.
- Extracts `session_id` **without `jq`** (Global Constraint 3) — a `sed`/`grep` extraction of
  the JSON string field is sufficient and is what the constraint intends.
- State file: `${HOME}/.claude/tone-roulette/<session_id>`, one line, the tone name. Create
  the directory if absent. If `session_id` cannot be extracted, key the file on a sanitised
  `$PWD` instead.
- **Roll path** (no usable state, or the recorded tone no longer exists in the catalogue):
  pick uniformly at random from `output-styles/*.md`. Use `$RANDOM` or `/dev/urandom`; do not
  depend on `shuf` being present. Write the chosen name to the state file.
- **Resume path** (state file names a tone that exists): use it unchanged. Do not re-roll.
- Emits a single JSON object on stdout containing both `systemMessage` (a one-line
  announcement naming the tone, e.g. a die emoji plus `Tone rolled: noir detective`) and
  `hookSpecificOutput.additionalContext` (the chosen file's body with its YAML frontmatter
  stripped).
- **JSON-escapes** the injected body. This is the sharpest edge in the task: tone files
  contain quotes, backslashes, newlines and em-dashes, and an unescaped body produces invalid
  JSON that silently breaks the hook. Escape `\` and `"` and encode newlines as `\n`, using
  shell text processing only.
- Exits 0 on **every** path, including missing directory, empty catalogue, unreadable state
  file, and absent `session_id`. On a fatal problem it prints nothing and exits 0.

**Tests** — `tests/test-handler.sh`. Uses `jq` for assertions (allowed in tests; forbidden in
the handler). Each test feeds crafted stdin and a `HOME` pointed at a temp directory, so no
test ever writes to the real `~/.claude`:

1. Output is valid JSON for a roll (`jq . >/dev/null`).
2. Output carries a non-empty `.systemMessage` naming a real tone from the catalogue.
3. `.hookSpecificOutput.hookEventName == "SessionStart"` and `.additionalContext` is
   non-empty.
4. `.additionalContext` contains the ground-rules text and does **not** contain the `---`
   frontmatter delimiter or the `name:` key.
5. **Randomness is real:** run the roll 60 times with fresh state each time and assert at
   least three distinct tones appear. (Chosen so a correct implementation effectively never
   fails, while a fixed pick always does.)
6. **Resume does not re-roll:** with a state file naming a known tone, twenty runs all return
   that same tone.
7. **Stale state recovers:** a state file naming a tone that does not exist causes a fresh
   roll rather than an error or empty output, and rewrites the state file.
8. Empty `output-styles/` directory → no stdout, exit code 0.
9. Malformed stdin (not JSON, and empty) → exit code 0.
10. A tone file containing `"` , `\` and a literal newline round-trips: the emitted JSON
    parses and `.additionalContext` reproduces the body exactly. Build this fixture in the
    test's temp directory; do not add a joke tone file to the shipped catalogue for it.

**Done when:** `bash plugins/tone-roulette/tests/test-handler.sh` passes, and the report
states what Step 0's probe found.

---

## Task 3 — The `/tone` skill

**Files you own:** `plugins/tone-roulette/skills/tone/SKILL.md`

**Frontmatter contract:** `name: tone`; a `description` that states it is user-invoked for
switching the conversational tone; `disable-model-invocation: true` (a tone plugin that
re-rolls because the model thought it relevant is a bug); `argument-hint` covering the verbs
below; `allowed-tools` limited to what the body actually uses.

**Body contract** — instructions for handling these invocations. The skill body is prose the
model follows; it has no code of its own beyond reading and writing the state file.

| Invocation | Behaviour |
|---|---|
| `/tone` | Report the current tone, read from the state file, and say it was rolled at session start |
| `/tone list` | List the catalogue with each tone's `description` |
| `/tone <name>` | Switch to that tone: adopt it from the next reply on, and update the state file so a later compaction re-injects the new tone and not the old one |
| `/tone roll` | Re-roll at random and announce the result |
| `/tone off` | Stop using any tone for the rest of the session, and remove the state file |

**The subtle requirement:** `/tone <name>`, `/tone roll` and `/tone off` must all keep the
state file in step with the live tone. If they do not, the next compaction re-injects the tone
the user just moved away from. Say this explicitly in the body — it is the failure a reader
of this skill would otherwise cause.

The body must also state, for the user's benefit, that `/output-style <name>` is the other way
to switch, and that disabling the plugin returns to the default tone from the next session.

**Done when:** the frontmatter parses, `disable-model-invocation: true` is present, and all
five invocations are documented with the state-file rule stated.

---

## Task 4 — Register the plugin and document it

**Files you own:** `.claude-plugin/marketplace.json`, `README.md`

**`marketplace.json`:** add a fourth entry following the existing three exactly — `name`,
`source: ./plugins/tone-roulette`, `version: 0.1.0`, `category`, `description`, `author`.
Pick the category that fits a deliberately frivolous plugin; the existing three use
`development` and `productivity`. Change nothing about the existing entries.

**`README.md`:** this repo describes itself as rules learned the expensive way, so a fun
plugin needs placing rather than smuggling in. Required edits:

1. Add a row to the plugin table. The "Install it if" column should be honest that this one
   is a demonstration and a joke, not a rule.
2. Add its install line to the install block.
3. State the three limitations from the spec's "Known limitations": subagents do not inherit
   the tone; disabling the plugin mid-session does not retract it (`/tone off` is the
   mid-session path); only `startup` rolls, so `--resume` keeps the stored tone.
4. Adjust the opening sentence, which currently says "Three Claude Code plugins" and would
   otherwise be wrong.

Keep the existing register. Do not restructure sections this task does not need to touch.

**Done when:** `marketplace.json` parses as JSON and lists four plugins, and no sentence in
`README.md` still claims there are three.

---

## Verification after all tasks

- `bash plugins/tone-roulette/tests/test-tone-files.sh` passes.
- `bash plugins/tone-roulette/tests/test-handler.sh` passes.
- Every JSON file in the repo parses.
- `claude plugin details tone-roulette` reports 8 output styles, 1 hook, 1 skill. This needs
  the marketplace installed and may not be runnable here; if it cannot be run, say so rather
  than reporting it as passed.

**Deferred to the human, and not claimable by any agent:** enabling the plugin in a real
session, seeing the announcement, confirming the tone holds and that `/output-style` lists all
eight. No agent can observe its own output style changing from inside a session.
