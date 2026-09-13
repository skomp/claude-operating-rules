# session-relay — design

**Date:** 2026-09-13
**Status:** approved, not implemented
**Scope:** a fourth plugin in `claude-operating-rules`

## Problem

A project spans several repositories in layers. The tutorial-tooling project is the worked
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

1. **One session, one repository.** The session binds to exactly one repository at
   start, taken from `git remote get-url origin` in the working directory. If there
   is no origin, or the origin is not GitHub, the session is *unbound* and takes no
   part in the protocol.
2. **Work is tracked in GitHub issues.** A project using `TODO.md` cannot
   participate — there is nothing for a peer to read or comment on.

### The teeth

A session may clone and read any peer repository to understand a problem. A session
**must never edit, commit, branch, tag or open a pull request in a repository it is
not bound to.** Work that belongs to another repository becomes an issue filed
against that repository, plus a ping.

Without this rule the protocol is optional: a session that can just fix the other
repository will do so, and the coordination never happens.

## Non-goals

- Coordinating sessions across machines. `SendMessage` reaches only sessions the
  host lists. Cross-machine coordination degrades to polling, which is acceptable
  because the issue, not the signal, is the durable record.
- Replacing human review. The protocol escalates to the human; it does not decide.
- Carrying discussion anywhere but GitHub. A session signal carries a reference and
  routing flags. It never carries a question, an answer or an argument.

## Architecture

### Packaging

A new plugin `session-relay`, two skills. It is deliberately not part of
`agent-operations`: that plugin is about many agents inside one repository, this is
one agent per repository across many. Separating them means installing the relay
never drags in worktree rules, and the reverse.

| Skill | Trigger |
|---|---|
| `coordinating-across-repos` | You find a cause that lives in another repository; you are about to edit a repository you are not bound to; you need to open, answer or close a cross-repo thread. Owns preconditions, addressing, the wire format and termination. |
| `handling-an-inbound-ping` | A peer signals you, or a poll finds an issue you have not triaged. Owns the decision rule and the subagent dispatch. |

The wire format is defined once, in `coordinating-across-repos`, and referenced by
the other. Two copies of one format is the failure `completing-a-correction`
describes.

### Identity and addressing

A session is identified by its host session name (`bundles`), its short ref
(`2eac95`) and its bound repository (`owner/repo-b`). Names alone are not
enough: in the observed fleet, `alpha-8c` and `alpha-run` cannot be told
apart from outside, and a name is reused when a session restarts.

Each session writes one file at start:

```
~/.claude/relay/sessions/<ref>.json
{ "name": "bundles", "ref": "2eac95", "repo": "owner/repo-b",
  "cwd": "/Users/robert/src/github.com/owner/repo-b",
  "pid": 12345, "started": "2026-09-13T09:12:00Z" }
```

One file per session, written to a temporary name and renamed, so concurrent
sessions never write the same file. To ping a repository: read the directory,
select the entry whose `repo` matches, confirm the name still appears in
`ListAgents`, then `SendMessage`. Entries whose name is absent from `ListAgents`
are stale and are deleted.

Addressing is **by repository, never by name**. A name that was eyeballed from a
session list is a guess.

### Discovery — two paths, different failure modes

**Peer to peer.** `SendMessage` carrying a reference and routing flags:

```
relay: <kind> <owner>/<repo>#<number> blocking=yes|no
```

`kind` is the same vocabulary the comments use. The sender sets `blocking=yes` only
when it cannot continue its own work without the answer — not merely because it
would prefer one soon. A sender that marks everything blocking has removed the
receiver's ability to protect its own task.

The body of the discussion is never in the signal. The receiving session reads the
issue.

**Human to a running session.** The human files an issue on GitHub. Nothing signals
anyone, so discovery is a poll — and the poll must cost the human no ceremony, no
label they have to remember. The poll asks two questions:

1. Which open issues in my repository carry neither `relay:triaged` nor
   `relay:stalled`? Those are untriaged work.
2. Which open issues carry `relay:awaiting-peer` where the newest protocol comment
   is *not* from me? Those are answers that arrived while I was not listening.

The second question is what makes a missed signal harmless.

**Both questions are bounded by a watermark.** A repository with forty open issues
must not deliver forty pings the first time a session starts in it. The poll
considers only issues created or updated after the timestamp in
`~/.claude/relay/watermark-<owner>-<repo>.json`, which each poll advances. The first
run in a repository writes the watermark, reports nothing, and says once that it has
adopted the repository from this point forward. An existing backlog is ordinary work
the human already knows about; it is not a set of pings.

The poll runs from two hooks and one command:

- `SessionStart` — registers the session and runs the poll once. Catches everything
  filed while no session was running.
- `Stop` — runs the poll when the session finishes a turn, debounced: skip if the
  last poll was under 60 seconds ago, recorded in `~/.claude/relay/last-poll-<ref>`.
  This is the part most likely to irritate, so it is separately switchable.
- `/relay-inbox` — the same poll on demand.

All three exit silently and successfully when `gh` is missing, the session is
unbound, or the network fails. A hook that blocks a session is worse than a late
ping.

### The thread

**One venue: the downstream issue.** When `bundles` files `authoring-tools#7`, that
issue is the whole conversation. `authoring` asks its questions there, `bundles`
answers there, the conclusion is recorded there. The upstream issue
`bundles#41` gets exactly two protocol comments: one linking out, one carrying the
conclusion back.

Every protocol comment opens with a machine-readable header and a visible
attribution line:

```markdown
<!-- relay:v1 from=bundles repo=owner/repo-b ref=2eac95 kind=question seq=3 blocking=yes -->
**`bundles` → `authoring`** · question · 3 of 10
```

The visible line is the provenance requirement: a reader sees which session spoke
without reading HTML. The `ref` distinguishes two sessions that both called
themselves `bundles` on different days. The `seq` is how ten is counted, and it counts **per issue**: the two comments on
the upstream issue are a separate, and separately capped, thread from the discussion
on the downstream one.

`kind` is one of `triage`, `question`, `answer`, `conclusion`, `stalemate`.

Bodies follow `tracking-work`: ASD-STE100 Simplified Technical English, and every
issue reference written `repo#123`, every pull request `PR: repo#123`. A bare
`#123` in a cross-repo thread is unresolvable by construction.

### Labels

| Label | Meaning | Applied by |
|---|---|---|
| `relay:triaged` | A bound session has read this issue and decided what it needs, including deciding it needs no peer at all | the triaging session |
| `relay:awaiting-peer` | This session has asked and is waiting | the asking session, which removes it when it reads the answer |
| `relay:stalled` | The thread hit the cap or a loop | the session that hit it |
| `created-by-claude` | Required on every issue Claude files | `tracking-work` |

Labels are created on first use with `gh label create`.

### Inbound decision rule

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
- If it needs a decision from the human, it returns to the session and reports.
  It never asks. A subagent asking the human is `parallel-sessions` §4 again.

### Termination

Three exits.

**Conclusion.** A `kind=conclusion` comment on the downstream issue stating what was
decided and why, cross-linked into the upstream issue. Each session closes only its
own repository's issue, and only when the fix lands.

**Cap.** Ten comments carrying your own `from=`. Count by reading the thread's
protocol headers, not by memory.

**Loop.** A checkable test rather than a judgement: *before posting, compare the
draft against your own earlier comments on this thread. If it asserts no new fact
and requests nothing new, that is the loop.*

Both stuck exits do the same thing:

1. Post one `kind=stalemate` comment: what is settled, what is still open, what each
   side believes.
2. Label the issue `relay:stalled`.
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
  commands/relay-inbox.md
  hooks/hooks.json
  hooks/relay-register.sh
  hooks/relay-poll.sh
```

Plus an entry in `.claude-plugin/marketplace.json` and a fourth row in `README.md`.

## Verification

The other six skills in this repository are untested, and the README says so. This
one is testable before it ships, and the live tutorial-tooling fleet is the rig.

1. **Prove the poll can fail.** Run it against a repository with no untriaged issue
   and confirm it reports nothing. Plant one untriaged issue and confirm it is
   found. A poll that has only ever been seen to report nothing is not evidence.
2. **Prove the hooks fire.** Confirm `SessionStart` writes the registry file and
   `Stop` runs the poll, by observing the side effects, not by reading the config.
3. **End to end.** File a real issue against the bundles repository. Confirm the
   bound session finds it, triages it, files against the authoring-tools repository
   with a correct header, and that the authoring session answers on the downstream
   issue.
4. **Prove a stuck exit.** Drive a thread to the cap and confirm the stalemate
   comment, the label and the escalation all happen.

The README's "untested" caveat must then be narrowed to the six skills it still
applies to, not copied onto the seventh.

## Risks

- **Plugin hook schema.** `SessionStart` and `Stop` hooks in a plugin's
  `hooks/hooks.json` are assumed to fire with `${CLAUDE_PLUGIN_ROOT}` available.
  This is unverified. Prove it before building on it.
- **`Stop` hook cost.** One `gh` call per turn boundary, debounced to 60 seconds.
  If it proves irritating in use, the fallback is `SessionStart` plus `/relay-inbox`
  only.
- **`SendMessage` reach.** It reaches only sessions the host lists — in practice,
  one machine. Cross-machine coordination falls back to polling. The issue label,
  never the signal, is the durable truth.
- **Registry staleness.** A session that exits without cleanup leaves a file behind.
  `ListAgents` is the authority; the registry is only a repository index.
- **Two copies.** Per this repository's `CLAUDE.md`, a private copy of these skills
  lives in `~/.claude/skills/`. A correction here must be checked against it.
