# agent-operations

Rules for running more than one agent over one repository, and for a session that has
outgrown its own transcript.

## What it's for

**`parallel-sessions`** — a branch is not isolation, a worktree is. Two agents sharing one
checkout share one working directory and one index; a subagent that stages with
`git add -A` can sweep an unrelated in-progress build into its own commits. Covers pushing
before you dispatch (an agent's worktree only sees what's on the remote), disjoint file
ownership, and never reverting a file that changed under you without accounting for the
change first.

**`writing-plans-and-dispatches`** — what belongs in a plan you hand to another agent.
Code written into a plan reads as authoritative and gets transcribed faithfully even when
it's wrong; a seven-task plan with complete code for every task produced fourteen real
defects, four of them silent-corruption bugs. Prefer specifying the contract — names,
signatures, the failure the code must prevent — to specifying the body, and label anything
you do include as a proposal, not a requirement.

**`recovering-a-session`** — when `--resume` fails, hangs, or errors because a transcript
outgrew the window it has to replay into. The file usually isn't corrupt, just too big;
the skill covers how to see it coming and how to cut a new session file at a safe point
without losing the thread of work.

Each skill fires from its own frontmatter `description` — see `skills/` for the full text
and the failures each one traces back to.

## Install it if

You dispatch subagents or run git worktrees. Useless if you work alone in one session.
