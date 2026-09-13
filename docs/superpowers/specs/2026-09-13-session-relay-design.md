# session-relay — design

**Date:** 2026-09-13
**Status:** approved, not implemented
**Scope:** a fourth plugin in `claude-operating-rules`

## Problem

A project spans several repositories in layers. The tutorail project is the worked
example: a runner that executes tutorials, a repository of tutorial bundles, and a
repository of authoring tools. A fault observed in one layer usually has its cause
in another.

Today a session that finds such a fault has two bad options. It fixes the other
repository itself — which puts two agents in one checkout, the failure
`parallel-sessions` is written about. Or it raises the question in its own chat,
and the human carries the answer by hand between sessions.

`parallel-sessions` §4 already permits coordination between sessions and forbids
carrying decisions between them. It defines no channel for the coordination it
permits. This plugin is that channel.

## Hard preconditions

The protocol refuses to operate unless both hold. A session that cannot satisfy
them says so plainly and does not silently degrade.

1. **One session, one repository.** The session binds to exactly one repository,
   taken from `git remote get-url origin` in the working directory. If there is no
   origin, or the origin is not GitHub, the session is *unbound* and takes no part
   in the protocol.
2. **Work is tracked in GitHub issues.** A project using `TODO.md` cannot
   participate — there is nothing for a peer to read or comment on.

### The teeth

A session may clone and read any peer repository to understand a problem. A session
**must never edit, commit, branch, tag or open a pull request in a repository it is
not bound to.** Work that belongs to another repository becomes an issue filed
against that repository, plus a signal.

Without this rule the protocol is optional: a session that can just fix the other
repository will do so, and the coordination never happens.

## Non-goals

- **Any background behaviour.** No hooks, no polling, no watcher, no registry file,
  no slash command. A session acts under this protocol only when it writes to a peer
  issue, when a peer signals it, or when the human asks it to look. Everything else
  is silence.
- **Noticing issues on its own.** A session does not scan open issues. An issue the
  human files enters the protocol when the human says so in that session's chat,
  which is that session's own input and needs no mechanism.
- **Coordinating across machines.** `SendMessage` reaches only sessions the host
  lists. Beyond that reach the protocol falls back to the human asking.
- **Replacing human review.** The protocol escalates; it does not decide.
- **Carrying discussion anywhere but GitHub.** A session signal carries a reference
  and routing flags. It never carries a question, an answer or an argument.

## Architecture

### Packaging

A new plugin `session-relay`, two skills, no executable parts. It is deliberately
not part of `agent-operations`: that plugin is about many agents inside one
repository, this is one agent per repository across many. Separating them means
installing the relay never drags in worktree rules, and the reverse.

| Skill | Trigger |
|---|---|
| `coordinating-across-repos` | You find a cause that lives in another repository; you are about to edit a repository you are not bound to; you need to open, answer or close a cross-repo thread. Owns the preconditions, the wire format, the signalling rule and termination. |
| `handling-an-inbound-ping` | A peer signals you **with a `relay:v1` envelope**, or the human asks whether there is anything to discuss. Owns the envelope discipline, the ownership guard, the decision rule and the subagent dispatch. It has no opinion on any other message. |

The wire format is defined once, in `coordinating-across-repos`, and referenced by
the other. Two copies of one format is the failure `completing-a-correction`
describes.

### The signalling rule

**A signal is emitted only immediately after this session writes to an issue, and
only when that write needs something back.** There is no other reason to signal, and
no other way to be signalled.

The consequence is strict alternation. Session `a` is bound to `ra`, session `b` to
`rb`:

| Step | Session | Writes | Signals |
|---|---|---|---|
| 1 | `a` finds a cause that lives in `rb` | files `rb#7`, `kind=triage` | → `b` |
| 2 | `b` reads `rb#7`, triages, asks | comment, `kind=question` | → `a`, because it asked |
| 3 | `a` reads the question, answers | comment, `kind=answer` | → `b` |
| … | alternating | | |
| n | either side | `kind=conclusion` | → peer, so it stops waiting; no reply expected |

A comment that needs nothing back produces no signal. A session never signals about
an issue it has merely noticed. A session that has nothing to write does not signal
at all.

The signal itself:

```
relay:v1 <kind> <owner>/<repo>#<number> blocking=yes|no
```

The leading `relay:v1` is the **envelope**. It is the only thing that makes a message
this protocol's, and it carries the version so a receiver can tell a message it does
not understand from a message it must ignore. `kind` is the vocabulary the comments
use. The sender sets `blocking=yes` only when
it cannot continue its own work without the answer — not because it would prefer one
soon. A sender that marks everything blocking has removed the receiver's ability to
protect its own task.

### Addressing

Signals are addressed to a repository. Sessions are addressed by name. Resolving one
to the other is the only genuinely unreliable step, so it is built to fail safely
rather than to be correct.

1. `ListAgents` gives the live session names.
2. Session names generally derive from the working directory, so the repository name
   is a usable candidate filter — but only a candidate. In the observed fleet
   `tutorail-8c` and `tutorial-run` cannot be told apart from outside.
3. The receiver decides. **Once a message is known to be this protocol's**, the
   first thing it checks is whether the issue's repository is the repository this
   session is bound to. If it is not, reply `relay:v1 not-mine <ref>` and stop.
   Nothing is read, nothing is written. What comes before this check is *Envelope
   discipline* below.
4. If no candidate matches, or every candidate replies `not-mine`, the sender says
   so in its own chat: the issue is filed and waiting for a session on that
   repository.

This is why no registry is needed. A mis-addressed signal costs one round trip and
changes nothing, so a cheap wrong guess is better than state to maintain.

### The thread

**One venue: the downstream issue.** When `bundles` files `authoring-tools#7`, that
issue is the whole conversation. `authoring` asks its questions there, `bundles`
answers there, the conclusion is recorded there. The upstream issue `bundles#41`
gets exactly two protocol comments: one linking out, one carrying the conclusion
back.

Every protocol comment opens with a machine-readable header and a visible
attribution line:

```markdown
<!-- relay:v1 from=bundles repo=skomp/tutorail-bundles ref=2eac95 kind=question seq=3 blocking=yes -->
**`bundles` → `authoring`** · question · 3 of 10
```

The visible line is the provenance requirement: a reader sees which session spoke
without reading HTML. The `ref` distinguishes two sessions that both called
themselves `bundles` on different days. The `seq` is how ten is counted, and it
counts **per issue**: the two comments on the upstream issue are a separate, and
separately capped, thread from the discussion on the downstream one.

`kind` is one of `triage`, `question`, `answer`, `conclusion`, `stalemate`.

Bodies follow `tracking-work`: ASD-STE100 Simplified Technical English, and every
issue reference written `repo#123`, every pull request `PR: repo#123`. A bare `#123`
in a cross-repo thread is unresolvable by construction.

**One exception, and it is silent when missed.** In a *closing keyword* — `Closes`,
`Fixes`, `Resolves`, in a commit message or a pull request body — write the full
`owner/repo#123`. GitHub's parser acts on `#123` and on `owner/repo#123` only; the
short `repo#123` form renders as plain text and closes nothing. This protocol files
issues into repositories other than the one being committed to, so the qualified
form is the *only* form that works here. After any push whose commits claim to close
a peer's issue, check it:

```sh
gh issue list --repo <owner>/<repo> --state open
```

### Labels

Two labels, and they exist for one purpose: to make the human's manual check cheap.

| Label | Meaning | Lifecycle |
|---|---|---|
| `relay:open` | A cross-repo thread is live on this issue | added with the first protocol comment, removed at conclusion |
| `relay:stalled` | The thread hit the cap or a loop and is waiting on the human | added at a stuck exit |

Issues Claude files also carry `created-by-claude`, per `tracking-work`. Labels are
created on first use with `gh label create`.

### Manual recovery

A signal reaches only a running session. When one is missed, recovery is the human
asking — "are there new issues to discuss?" — and the answer must be cheap to
produce. That is what `relay:open` is for:

```sh
gh issue list --state open --label relay:open --json number,title,updatedAt
```

Read only the newest protocol comment of each result. **Do not read every open issue
and every comment.** A recovery check that costs a large fraction of the context
window is worse than the missed signal it repairs.

### Envelope discipline

**The skill must not consume a message it was not meant to receive.** A session
receives messages for many reasons, and other skills — present or future — define
their own. This protocol owns exactly one shape and must be inert for everything
else.

**The prefix is both the trigger and the guard, and they are different
mechanisms.** The guard below runs inside a skill that is already in context. What
puts it there is its frontmatter `description`, which is the only retrieval
mechanism a skill has. So the description of `handling-an-inbound-ping` must name
the literal string `relay:` and must say that the skill is inert for anything else.
A description that says "handles messages from peer sessions" routes every protocol
to this one skill and makes the guard the only thing standing between them.

Written that way, each protocol routes itself by its own prefix and needs no central
dispatcher. That claim is untested — it is the same retrieval property this
repository's `README.md` already admits is unproven for all six existing skills — so
it is a verification item below, not an assumption.

The guards run in this order, and the order is the point:

1. **Does the message begin with `relay:`?** If not, it is not this protocol's.
   Ignore it completely: do not act, do not reply, do not report it as unrecognised,
   do not mark it handled. Hand it back to the session's normal handling, which may
   include another skill. **A reply is a form of consumption** — answering
   `not-mine` to a message that was never a relay message claims it.
2. **Is the version supported?** `relay:v1` is understood. A higher version means the
   sender knows something this receiver does not. Reply
   `relay:v1 unsupported version=<v> <ref>` and tell the human. Do not guess at the
   semantics of a version you do not implement.
3. **Is the repository mine?** The ownership guard, *Addressing* step 3.
4. **Is the `kind` one of the five?** If not, reply
   `relay:v1 unsupported kind=<kind> <ref>` and tell the human. An unknown `kind`
   inside a known version is a protocol error, not a message to improvise on.

Only a message that passes all four reaches the decision rule below. Guards 2 and 4
reply because the message *was* addressed to this protocol and silence would strand
the sender. Guard 1 stays silent because the message was not.

### Handling an inbound signal

After the four guards above:

```
blocking?  ──no──→  subagent handles it; the main session continues
   │
  yes
   │
overlaps the in-flight task?  ──no──→  subagent
   │
  yes → finish the current step, then answer in the main session
```

"Overlaps" reuses the file-ownership notion `parallel-sessions` already defines:
does the issue concern a path the in-flight task owns? When it does, a subagent
would read a tree moving under it — the same reason a reviewer must pin a commit.

The subagent's constraints, which go in its dispatch verbatim:

- It owns no files. It reads, and it runs `gh`. It never edits, stages or commits.
- It signs comments with the **session's** name and ref, not its own.
- If it needs a decision from the human, it returns to the session and reports. It
  never asks. A subagent asking the human is `parallel-sessions` §4 again.
- It emits the outbound signal itself only if it wrote a comment that needs an
  answer, following the same rule as the session.

### Termination

Three exits.

**Conclusion.** A `kind=conclusion` comment on the downstream issue stating what was
decided and why, cross-linked into the upstream issue, `relay:open` removed. Each
session closes only its own repository's issue, and only when the fix lands.

**Cap.** Ten comments carrying your own `from=` on that issue. Count by reading the
thread's protocol headers, not by memory.

**Loop.** A checkable test rather than a judgement: *before posting, compare the
draft against your own earlier comments on this thread. If it asserts no new fact
and requests nothing new, that is the loop.*

Both stuck exits do the same thing:

1. Post one `kind=stalemate` comment: what is settled, what is still open, what each
   side believes.
2. Replace `relay:open` with `relay:stalled`.
3. Signal the peer that the thread is closed, so a peer mid-compose does not post an
   eleventh comment.
4. Raise the specific decision with the human **in the session that owns the work**.

The issue stays open. A closed issue loses a real open question, and closing is
outward-facing.

## Files

```
plugins/session-relay/
  .claude-plugin/plugin.json
  skills/coordinating-across-repos/SKILL.md
  skills/handling-an-inbound-ping/SKILL.md
```

Plus an entry in `.claude-plugin/marketplace.json` and a fourth row in `README.md`.

## Verification

The other six skills in this repository are untested, and the README says so. This
one is testable before it ships, and the live tutorail fleet is the rig.

1. **Prove the description fires on the prefix alone.** Send a session a bare
   `relay:v1 triage <owner>/<repo>#1 blocking=no` and nothing else — no surrounding
   explanation, no mention of issues or peers. The skill must load. If it does not,
   the prefix does not route, and a central dispatcher becomes necessary rather than
   optional. Record the result in `skomp/session-signal-router#1`, which is waiting
   on exactly this answer.
2. **Prove the skill ignores what is not its own.** Send a session an ordinary
   message with no `relay:` prefix while the skill is loaded. It must do nothing at
   all — no reply, no `not-mine`, no mention that it saw a protocol message. This is
   the guard most likely to be written and never exercised.
3. **Prove the ownership guard rejects.** Signal a session about an issue in a
   repository it is not bound to. It must reply `not-mine` and read nothing. A guard
   only ever seen to accept is not evidence.
4. **Prove one round trip.** File an issue in the bundles repository from the bundles
   session, signal the authoring session, and confirm a `kind=question` comment with
   a correct header appears on the downstream issue and that the bundles session is
   signalled back.
5. **Prove silence.** Confirm that a session which writes a comment needing no answer
   sends no signal, and that a session with no inbound signal does nothing at all.
6. **Prove a stuck exit.** Drive a thread to the cap and confirm the stalemate
   comment, the label swap and the escalation all happen.
7. **Prove the recovery check is cheap.** Measure what the manual check reads on a
   repository with a realistic number of open issues. It must touch only the
   `relay:open` ones.

The README's "untested" caveat must then be narrowed to the six skills it still
applies to, not copied onto the seventh.

## Risks

- **Name resolution is a guess.** Mitigated by the receiver's ownership guard, which
  makes a wrong guess cost one round trip. If guessing proves noisy in practice, a
  registry can be added later; it is not needed to start.
- **`SendMessage` reach.** It reaches only sessions the host lists — in practice, one
  machine. Beyond that, recovery is the human asking. Accepted deliberately.
- **A thread can sit unnoticed.** With no poller, a filed issue waits until a session
  opens on that repository and the human asks. Accepted deliberately: the alternative
  costs context on every session start.
- **Two copies.** Per this repository's `CLAUDE.md`, a private copy of these skills
  lives in `~/.claude/skills/`. A correction here must be checked against it.
