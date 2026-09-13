# session-relay — design

**Date:** 2026-09-13
**Status:** approved, not implemented
**Scope:** a fifth plugin in `claude-operating-rules`

## Problem

A project spans several repositories in layers. The courseware project is the worked
example: a runner that executes courses, a repository of course bundles, and a
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

The protocol refuses to operate unless all three hold. A session that cannot satisfy
them says so plainly and does not silently degrade.

1. **One session, one repository.** The session binds to exactly one repository,
   taken from `git remote get-url origin` in the working directory. If there is no
   origin, or the origin is not GitHub, the session is *unbound* and takes no part
   in the protocol.
2. **Work is tracked in GitHub issues.** A project using `TODO.md` cannot
   participate — there is nothing for a peer to read or comment on.
3. **The protocol is enabled for this repository, by a human, in writing.** The
   repository's `CLAUDE.md` carries a declaration naming the peer repositories this
   project spans:

   ```markdown
   ## Session relay

   Enabled. Peer repositories:
   - skomp/courseware-authoring
   - skomp/courseware-bundles
   ```

   **A session never infers enablement** — not from peer repositories on disk, not
   from a project obviously spanning several repositories, and above all not from
   being asked to file an issue against another repository. "File an issue against
   the bundles repo" is an ordinary sentence and must not start a machine.

   **It may offer, once, and enable on a yes.** See *Offering the protocol* below.
   The gate is a human's explicit confirmation, not the absence of one.

   The declared list also bounds the protocol: **a target repository that is not on
   it is not a peer.** A session that finds a cause in an undeclared repository
   reports it and stops, exactly as if the protocol were disabled.

   **This is an outbound rule only.** It governs where a session may file and signal.
   It is not a test an inbound guard can run: the only repository an inbound signal
   names is the receiver's own, and the sender's repository appears nowhere a guard
   is allowed to look. Inbound, enablement is binary — the `## Session relay` section
   is present and says enabled, or it is not.

   *Why it is opt-in:* cross-repository coordination is confusing enough when it is
   deliberate. A protocol that starts itself spends a human's attention on machinery
   they did not ask for, in the one situation where they can least afford to be
   working out what is talking to what.

### Offering the protocol

A silent refusal makes the protocol undiscoverable: only someone who already knows it
exists would ever turn it on. So when the declaration is **absent** and you find a
cause that lives in another repository, **do the work you were asked to do first** —
file the ticket, or say where the cause lives — and then offer, once:

> Filed `skomp/courseware-bundles#41`.
>
> I can also check whether a session is running that would pick this up. That starts
> the inter-session issue protocol: the two sessions triage and discuss the issue
> themselves, in GitHub comments on the issue, each comment naming the session that
> wrote it. It needs a second session already running in the other repository's local
> working copy — without one there is nothing to talk to. Want me to?

The offer states the cost honestly, because both halves surprise people: the
discussion is **autonomous** and it is **written into a public record**. Do not soften
either.

**Any clear yes is enough** — "yes", "go ahead", "do it". There is no ceremony and no
second confirmation. On a yes, write the `## Session relay` declaration into this
repository's `CLAUDE.md`, naming the peer, and continue.

**On a no, write the declaration anyway, as a refusal:**

```markdown
## Session relay

Not enabled.
```

That is what stops the offer coming back every time. An offer repeated in every
session is nagging, and nagging is how a good feature gets disabled for good. Record
in the same line that deleting the section restores the offer.

**Offer only when the section is absent.** `Not enabled.` means never ask again.

### When a peer signals a repository that has not opted in

The receiving session knows the repository and the issue reference from the signal
alone, so it can answer without reading anything. It replies
`session-relay:v1 not-enabled <subject>`, and then makes the same offer to its own human
partner — naming the session that called and the issue it points at. A repository that
has been invited into a conversation is exactly where the offer is most useful, and
the reply already told the sender not to wait.

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
- **Depending on a router.** A central dispatcher for inbound signals is under
  evaluation in a separate private repository, and this protocol must never require
  it. Every guard here works with no router installed, and must keep working when
  one is installed and when it is removed again. The router repository's second issue
  holds that as a requirement on the router, not on this protocol.
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
| `handling-an-inbound-ping` | A peer signals you **with a `session-relay:v1` envelope**, or the human asks whether there is anything to discuss. Owns the envelope discipline, the ownership guard, the decision rule and the subagent dispatch. It has no opinion on any other message. |

The wire format is defined once, in `coordinating-across-repos`, and referenced by
the other. Two copies of one format is the failure `completing-a-correction`
describes.

### The signalling rule

**A signal is emitted only immediately after this session writes to an issue, and
only when that write needs an answer, or ends a thread a peer is waiting on.** There
is no other reason to signal, and no other way to be signalled.

The second half of that rule is not a loophole. A `conclusion` expects no reply, but a
peer that asked a question is waiting; leaving it waiting to honour a narrower reading
of "needs something back" would strand it. The test is whether the peer's next action
depends on this write, not whether you want a reply.

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

**The transport is `SendMessage`**, addressed to a session name from `ListAgents`.
It is the only transport this protocol uses and it carries everything: signals,
control replies and `whois` broadcasts alike. Nothing else moves between sessions.

The signal itself:

```
session-relay:v1 <kind> <owner>/<repo>#<number> blocking=yes|no
```

The leading `session-relay:v1` is the **envelope**. It is the only thing that makes a message
this protocol's, and it carries the version so a receiver can tell a message it does
not understand from a message it must ignore. `kind` is the vocabulary the comments
use. The sender sets `blocking=yes` only when
it cannot continue its own work without the answer — not because it would prefer one
soon. A sender that marks everything blocking has removed the receiver's ability to
protect its own task.

### Addressing

Signals are addressed to a repository. Sessions are addressed by name. **Nothing
reliably connects the two**, so resolution is a question asked over the wire, not a
lookup and not a guess that can give up.

1. `ListAgents` gives the live sessions. Only an interactive peer can be reached; an
   offline or Remote Control session is skipped.
2. The repository name **orders** the candidates. It never excludes one. Measured
   against a real fleet of four sessions on 2026-09-13: `courseware-authoring-db`
   matched its repository by prefix, `courseware-8c` matched case-insensitively,
   `bundles` matched `courseware-bundles` only as a substring, and `coursewear-run` did
   not match `courseWare-supplies` under any string rule — the session spells the
   project differently from the repository. **A filter that could exclude would have
   failed to reach a live, correct session one time in four**, and would have
   reported that no session owned the repository while that session sat idle.
3. Ask. Send `session-relay:v1 whois <owner>/<repo>` to the best candidate. The
   session bound to that repository replies `session-relay:v1 mine <owner>/<repo>`.
   Any other session replies `not-mine` under guard 3.
4. On `not-mine`, send the same `whois` to every remaining live interactive peer. One
   `mine` resolves the address for the rest of this session.
5. Only when no session replies `mine` does the sender give up — and giving up is a
   report with **fixing instructions**, not a statement of fact. See below.

This is why no registry is needed — **the sessions are the registry, and they are
asked rather than recorded.** A `whois` costs one message, reads nothing and writes
nothing, and it cannot go stale.

### When nobody answers `mine`

Resolution is best effort by construction, so the dead end is a normal outcome, not an
error. Either no session is bound to that repository, or one is and could not be
found. **The sender cannot tell these apart, and must not guess** — so the report says
what it tried and what the human can do about each case.

The report names, in this order:

1. **What was filed, and where**: the issue reference as `owner/repo#123` plus its
   URL. The work is not lost; it is sitting in GitHub with `session-relay:open` on it.
2. **Who was asked and what they said** — every live peer, with its answer or its
   silence. This is the part that lets a human see the real problem: a session that
   answered nothing is a different fault from a fleet where every session answered
   `not-mine`.
3. **Who could not be asked**: peers listed as offline or Remote Control. The right
   session may be one of them, on another machine, where no signal reaches.
4. **The fixes, named as alternatives:**
   - *No session is running for that repository.* Open one in that repository's
     checkout and tell it to triage the issue. One sentence in that session's own chat
     is the whole fix, and it is the sanctioned entry point anyway.
   - *A session is running but was not found.* It is not bound: its working directory
     has no GitHub `origin`, or it points at a different repository. Check it with
     `git remote get-url origin` in that checkout. A session with the wrong origin is
     unbound by precondition 1 and will never answer `mine`, however many times it is
     asked.
   - *A session answered `not-enabled`.* It is the right session, and that repository
     has not opted in. It has already offered its own human the choice, so the fix may
     be one word in that session's chat; failing that, add the `## Session relay`
     declaration to its `CLAUDE.md`, naming this repository as a peer.

**Never report only that no session was found.** That names the symptom and leaves the
human to derive both the diagnosis and the remedy, at the moment they have least
context — which is the failure this whole protocol exists to stop.

### When a peer replies `unsupported`

A refusal is deterministic: the same message resent gets the same answer, so **the
sender never retries it**, and never takes the same issue to a different session — the
repository belongs to the peer that refused.

- `unsupported version=<v>`: that session implements a version this sender does not
  share. Downgrading by guessing what an older receiver would have done is the same
  fault guard 2 refuses in the other direction. The sender treats the peer as
  unreachable for this thread and reports it as it reports a dead end, with one fix in
  place of the three: **the peer's `session-relay` plugin is older, and updating it is
  the remedy.** The peer has already told its own human.
- `unsupported kind=<kind>`: inside a shared version this is the *sender's* defect.
  Correct the `kind` to one of the ten and send the corrected message; a different
  message is not a retry. If the `kind` sent was already one of the ten, the peer holds
  an older vocabulary and this is the version case under another name.

### Two vocabularies, and guard 4 accepts both

`kind` names either a comment or a control reply, and the two never mix:

| Vocabulary | Values | Where it appears |
|---|---|---|
| Comment kinds | `triage`, `question`, `answer`, `conclusion`, `stalemate` | in a GitHub issue comment, and in the signal that announces it |
| Control replies | `whois`, `mine`, `not-mine`, `not-enabled`, `unsupported` | in a signal only — never written into an issue |

A control signal carries no issue number of its own: `session-relay:v1 whois
<owner>/<repo>` and `session-relay:v1 mine <owner>/<repo>` are complete messages.

**`<subject>` in a reply is the subject of the message being answered, echoed
verbatim** — `<owner>/<repo>#<number>` when the inbound signal named an issue,
`<owner>/<repo>` when it was a `whois`. It exists so a sender with two questions in
flight can tell which one came back, and it invents no identifier.

**It is deliberately not called `ref`.** `ref=` in a comment header is the sender
session's short ref from `ListAgents`. One word with two meanings is what
`tracking-work` forbids. A reply carries a `<subject>`; a header carries a `ref`. **Guard 4 must accept
both vocabularies** — a guard that rejected `whois` would make addressing impossible,
because the message that finds the right session would be refused by every session.

### The thread

**The thread's first protocol comment is the filed issue's body.** The issue a session
files to open a thread carries the header and the attribution line in its body, with
`kind=triage` and `seq=1`. There is no separate first comment, and the next write on
that issue is `seq=2`. On an issue that already exists — the upstream one — the first
protocol comment is an ordinary comment carrying that sender's `seq=1`.

**One venue: the downstream issue.** When `bundles` files `authoring-tools#7`, that
issue is the whole conversation. `authoring` asks its questions there, `bundles`
answers there, the conclusion is recorded there. The upstream issue `bundles#41`
gets exactly two protocol comments: one linking out, one carrying the conclusion
back.

Every protocol comment opens with a machine-readable header and a visible
attribution line:

```markdown
<!-- session-relay:v1 from=bundles repo=skomp/courseware-bundles ref=2eac95 kind=question seq=3 blocking=yes -->
**`bundles` → `authoring`** · question · 3 of 10
```

Field by field, because two of these were previously left to inference:

- `from` is the sender's **session name**, as `ListAgents` prints it.
- `repo` is the **sender's own bound repository** — never the issue's repository,
  which is already known from the issue the comment sits on. It is what lets a reader
  of `authoring-tools#7` see that the question came from the bundles side.
- `ref` is the sender session's **short ref**, copied from `ListAgents` (`2eac95`).
  A session never invents one, and a session that cannot read its own ref omits the
  field rather than guessing.
- `blocking` appears in two places and they describe different things. **A signal
  reports how the sender wants this delivery scheduled now; a header records what the
  sender believed when it wrote that comment.** Four rules follow, and the fourth is
  the one a live test found missing:
  1. A sender sets both from one judgement at the moment it writes. They agree when
     the sender is correct.
  2. A receiver holding a signal uses the signal's value. It is the newer of the two
     and it is addressed to this delivery.
  3. A receiver with no signal reads the newest protocol comment's header. That is the
     recovery path.
  4. A receiver **compares the two before scheduling** — this is a step it performs,
     not a condition that happens to fire. Measured on 2026-09-13: stating the rule as
     a condition produced a session that never compared, because nothing told it to
     look. Seeing them differ, it **uses the signal, continues, and reports the
     disagreement in its reply, quoting both values.** It is a defect of the sender. It is not a reason to
     stop. Measured on 2026-09-13: a session that met this stopped and asked a human,
     which is right when the protocol is silent and wrong once it says what to do.
- `seq` is this sender's comment count on this issue, starting at 1. The issue body
  counts as 1 when this sender filed the issue to open the thread.

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
| `session-relay:open` | A cross-repo thread is live on this issue | added when the thread's first protocol header is written — at filing for an issue filed to open a thread, with the first protocol comment on an issue that already exists — and removed at conclusion |
| `session-relay:stalled` | The thread hit the cap or a loop and is waiting on the human | added at a stuck exit |

Issues Claude files also carry `created-by-claude`, per `tracking-work`. Labels are
created on first use with `gh label create`.

### Manual recovery

A signal reaches only a running session. When one is missed, recovery is the human
asking — "are there new issues to discuss?" — and the answer must be cheap to
produce. That is what `session-relay:open` is for:

```sh
gh issue list --state open --label session-relay:open --json number,title,updatedAt
```

Read only the newest protocol comment of each result. **Do not read every open issue
and every comment.** A recovery check that costs a large fraction of the context
window is worse than the missed signal it repairs.

### Envelope discipline

**The skill must not consume a message it was not meant to receive.** A session
receives messages for many reasons, and other skills — present or future — define
their own. This protocol owns exactly one shape and must be inert for everything
else.

**The prefix names the protocol, not the skill and not the message type.** It is
`session-relay:` because that is the name of the protocol and of the plugin, and
because both of the obvious alternatives are worse. A prefix carrying the receiving
skill's name would make the sender depend on the receiver's implementation: rename
the skill and every header already posted into a GitHub issue is retroactively
wrong, and those comments are permanent. A prefix carrying the message type
(`triage:`, `question:`) would claim four generic English words for one protocol. A
wire format must outlive the code that reads it, so it names the only thing that
does not move.

**The prefix is both the trigger and the guard, and they are different
mechanisms.** The guard below runs inside a skill that is already in context. What
puts it there is its frontmatter `description`, which is the only retrieval
mechanism a skill has. So the description of `handling-an-inbound-ping` must name
the literal string `session-relay:` and must say that the skill is inert for anything else.
A description that says "handles messages from peer sessions" routes every protocol
to this one skill and makes the guard the only thing standing between them.

Written that way, each protocol routes itself by its own prefix and needs no central
dispatcher. That claim is untested — it is the same retrieval property this
repository's `README.md` already admits is unproven for all six existing skills — so
it is a verification item below, not an assumption.

The guards run in this order, and the order is the point:

1. **Does the message body begin with `session-relay:`?** Test the **body**, not the
   raw delivered text. `SendMessage` wraps what it delivers. **The wrapper's exact
   shape has not been observed** — it is expected to be something like
   `<cross-session-message from="...">` around the sender's text, and Verification
   item 1 below exists to record what actually arrives. The rule does not depend on
   the shape: a guard that tested the delivered string for a leading
   `session-relay:` would reject every real signal that arrives wrapped in anything at
   all and leave the protocol inert in both directions, while still passing any test
   where a human typed the signal by hand. Strip whatever the transport put around the
   message, then test the first line of what the sender actually wrote.

   If it does not begin with `session-relay:`, it is not this protocol's.
   Ignore it completely: do not act, do not reply, do not report it as unrecognised,
   do not mark it handled. Hand it back to the session's normal handling, which may
   include another skill. **A reply is a form of consumption** — answering
   `not-mine` to a message that was never a relay message claims it.
2. **Is the version supported?** `session-relay:v1` is understood. A higher version means the
   sender knows something this receiver does not. Reply
   `session-relay:v1 unsupported version=<v> <subject>` and tell the human. Do not guess at the
   semantics of a version you do not implement.
3. **Is the repository mine?** The ownership guard, *Addressing* step 3.
   **This guard is skipped for a control reply.** `mine`, `not-mine`, `not-enabled`
   and `unsupported` are answers to a message this receiver already sent, so the
   repository or issue they name is the one this session addressed, not a claim about
   who owns the work. Guard 3 exists to stop a session acting on another repository's
   issue; run on a session's own replies it would answer `not-mine` to every one of
   them, and no exchange that depends on a reply — addressing, refusal, version
   mismatch — could ever complete. `whois` is the one control value the guard does run
   on, because guard 3 is the question a `whois` asks. Guards 1, 2 and 4 run on all
   five.
   Then: **is the protocol enabled here?** A session bound to the right repository
   whose `CLAUDE.md` carries no declaration replies
   `session-relay:v1 not-enabled <subject>` and tells its human partner once. The two
   answers are different facts and the sender needs to tell them apart: `not-mine`
   means keep looking, `not-enabled` means stop looking and talk to a human.
4. **Is the `kind` in one of the two vocabularies?** The five comment kinds and the
   five control replies are both valid; see *Two vocabularies* above. If it is in
   neither, reply `session-relay:v1 unsupported kind=<kind> <subject>` and tell the human.
   An unknown `kind` inside a known version is a protocol error, not a message to
   improvise on.

Only a message that passes all four reaches the decision rule below. Guards 2 and 4
reply because the message *was* addressed to this protocol and silence would strand
the sender. Guard 1 stays silent because the message was not.

### Handling an inbound signal

**Control replies never reach the decision rule.** `mine`, `not-mine`, `not-enabled`
and `unsupported` answer a message this session already sent; they name no issue and
carry no `blocking` field, so there is nothing to dispatch. They return to the outbound
half, which is waiting for them, and `whois` is answered inside guard 3. A control
reply that answers nothing this session sent is a stray: it is reported to the human
and not replied to. Only the five comment kinds are work.

After the four guards above, for a comment kind:

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

The subagent cannot read its parent's `ListAgents` entry, so **the session fills its
own name and ref into the boilerplate before dispatching**. A subagent that had to
discover them would guess, and `ref` is the one field the spec forbids inventing.

On the recovery path, `blocking` is read from the newest protocol comment's header,
not assumed — an issue picked up late is as likely to be blocking as one that arrived
by signal.

The subagent's constraints, which go in its dispatch verbatim:

- It owns no files. It reads, and it runs `gh`. It never edits, stages or commits.
  The only things it writes are GitHub issue comments and the two `session-relay:`
  labels on the issue it was sent to. Both are in GitHub, not in the checkout.
- It signs comments with the **session's** name and ref, not its own.
- If it needs a decision from the human, it returns to the session and reports. It
  never asks. A subagent asking the human is `parallel-sessions` §4 again.
- It emits the outbound signal itself only if it wrote a comment that needs an
  answer, following the same rule as the session.
- **It carries the label transition with the comment that causes it**: a `conclusion`
  removes `session-relay:open`, a `stalemate` replaces it with
  `session-relay:stalled`, and any other kind adds `session-relay:open` if the issue
  does not already carry it. **The grant includes `gh label create` for those two
  labels in this session's own repository**, with the fixed name, colour and
  description — a label that does not exist cannot be added, and deferring its creation
  to the parent reopens the same window as deferring the transition. It is bounded to
  two known labels in one repository, and the subagent invents none of their fields.

The alternative — returning every label transition to the parent session — was
considered and rejected. The parent would have to be interrupted at an arbitrary
moment to finish a subagent's write, which is exactly the interruption the subagent
exists to prevent, and until that happened the manual recovery check would keep
returning a thread that has already concluded. A label is not a file and not in the
checkout, so permitting it costs the no-edit rule nothing. Step 4 of a stuck exit does
return to the session, because that step needs the human.

### Termination

Three exits.

**Conclusion.** A `kind=conclusion` comment on the downstream issue stating what was
decided and why, cross-linked into the upstream issue, `session-relay:open` removed. Each
session closes only its own repository's issue, and only when the fix lands.

**Cap.** Ten comments carrying your own `from=` on that issue. Count by reading the
thread's protocol headers, not by memory.

**Loop.** A checkable test rather than a judgement: *before posting, compare the
draft against your own earlier comments on this thread. If it asserts no new fact
and requests nothing new, that is the loop.*

Both stuck exits do the same thing:

1. Post one `kind=stalemate` comment: what is settled, what is still open, what each
   side believes.
2. Replace `session-relay:open` with `session-relay:stalled`.
3. Signal the peer that the thread is closed, so a peer mid-compose does not post an
   eleventh comment.
4. Raise the specific decision with the human **in the session that owns the work**.

Steps 1 to 3 belong to whoever posted the comment, session or dispatched subagent.
Only step 4 returns to the session.

The issue stays open. A closed issue loses a real open question, and closing is
outward-facing.

## Files

```
plugins/session-relay/
  .claude-plugin/plugin.json
  skills/coordinating-across-repos/SKILL.md
  skills/handling-an-inbound-ping/SKILL.md
```

Plus an entry in `.claude-plugin/marketplace.json` and a fifth row in `README.md`.

## Verification

The other six skills in this repository are untested, and the README says so. This
one is testable before it ships, and the live courseware fleet is the rig.

1. **Prove the description fires on the prefix alone, and record what the receiver
   actually sees.** Send a session a bare
   `session-relay:v1 triage <owner>/<repo>#1 blocking=no` and nothing else — no surrounding
   explanation, no mention of issues or peers. **Write down the raw text as it arrived**,
   wrapper included: guard 1 depends on it, and a hand-typed signal is the one case
   where nothing can be prepended, so this is the only item that can catch a wrapper
   the guard does not expect. The skill must load. If it does not,
   the prefix does not route, and a central dispatcher becomes necessary rather than
   optional. Record the result in the router repository's first issue, which is waiting
   on exactly this answer.
2. **Prove the skill ignores what is not its own.** Send a session an ordinary
   message with no `session-relay:` prefix while the skill is loaded. It must do nothing at
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
   `session-relay:open` ones.

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
