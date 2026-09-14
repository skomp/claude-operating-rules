# evidence-discipline

Two rules about trusting your own checks, learned from failures that shipped anyway.

## What it's for

**`verifying-claims`** — before you report that something is absent, closed, safe, healthy,
or not-reproducible: a check that cannot fail proves nothing, and a negative from one
instrument is evidence about the instrument, not the property you care about. Run the same
probe against a known-positive input first and confirm it fires; guard against an empty
needle; distinguish "refused" from "failed earlier" by reading the actual error.

**`completing-a-correction`** — the moment a fix lands: a ruling is not complete when the
code is fixed, it's complete when every artefact carrying the same claim is fixed — spec,
plan, README, CLAUDE.md, tests, dispatch prompts, and any comment restating the value.

Neither skill is specific to Claude Code. Both fire from their own frontmatter
`description` — see `skills/` for the full text and the failures each one traces back to.

## Install it if

Always. This is the one plugin in the marketplace with no situational caveat.
