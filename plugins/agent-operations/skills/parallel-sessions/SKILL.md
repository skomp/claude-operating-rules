---
name: parallel-sessions
description: "Read before you dispatch a subagent, an implementer, or a review/verification agent; before you create a git worktree or rely on a branch for isolation; when a request says another session or agent is working in this repo right now; before you stage or commit while an agent is live; when a file changed under you and you cannot account for the change; and when two sessions have already collided and the history is interleaved."
---

# Parallel Sessions — Operating Rules

Two agents in one checkout share one working directory and one index. A dispatched
subagent, an implementer, a reviewer, and your human partner editing a file by hand
are all *live sessions*. No rule below softens because the other party is "only a
subagent".

## 1. A branch is not isolation. A worktree is.

When a request says another session/agent is working in this repo right now
("while you are working on X on another branch..."), **use a git worktree**, not
just a new branch in the shared checkout.

This has already gone wrong once (an Android project, 2026-07-31). Both sessions
were in the same checkout; the other one committed with `git add -A`-style staging
and swept an entire in-progress Android build into five unrelated commits with
misleading messages. Nothing was lost, but the history is now interleaved and only
your human partner can decide how to untangle it.

## 2. Before dispatching: push, or name the local-only path

Worktree isolation defaults to branching from `origin/<default-branch>`, so **any
commit you have not pushed is invisible to the agent you just dispatched.** Seen on
an Android project, 2026-08-03: a spec and a plan were committed locally and the
implementer's worktree had neither, so it re-created both from the untracked
working copy and committed duplicates. Harmless there because the content was
identical, but an agent told to "read the approved spec at <path>" can just as
easily find nothing and improvise.

So: **push, or say explicitly that the file is local-only and give its absolute
path in the parent checkout.** Pushing is better — the agent's `git log` then shows
the history its task sits on top of.

### Knowing this rule does not protect you. Run the check.

*Recorded from a concurrent session, 2026-09-12. Not yet reviewed by the session that lived it.*

A Python API client, 2026-09-12: this rule was in front of the session and it was
broken anyway, twice in one turn. A push, then a merge of an agent's branch, then two
more commits, then two fresh agents dispatched — with no re-check, because the push was
remembered. Both got a base four commits stale. One was told "203 tests pass on `main`";
it saw **155**, plus an `emit.py` missing 156 lines and an assigned test file that
**did not exist yet**.

It caught this itself and fast-forwarded. Had it not, it would have written a guard
against a module four commits out of date, and that work would have been merged. The
other agent was mid-flight and had to be messaged with a correction.

The failure mode is specific and worth naming: **"I pushed" decays into "I am pushed"**.
Every commit you make afterwards silently invalidates it, and a merge you perform to
land an agent's work is itself a commit. The gap is widest exactly when you are most
productive.

*Recorded from a concurrent session, 2026-09-12. Not yet reviewed by the session that lived it.*

So make it mechanical, immediately before **every** `Agent` call that gets a worktree —
not once per session:

```sh
git fetch -q origin
git symbolic-ref -q refs/remotes/origin/HEAD >/dev/null || git remote set-head origin --auto
base=$(git symbolic-ref --short refs/remotes/origin/HEAD) &&   # e.g. origin/main
  git rev-list --left-right --count "$base...${base#origin/}" # the RIGHT number MUST be 0
```

The `fetch` is the part that does the work. Without it the command reads a local
`origin/…` ref that may be days old, prints `0 0`, and clears a base that is stale —
a probe that cannot report the condition it exists to catch. Deriving `base` rather
than hardcoding `main` keeps it working in a repository whose default branch is not
`main`.

`refs/remotes/origin/HEAD` is written by `git clone`, so it can be absent in a
repository created another way; the `set-head --auto` line repairs it in place. If that
fails with `Cannot determine remote HEAD`, the remote itself reports no default — name
the branch once by hand: `git remote set-head origin <branch>`.

**Only the right-hand number blocks the dispatch.** Non-zero on the right is local
commits that are not pushed: push before dispatching. Non-zero on the left is commits on
the remote that are not pulled — a different situation with a different remedy. The
agent's worktree branches from `origin/<default>` and gets those commits; the local
checkout does not, so the sha and the test count quoted in the dispatch describe a
different tree from the one the agent will see. Pull, re-run the check, then quote the
numbers.

Dispatching two agents in one message counts as two dispatches from one base — check
once, but check *then*, after any merge you just did.

And in the dispatch itself, **state the base commit and the expected test count
together**: "branched from `origin/main` at `<sha>`, where `N` tests pass". Those two
facts cross-check each other — an agent that sees a different count knows instantly that
something is wrong, which is exactly how this was caught. A bare test count with no sha
is a number the agent cannot verify; a bare sha is one it has no reason to question.

## 3. While an agent is live

**Never `git add -A` or `git commit -a`.** That sweeps whatever the agent has
written **so far** into your commit — including a file caught mid-write, which
commits as syntactically broken. Near-miss on a GPU renderer project, 2026-08-18:
docs were committed with `git add -A` while an implementer agent owned `frag.glsl`;
it happened not to have written yet, so nothing broke, but the race was real and
silent.

- Stage **explicit paths you own**: `git add DEV_NOTES.md TODO.md`.
- **Assign disjoint file ownership when dispatching**, and say in the prompt which
  files are the agent's, so "paths you own" is unambiguous on both sides.
- Run `git status --short` before committing; confirm nothing unexpected is staged.

*Recorded from a concurrent session, 2026-09-12. Not yet reviewed by the session that lived it.*

**Explicit staging is not enough, and knowing the rule is not enough.** A
tutorial-authoring project, 2026-09-12: three explicit paths were staged and committed.
The commit contained **ten files** — a live agent's scanner rewrite, its test file and a
new fixture rode along, under a message describing only the three.

The mechanism is worth stating plainly, because "never `git add -A`" reads as if explicit
staging were the protection: **`git commit` commits the whole index, not the paths you
just added.** Your agent's own `git add` writes into that same index. So explicit staging
protects you from what *you* would have swept in; it does nothing about what someone else
already staged. The only thing that catches it is looking at the index immediately before
committing:

```sh
git status --short          # or: git diff --cached --name-only
```

Two consequences:

- **Check between `git add` and `git commit`, every time an agent is live** — not at the
  start of the turn. The agent can stage in the seconds between.
- **When it happens, do not rewrite the commit.** Rule 5 holds even though the message is
  now wrong and the fix looks trivial: a live agent's work is in there. Verify the content
  at `HEAD` is correct, leave the history alone, and add a follow-up commit that says what
  the earlier one actually contains. A misleading message is cheap to correct in a note and
  expensive to correct with a rebase.

**Your own review agents count.** An Android project, 2026-08-03: a reviewer was
checking one commit's test counts when a commit from the dispatching session landed
underneath it, so its first full-suite run reported the wrong numbers for the commit
under review. It recovered by pinning a `git archive <sha>` copy and said so — but a
reviewer that had NOT noticed would have reported confidently wrong figures, and you
would have believed them.

So while a reviewer is out, either leave the tree alone or tell it which commit to
pin. **Prefer telling it to pin** — waiting serialises work that has no reason to be
serial. Findings quoting `file:line` are read against a moving tree too, so a review
dispatched on a commit must name that commit.

## 4. A session's input is its own chat, never another session's

A tutorial-authoring project, 2026-09-12. A design question that belonged to *one*
session's thread — how a quality rubric should score one field — got asked of the
human partner in the *other* session, because that session disagreed with the answer
the first one had recorded. They then answered the same topic twice, and their
decision reached the first session's chat second-hand.

**The rule: do not ask questions about session A's work inside session B.** Each
session's questions belong in that session's chat.

Mechanically:

- **Signals and coordination between sessions: fine.** "Which files do you hold?"
  "I am done, the branch is on main." "I am about to touch X." Those are about the
  sessions, not about the work's direction.
- **Decisions about the work: ask in the session that owns the work.** If a peer's
  thread raises a question about yours, the answer is "that belongs in the other
  session", not a relayed ruling. A peer session is not a channel to your human
  partner, and it is not a second opinion to consult when you dislike the answer you
  were given.
- **Never let a peer's disagreement become a reason to re-ask a settled question
  elsewhere.** That is forum-shopping, and it costs your human partner the same
  decision twice with less context each time.
- **If a decision does reach you second-hand, record the provenance** and say so
  plainly, so it can be corrected in one line if it arrived distorted.

The tell that it has gone wrong: your human partner reads a conversation between two
of their own sessions and has to reconstruct who decided what. They should never have
to do that.

## 5. When a collision happens anyway: do NOT rewrite history

No `reset`, no `rebase`, no `checkout` — the other session's uncommitted work is
live and you will destroy it. Instead: work out exactly which files are yours,
commit only those, leave everything else untouched, and report the collision.

That holds for single files too, and it cost real work on a GPU renderer project,
2026-08-21. An implementer mid-task found `skel/frag.glsl` dirty with an
`ALPHA .15 -> 0.4` edit it could not account for — no live process, no traceable
source in its own session, file perms matching the project's own atomic writer. It
**reverted it with `git checkout`** and carried on.

Almost certainly that was the owner using the very feature the branch had just
shipped: drag a slider, press "apply to initializer". The editor working exactly as
designed, and an agent threw the result away.

The tell that it was legitimate was right there in the report — perms consistent
with the project's writer, and every "the suite never wrote this file" guard still
passing, which together say *something else wrote it deliberately*. **An agent that
reasons that far and then reverts anyway has diagnosed the situation and drawn the
opposite conclusion, which is worse than not noticing.**

The rule against reverting a collision lived in a human's head. It never reached the
*dispatch*, which is where it had to be. Hence section 6.

### A rebase rewrites other people's refs, including their backups

This repository, 2026-09-13. Two sessions were cleaning commit metadata out of one
checkout. One took backup branches before rewriting — the standard move that makes a
rewrite reversible. The other then ran `git rebase --onto origin/main <old-base>
<its-branch>` and **moved two of those backup refs off the commits they existed to
preserve**, onto its own new tip.

That is not a bug. `rebase.updateRefs` force-updates any branch pointing at a commit
being rebased, and here it was `true` in `~/.gitconfig` — **global, so every
repository and every session on the machine**, not something one project opted into.
The only warning is a line in the rebase output that scrolls past.

The cruel part is the selection effect: **a backup ref is, by definition, a ref
pointing into the range you are about to rewrite.** These are the refs
`--update-refs` is most likely to move, and they are the ones whose whole job is to
still be there afterwards.

Recovery worked only because the commit was also on the remote. A backup that exists
solely as a local branch, in a checkout where someone else may rebase, is not yet a
backup.

So, before rebasing in a shared checkout:

```sh
git config --get rebase.updateRefs        # true is the dangerous case
git for-each-ref --contains <base>        # every ref the rebase may move
```

Six refs were in range here. If the list holds refs you do not own, either pass
`--no-update-refs` for that rebase or tell the session that owns them first.

**And do not reach for a tag as the safe alternative without checking.** The same
session also took a tag backup, confirmed it existed, and found it gone afterwards —
with no determination of what removed it. `--update-refs` is documented to move
branches, not tags, so the tag "should" have survived; it did not, and an
unverified "should" was one edit away from becoming a rule in this file. Push the
backup, or verify the ref after every rewrite anybody performs.

## 6. Dispatch boilerplate — paste into every agent prompt

Use it every time an agent owns a file a human might also touch. Fill in the file
list; change nothing else.

> **Files you own:** `<explicit paths>`. Do not create, edit, stage or delete
> anything outside that list. Other sessions own the rest of this checkout.
>
> Stage explicit paths you own (`git add <your paths>`). Never `git add -A` or
> `git commit -a`. Run `git status --short` before committing and confirm nothing
> unexpected is staged.
>
> If a file you own changes under you and you cannot account for the change, **stop
> and report it**. Do not revert it, do not stash it, do not `git checkout` it, and do
> not stage it. Quote the diff in your report and continue with the rest of your task
> if you can. An unexplained edit is far more likely to be the owner working than
> corruption, and it is never yours to discard.

For a reviewer or verification agent, add the commit it must measure:

> Pin your measurements to `<sha>` (`git archive <sha>`). The working tree is moving
> under you; any finding you quote as `file:line` must be read against `<sha>`.

## Red flags — stop

| About to… | Do this instead |
|---|---|
| Open a branch in the shared checkout "for isolation" | Create a worktree |
| Dispatch into a worktree with commits unpushed | Push first, or give the absolute path in the parent checkout and say it is local-only |
| `git add -A` / `git commit -a` with an agent live | `git add <explicit paths you own>`, then `git status --short` |
| Wait for a reviewer to finish before committing | Tell the reviewer which commit to pin |
| Revert/stash/`git checkout` a file that changed under you | Stop, quote the diff, report it |
| Ask about session A's work in session B's chat | Ask in the session that owns the work |
| Dispatch without naming the agent's files | Paste the boilerplate above, file list filled in |
