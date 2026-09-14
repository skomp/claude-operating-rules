# ticket-craft

One skill, one job: decide where work gets written down, and word it in
ASD-STE100 Simplified Technical English.

## What it's for

**`tracking-work`** — two questions at one moment. *Where it goes*: task tracking is a
per-project choice (GitHub issues, preferred in general, or a `TODO.md` for very small
projects); check the project's `CLAUDE.md` for an existing preference, and if there isn't
one, ask before writing anything and record the answer for next time. Every issue Claude
creates carries the `created-by-claude` label. *How it's worded*: every ticket — issue
titles and bodies, sub-issues, user stories, acceptance criteria, `TODO.md` entries — uses
STE100: one instruction per sentence, active voice with a named actor, one word per
meaning, simple approved verbs, no noun stack longer than three words. Identifiers, file
paths, commands, error strings and API names stay verbatim even where that fights the
style — precision wins over simplification there.

See `skills/tracking-work/SKILL.md` for the full rule set.

## Install it if

You want STE100 enforced on every ticket. Deliberately packaged alone, separate from
`evidence-discipline` and `agent-operations`, so wanting the verification or coordination
rules never drags this one in too.
