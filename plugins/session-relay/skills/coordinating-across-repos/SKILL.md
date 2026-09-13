---
name: coordinating-across-repos
description: "Read when you find that a fault in this repository has its cause in a peer repository; before you edit, commit, branch or open a pull request in a repository this session is not bound to; and before you raise work with a peer repository's session, answer one, or conclude a cross-repository thread. Read it whether or not this repository has opted in — a `## Session relay` declaration in its `CLAUDE.md` — because it also carries what to do, and what to offer, when it has not. Being asked to file an issue against another repository is NOT a trigger on its own."
---

# Coordinating Across Repos

A project in layers puts the symptom in one repository and the cause in another. Fixing
the other repository yourself puts two agents in one checkout — the failure
`parallel-sessions` exists to stop. Asking in your own chat makes your human partner
the transport. `parallel-sessions` §4 permits coordination between sessions and forbids
carrying decisions between them; this is the channel it never named.

**The conversation happens in GitHub issues, and a session signal only says that there
is something new to read.** A human opens the channel, not you — but a channel nobody
is told about is a channel nobody opens, so you may offer it once. Section 1 is the
gate.

## 1. Three hard preconditions

The protocol refuses to operate unless all three hold. If one fails, **say so plainly
and take no part** — a session that signals but cannot be answered is worse than one
that says up front that it cannot play. Preconditions 1 and 2 are facts about the
checkout. Precondition 3 is a human's decision, and you may ask for it once.

1. **One session, one repository.** The session binds to exactly one repository, taken
   from `git remote get-url origin` in the working directory. Run it; do not assume.
   With no origin, or an origin that is not GitHub, this session is *unbound*: it files
   nothing, signals nothing, and never answers `mine`.
2. **Work is tracked in GitHub issues.** A project on a `TODO.md` cannot participate —
   there is nothing for a peer to read and nothing for it to comment on. Check the
   project's `CLAUDE.md` for the tracking choice, per `tracking-work`.
3. **The protocol is enabled for this repository, by a human, in writing.** The
   repository's `CLAUDE.md` names the peer repositories this project spans:

   ```markdown
   ## Session relay

   Enabled. Peer repositories:
   - skomp/courseware-authoring
   - skomp/courseware-bundles
   ```

**You never infer enablement.** Not from peer repositories sitting on disk, not from a
project that obviously spans several repositories, and above all not from being asked
to file an issue against another repository. "File an issue against the bundles repo"
is an ordinary English sentence, and it must not start a machine. You may offer once
and enable on a yes: the gate is an explicit confirmation, not the absence of one.

**The declared list also bounds the protocol: a target repository that is not on it is
not a peer.** A cause in an undeclared repository is reported and left there, exactly
as if the protocol were disabled. Read the declaration; do not extend it.

*Why it is opt-in:* a protocol that starts itself spends your human partner's attention
on machinery they did not ask for, in the one situation where they can least afford to
work out what is talking to what.

### Offering the protocol

A silent refusal makes the protocol undiscoverable: only someone who already knows it
exists would ever write the declaration that turns it on. So when the section is
**absent** and you find a cause in another repository, **do the work you were asked to
do first** — file the ticket, or say where the cause lives — and only then offer, once.
The offer never blocks the request you were given.

> Filed `skomp/courseware-bundles#41`.
>
> I can also check whether a session is running that would pick this up. That starts
> the inter-session issue protocol: the two sessions triage and discuss the issue
> themselves, in GitHub comments on the issue, each comment naming the session that
> wrote it. It needs a second session already running in the other repository's local
> working copy — without one there is nothing to talk to. Want me to?

**State both costs, and do not soften either** — the discussion is **autonomous**, and
it is **written into a public record**. Both halves surprise people. Name the
precondition in the same breath, because without a second session already running there
the answer buys nothing.

**Any clear yes is enough.** "yes", "go ahead", "do it". No ceremony, no second
confirmation. On a yes, write the `## Session relay` declaration into this repository's
`CLAUDE.md`, naming the peer, and continue.

**On a no, write the declaration anyway, as a refusal:**

```markdown
## Session relay

Not enabled.
```

Say in the same line that deleting the section restores the offer. The refusal is what
stops the offer coming back every session, and nagging is how a good feature gets
switched off for good. **Offer only when the section is absent.** `Not enabled.` means
never ask again.

### When a peer signals a repository that has not opted in

You know the repository and the issue reference from the signal alone, so **answer
without reading anything** — no clone, no `gh issue view`, no triage. Reply
`session-relay:v1 not-enabled <subject>`, which tells the sender to stop waiting and
stop looking. Then make the same offer to your own human partner, naming the session
that called and the issue it points at. A repository just invited into a conversation
is where the offer is most useful, and the reply has already released the sender.

## 2. The teeth

You may clone and read any peer repository to understand a problem. Read what the
fault needs and no more — section 9's frugality applies to a peer's tree as much as to
your own.

**You must never edit, commit, branch, tag or open a pull request in a repository you
are not bound to.** Work that belongs to another repository becomes an issue filed
against that repository, plus a signal to the session bound there. This is the rule the
whole protocol rests on: without it the protocol is optional, a session that *can* just
fix the other repository will, and two agents end up in one checkout anyway.

## 3. The signalling rule

**A signal is emitted only immediately after this session writes to an issue, and only
when that write needs an answer, or ends a thread a peer is waiting on.** There is no
other reason to signal and no other way to be signalled. There is no hook, no poller,
no watcher, no registry file and no slash command; a session acts under this protocol
when it writes to a peer issue, when a peer signals it, or when its human partner asks
it to look. Everything else is silence.

The consequence is strict alternation. Session `a` is bound to `ra`, session `b` to
`rb`:

| Step | Session | Writes | Signals |
|---|---|---|---|
| 1 | `a` finds a cause that lives in `rb` | files `rb#7`, `kind=triage` | → `b` |
| 2 | `b` reads `rb#7`, triages, asks | comment, `kind=question` | → `a`, because it asked |
| 3 | `a` reads the question, answers | comment, `kind=answer` | → `b` |
| … | alternating | | |
| n | either side | `kind=conclusion` | → peer, so it stops waiting; no reply expected |

The second half of the rule is not a loophole. A `conclusion` expects no reply, but a
peer that asked a question is waiting; the test is whether the peer's next action
depends on this write, not whether you want a reply. Everything else produces no
signal: a session never signals about an issue it has merely noticed, and a session
with nothing to write does not signal at all.

**The transport is `SendMessage`, addressed to a session name from `ListAgents`.** It
is the only transport this protocol uses, and it carries everything: signals, control
replies and `whois` broadcasts alike. Nothing else moves between sessions.

## 4. The signal, and what `blocking` means

```
session-relay:v1 <kind> <owner>/<repo>#<number> blocking=yes|no
```

Write the issue as `<owner>/<repo>#<number>`. The receiver cannot expand a short form —
it is not in that repository.

**Set `blocking=yes` only when you cannot continue your own work without the answer.**
Not when you would prefer one soon, and not when the issue feels important. `blocking`
is not a priority field; it is the receiver's interrupt, and it decides whether the
peer hands the work to a subagent or stops what it is doing. **A sender that marks
everything blocking has removed the receiver's ability to protect its own task** — it
has ranked every one of its questions above work it cannot see.

## 5. The envelope

The leading `session-relay:v1` is the **envelope**. It is the only thing that makes a
message this protocol's, and it carries the version so a receiver can tell a message it
does not understand from one it must ignore. `handling-an-inbound-ping` owns the guards
that read it.

**The prefix names the protocol — not the skill, and not the message type.** A prefix
carrying the receiving skill's name would make the sender depend on the receiver's
implementation: rename the skill and every header already posted into a GitHub issue is
retroactively wrong, and those comments are permanent. A prefix carrying the message
type (`triage:`, `question:`) would claim four generic English words for one protocol.
A wire format must outlive the code that reads it, so it names the only thing that does
not move.

## 6. Addressing: ask, do not guess

Signals are addressed to a repository. Sessions are addressed by name. **Nothing
reliably connects the two**, so resolution is a question asked over the wire — not a
lookup, and not a guess that is allowed to give up.

1. **`ListAgents` gives the live sessions.** Only an interactive peer can be reached.
   Skip an offline or Remote Control session, and remember that you skipped it.
2. **The repository name orders the candidates. It never excludes one.** Measured
   against a real fleet of four sessions on 2026-09-13: `courseware-authoring-db`
   matched its repository by prefix, `courseware-8c` matched case-insensitively,
   `bundles` matched `courseware-bundles` only as a substring, and `coursewear-run` did
   not match `courseWare-supplies` under any string rule at all — that session spells
   the project differently from the repository. **A filter that could exclude would
   have failed to reach a live, correct session one time in four**, and would have
   reported that no session owned the repository while that session sat idle.
3. **Ask.** `SendMessage` `session-relay:v1 whois <owner>/<repo>` to the best candidate. The
   session bound to that repository replies `session-relay:v1 mine <owner>/<repo>`.
   Any other session replies `not-mine`.
4. **On `not-mine`, ask every remaining live interactive peer.** One `mine` resolves
   the address for the rest of this session.
5. **On `not-enabled`, stop looking.** That is the right session, refusing on purpose:
   its repository has not opted in, and asking anyone else cannot change the answer.
   `not-mine` means keep looking; `not-enabled` means stop looking and talk to a human.
   Never treat the two as the same answer.
6. **On `unsupported`, stop, and never send that message again.** The peer read your
   envelope and refused what was inside it. A refusal is deterministic — the same
   message gets the same answer — so a retry buys nothing. See *When a peer replies
   `unsupported`* below.
7. **Only when no session replies `mine` do you give up**, and giving up is the report
   below, not a statement of fact.

**This is why there is no registry: the sessions are the registry, and they are asked
rather than recorded.** A `whois` costs one message, reads nothing and writes nothing,
and unlike a file it cannot go stale.

### When nobody answers `mine`

A dead end is a normal outcome, not an error. Either no session is bound to that
repository, or one is and could not be found, and **you cannot tell these apart** — a
`not-enabled` answer is the one case you do know.

**Never report only that no session was found.** That names the symptom and leaves your
human partner to derive both the diagnosis and the remedy, at the moment they have the
least context — the failure this whole protocol exists to stop.

The report names, in this order:

1. **What was filed, and where.** The issue as `owner/repo#123` plus its URL. The work
   is not lost; it is in GitHub with `session-relay:open` on it.
2. **Who was asked, and what each one said.** Every live peer, with its answer or its
   silence. A session that answered nothing is a different fault from a fleet where
   every session answered `not-mine`.
3. **Who could not be asked.** The peers listed as offline or Remote Control. The
   right session may be one of them, on another machine, where no signal reaches.
4. **The three fixes, named as alternatives:**
   - *No session is running for that repository.* Open one in that repository's
     checkout and tell it to triage the issue. One sentence in that session's own chat
     is the whole fix, and it is the sanctioned entry point anyway.
   - *A session is running but was not found.* It is not bound: its working directory
     has no GitHub `origin`, or the origin points elsewhere. Check it with
     `git remote get-url origin` in that checkout. A session with the wrong origin is
     unbound by precondition 1 and will never answer `mine`, however often it is asked.
   - *A session answered `not-enabled`.* It is the right session, and that repository
     has not opted in. It has already offered its own human partner the choice, so the
     fix may be one word in that session's chat; failing that, add the
     `## Session relay` declaration to its `CLAUDE.md`, naming this repository as a peer.

### When a peer replies `unsupported`

The reply names which half it refused, and the two have different remedies. Neither
remedy is sending the same message again.

- **`session-relay:v1 unsupported version=<v> <subject>`** — that session does not
  implement the version you sent. You cannot downgrade by guessing what an older
  receiver would have made of your message; guessing at a version you do not implement
  is the thing guard 2 refuses on the other side, and it is no better in this
  direction. Treat that peer as unreachable for this thread and report it the way a
  dead end is reported above, with one fix in place of the three: **that session's
  `session-relay` plugin is older than this one's, and updating it is the whole
  remedy.** It has already told its own human partner. Nothing is lost — the issue is
  filed, labelled and waiting.
- **`session-relay:v1 unsupported kind=<kind> <subject>`** — the `kind` you sent is in
  neither vocabulary. Inside a version you both implement that is your own defect, not
  the peer's: correct the `kind` to one of the ten below and send the corrected
  message. A different message is not a retry. If the `kind` you sent *was* one of the
  ten, the peer is running an older vocabulary, and it is the version case above under
  another name.

**Do not signal a third session about the same issue to get past a refusal.** The
repository belongs to the peer that refused, whatever it can and cannot parse.

### Two vocabularies

`kind` names either a comment or a control reply, and the two never mix:

| Vocabulary | Values | Where it appears |
|---|---|---|
| Comment kinds | `triage`, `question`, `answer`, `conclusion`, `stalemate` | in a GitHub issue comment, and in the signal that announces it |
| Control replies | `whois`, `mine`, `not-mine`, `not-enabled`, `unsupported` | in a signal only — never written into an issue |

**A control signal carries no issue number of its own.**
`session-relay:v1 whois <owner>/<repo>` and `session-relay:v1 mine <owner>/<repo>` are
complete messages.

**`<subject>` in a reply is the subject of the message being answered, echoed
verbatim** — `<owner>/<repo>#<number>` when the inbound signal named an issue,
`<owner>/<repo>` when it was a `whois`. It lets a sender with two questions in flight
tell which one came back, and it invents no identifier. **It is deliberately not called
`ref`**: `ref=` in a comment header is the sender session's short ref, and one word with
two meanings is what `tracking-work` forbids. A reply carries a `<subject>`; a header
carries a `ref`.

A receiver must accept both vocabularies. A guard that rejected `whois` would make
addressing impossible, because the message that finds the right session would be
refused by every session that could answer it.

## 7. The thread

**One venue: the downstream issue.** When `bundles` files `authoring-tools#7`, that
issue is the whole conversation: `authoring` asks its questions there, `bundles` answers
there, the conclusion is recorded there.

The upstream issue gets **exactly two protocol comments**: one linking out when the
downstream issue is filed, one carrying the conclusion back. A discussion split across
two issues is a discussion nobody can read later.

## 8. The comment format

**This section is the single definition of the format.** Every protocol comment opens
with a machine-readable header and a visible attribution line:

```markdown
<!-- session-relay:v1 from=bundles repo=skomp/courseware-bundles ref=2eac95 kind=question seq=3 blocking=yes -->
**`bundles` → `authoring`** · question · 3 of 10
```

| Field | Meaning |
|---|---|
| `from` | the sender's session name, as `ListAgents` prints it |
| `repo` | the sender's own bound repository, as `<owner>/<repo>` — never the issue's repository, which the reader already knows from the issue the comment sits on |
| `ref` | the sender session's short ref, **copied from `ListAgents`** |
| `kind` | one of `triage`, `question`, `answer`, `conclusion`, `stalemate` |
| `seq` | this sender's comment count on this issue, starting at 1 — the issue body counts as 1 when you filed the issue to open the thread |
| `blocking` | `yes` or `no`, with the meaning in section 4 |

**The filed issue's body is the thread's first protocol comment.** When you open a
thread by filing the downstream issue, its body carries this same header and
attribution line, with `kind=triage` and `seq=1`; you never post a separate first
comment, and the next thing written on that issue is `seq=2`. On an issue that already
exists — the upstream one — the first protocol comment is an ordinary comment, and it
is that sender's `seq=1`.

**Never invent a `ref`.** Copy the one `ListAgents` prints; a session that cannot read
its own ref **omits the field** rather than guessing. An invented ref reads exactly like
a real one and silently attributes a comment to a session that never wrote it. What it
buys is telling apart two sessions that both called themselves `bundles` on different
days — session names repeat, so a name alone does not identify who spoke last week.

`seq` is per sender **and** per issue, because the cap is: two sessions each have their
own run from 1 to 10 on one issue, and the two comments on the upstream issue are a
separate, separately capped thread from the discussion downstream.

**Write both lines.** The visible one is the provenance requirement — a reader sees
which session spoke without reading HTML. A header with no visible line is provenance
only a machine can read.

## 9. Labels

Two labels, for one purpose: to make your human partner's manual check cheap. A signal
reaches only a running session, so when one is missed, recovery is your human partner
asking — and the answer has to be cheap to produce.

| Label | Meaning | Lifecycle |
|---|---|---|
| `session-relay:open` | a cross-repo thread is live on this issue | added when the thread's first protocol header is written — at filing for an issue you file to open a thread, with the first protocol comment on an issue that already exists — and removed at conclusion |
| `session-relay:stalled` | the thread hit the cap or a loop and is waiting on the human | added at a stuck exit |

Issues you file also carry `created-by-claude`, per `tracking-work`. Create a label on
first use — a missing label makes the `gh` call fail, and a failed label call after a
successful comment leaves the thread invisible to the recovery check. Fix the colours,
so the same label looks the same in every repository of the project:

```sh
gh label create session-relay:open    --color 1D76DB --description "A cross-repo session thread is live on this issue"
gh label create session-relay:stalled --color B60205 --description "A cross-repo session thread is stuck and waits on a human"
```

The check itself is one command:

```sh
gh issue list --state open --label session-relay:open --json number,title,updatedAt
```

It reads only what the labels point at, and only the newest protocol comment of each
result. **Do not read every open issue and every comment** — a recovery check that costs
a large fraction of the context window is worse than the missed signal it repairs.

## 10. Termination

Three exits. The loop is a test you run on every draft before you post it; the other
two are conditions you notice.

**Conclusion.** A `kind=conclusion` comment on the downstream issue saying what was
decided and why, cross-linked into the upstream issue, `session-relay:open` removed.
Each session closes only its own repository's issue, and only when the fix lands.

**Cap.** Ten comments carrying your own `from=` on that issue. **Count by reading the
thread's protocol headers, not by memory** — your memory of a long thread is what the
cap exists to distrust.

**Loop.** A checkable test, not a judgement: *before posting, compare the draft against
your own earlier comments on this thread. If it asserts no new fact and requests nothing
new, that is the loop.* Run it on every draft, and do not argue with the result.

Both stuck exits do the same four things:

1. Post one `kind=stalemate` comment: what is settled, what is still open, and what
   each side believes.
2. Replace `session-relay:open` with `session-relay:stalled`.
3. Signal the peer that the thread is closed, so that a peer mid-compose does not post
   an eleventh comment.
4. Raise the specific decision with your human partner **in the session that owns the
   work**, per `parallel-sessions` §4 — not in this one, if the work is not this one's.

**Steps 1 to 3 belong to whoever posted the comment.** A subagent dispatched under
`handling-an-inbound-ping` §3 posts the comment, swaps the label and signals the peer
itself, and comes back for step 4 — a subagent never asks your human partner anything.
The same goes for the `conclusion` exit: the label comes off in the same act as the
comment that concluded, by whoever wrote it.

**The issue stays open.** A closed issue loses a real open question, and closing is
outward-facing.

## 11. How references are written

Comment bodies follow `tracking-work`: ASD-STE100 Simplified Technical English, every
issue reference written `repo#123`, and every pull request written `PR: repo#123`. A
bare `#123` in a cross-repo thread is unresolvable by construction — the reader is in
a different repository from the writer.

**One exception, and it fails silently when it is missed.** In a *closing keyword* —
`Closes`, `Fixes`, `Resolves`, in a commit message or a pull request body — write the
full `owner/repo#123`. GitHub's parser acts on `#123` and `owner/repo#123` only; the
short `repo#123` form renders as plain text and closes nothing. This protocol files
issues into repositories other than the one you commit to, so the qualified form is the
*only* one that works here. After any push whose commits claim to close a peer's issue,
check that it worked:

```sh
gh issue list --repo <owner>/<repo> --state open
```

## Red flags — stop

| About to… | Do this instead |
|---|---|
| Start the protocol because someone asked you to file an issue against another repository | Read section 1. With no `## Session relay` declaration: do the work, then offer once |
| Infer enablement from peer repositories on disk, or add a repository to the declared list | Read the declaration. Absent means not enabled; a target it does not name is not a peer |
| Offer again after a no, or hold up the ticket until the offer is answered | File first, offer once, and write `Not enabled.` on a no |
| Fix the other repository yourself because it is a one-line change | File the issue against that repository and signal the session bound there |
| Guess which session owns a repository, or filter the candidate list | Order the candidates, then `SendMessage` a `whois` and let the answer decide |
| Treat `not-enabled` as `not-mine` and keep asking | Stop looking, and report what to add to that repository's `CLAUDE.md` |
| Resend a signal that came back `unsupported`, or take it to a different session | A refusal is deterministic. Fix the `kind`, or report that the peer's plugin needs updating |
| Report "no session found" and stop | Report what was filed, who answered what, who could not be asked, and the fixes |
| Mark a signal `blocking=yes` because the issue matters | Mark it `blocking=yes` only when you cannot continue without the answer |
| Signal a peer about an issue you merely noticed | Signal only right after you write, and only when the write needs an answer or ends a thread a peer waits on |
| Invent a `ref`, or post a header with no visible attribution line | Copy the ref from `ListAgents`, or omit the field; always write both lines |
| Count your comments from memory, or argue past ten because this one feels different | Count your own `from=` headers. At ten: `kind=stalemate`, swap the label, signal the peer, escalate in the session that owns the work, and leave the issue open |
| Write `Closes repo#123` in a commit that closes a peer's issue | Write `Closes owner/repo#123`, then verify with `gh issue list --repo <owner>/<repo> --state open` |
| Ask your human partner about the peer's work in this session's chat | Ask in the session that owns the work, per `parallel-sessions` §4 |
