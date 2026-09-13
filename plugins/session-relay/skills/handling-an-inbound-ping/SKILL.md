---
name: handling-an-inbound-ping
description: "Read when a message arrives carrying the envelope `session-relay:` — the prefix of the cross-repository issue protocol — or when your human partner asks whether there is anything new to discuss with a peer repository's session. The skill is inert for every message that does not carry that prefix: it owns one envelope, it has no opinion on the rest, and it never answers a message that is not its own."
---

# Handling an Inbound Ping

A peer session signals you when it has written something to a GitHub issue that you
need to read. **The signal carries a reference and routing flags — never a question, an
answer or an argument.** The conversation itself lives in the issue.

`coordinating-across-repos` owns the preconditions, the wire format and the outbound
half of this protocol. This skill owns the short distance between a message arriving
and the work starting: the guards, who handles it, and what a subagent sent to handle
it is allowed to do.

**Most messages you receive are not this protocol's.** Section 1 is what keeps it that
way.

## 1. Envelope discipline

**Never consume a message you were not meant to receive.** A session receives messages
for many reasons, and other skills — existing and not yet written — define their own
shapes. This protocol owns exactly one shape and must be inert for everything else.

Run four guards, in this order. The order is the point.

| # | Guard | On failure |
|---|---|---|
| 1 | Does the message **body** begin with `session-relay:`? | **Say nothing at all** |
| 2 | Is the version one you implement? | `session-relay:v1 unsupported version=<v> <subject>` |
| 3 | Is this session bound to that repository — and then, is the protocol enabled here? **Skipped for a control reply.** | `session-relay:v1 not-mine <subject>` or `session-relay:v1 not-enabled <subject>` |
| 4 | Is `kind` in one of the two vocabularies? | `session-relay:v1 unsupported kind=<kind> <subject>` |

Only a message that passes all four reaches section 2.

**`mine`, `not-mine`, `not-enabled` and `unsupported` skip guard 3, and they never
reach section 2 either.** The reason is one fact, and it is worth stating once so that
nobody puts the test back: **a control reply is an answer to a message this session
already sent, so the repository or issue it names is the one this session addressed —
it is not a claim about who owns the work.** Guard 3 exists to stop this session acting
on another repository's issue. It has no business filtering the answers to questions
this session asked, and a session that ran it on its own replies would answer
`not-mine` to every one of them and never learn anything it asked for. `whois` is the
one control value guard 3 does run on, because guard 3 is precisely the question a
`whois` asks. Guards 1, 2 and 4 run on all five.

### Guard 1 replies to nothing, and that is the whole guard

**Test the body, not the raw delivered text.** `SendMessage` wraps what it delivers.
**The wrapper's exact shape has not been observed** — it is expected to be something
like `<cross-session-message from="...">` around the sender's text, and no live signal
has yet arrived to confirm it. **The rule does not depend on the shape:** strip whatever
the transport put around the message, then test the first line of what the sender
actually wrote. A guard that tested the delivered string for a leading
`session-relay:` would reject every real signal that arrives wrapped in anything at all,
leaving the protocol inert in both directions — while still passing every test where a
human typed the signal by hand, which is how such a guard gets written and never
exercised.

If that line does not begin with `session-relay:`, the message is not this protocol's.
Ignore it completely: do not act on it, **do not reply**, do not report it as
unrecognised, do not mark it handled. Hand it back to the session's normal handling,
which may include another skill that does own it.

**A reply is a form of consumption.** Answering `not-mine` to a message that was never
a relay message claims it: the sender learns that something read its message and
rejected it, another skill's message has been answered by this one, and a protocol that
was supposed to be invisible here has made itself the responder. Silence is not a
failure to handle the message. It is the correct handling.

### Guards 2, 3 and 4 reply; guard 1 never does

The message *was* addressed to this protocol, so silence would strand the sender —
which waits, or worse, retries. Each of these three guards sends exactly one reply, by
`SendMessage`, back to the session that signalled you. Never answer a control message
with a GitHub comment; control replies are never written into an issue.

**Guard 2 — the version.** `session-relay:v1` is understood. A higher version means the
sender knows something this receiver does not. Reply
`session-relay:v1 unsupported version=<v> <subject>` and tell your human partner. **Do
not guess at the semantics of a version you do not implement** — a plausible guess is
worse than a refusal, because the sender cannot tell it from real support.

**Guard 3 — ownership, then enablement.** It runs on a comment kind and on `whois`,
and **never on `mine`, `not-mine`, `not-enabled` or `unsupported`** — see the exemption
above; reading which word follows the version is a lookup, not guard 4. When it does
run it asks two questions, in that order, and both are answered from the signal and two
local reads. **Neither one touches the network, the
peer's tree or the issue**: no clone, no `gh issue view`, no triage. The signal already
names the repository; you only have to say whether it is yours and whether you are
playing.

- *Bound?* This session's repository is the one `git remote get-url origin` prints in
  its working directory. A different repository, or no GitHub origin at all, gives
  `session-relay:v1 not-mine <subject>`.
- *Enabled?* A `## Session relay` declaration in this repository's `CLAUDE.md`, saying
  enabled. **Inbound, enablement is binary**: the section is present and says enabled,
  or it is not. Absent, or a refusal, gives `session-relay:v1 not-enabled <subject>`.
  The declared peer list bounds where *you* may file and signal; it is an outbound rule
  and never an inbound test, because the only repository an inbound signal names is your
  own. What you say to your own human partner after that reply is owned by
  `coordinating-across-repos` §1, *When a peer signals a repository that has not opted
  in*. Read it there; it is not repeated here.

**The two answers are different facts, and the sender needs to tell them apart.**
`not-mine` means keep looking. `not-enabled` means stop looking and talk to a human.

**Guard 4 — both vocabularies are valid.** `kind` names either a comment or a control
reply, and a receiver accepts both. **`coordinating-across-repos` §6 owns this
vocabulary**, including which of the two each value belongs to and why a reply carries
a `<subject>` rather than a `ref`. The ten values are listed here only because guard 4
cannot run without them; if the two lists ever disagree, §6 is right.

| Vocabulary | Values |
|---|---|
| Comment kinds | `triage`, `question`, `answer`, `conclusion`, `stalemate` |
| Control replies | `whois`, `mine`, `not-mine`, `not-enabled`, `unsupported` |

**A guard that rejected `whois` would make addressing impossible**, because the message
that finds the right session would be refused by every session that could answer it —
including the one session that was going to say yes. A `kind` in neither list is a
protocol error inside a version you do implement, not an invitation to improvise: reply
`session-relay:v1 unsupported kind=<kind> <subject>` and tell your human partner.

### Answering a `whois`

A `whois` that passes all four guards is about **this** session's repository — guard 3
already answered `not-mine` for every other one. So it is answered, not triaged, and it
reads nothing:

```
session-relay:v1 mine <owner>/<repo>
```

That is a complete message. A control signal carries no issue number of its own.

`<subject>` in any reply is defined in `coordinating-across-repos` §6, together with
the reason it is not called `ref`. Read it there before you send one.

## 2. The decision rule

**A control reply is not work, and it never reaches this rule.** `mine`, `not-mine`,
`not-enabled` and `unsupported` are answers to a message *this* session already sent.
They name no issue and carry no `blocking` field, so there is nothing to dispatch and
nothing to decide. Hand each one straight to the outbound half that is waiting for it:
`coordinating-across-repos` §6 says what every one of them means and what this session
does next. A `whois` is answered in section 1 and stops there.

**A control reply that answers nothing this session sent is a stray.** Do not act on
it and do not reply to it — a reply would start an exchange nobody asked for. Tell
your human partner what arrived and from which session, and carry on.

What does reach this rule is a comment kind: `triage`, `question`, `answer`,
`conclusion` or `stalemate`. That is work, and the only question is who does it — a
subagent, or this session itself.

```
blocking=no  ─────────────────────→  subagent; this session carries on
   │
blocking=yes
   │
   └─ overlaps the in-flight task?  ──no──→  subagent
         │
        yes  ─────────────────────→  finish the current step, then answer here
```

**"Overlaps" is the file-ownership notion `parallel-sessions` already defines:** does
the issue concern a path the in-flight task owns? When it does, a subagent would be
reading a tree that moves under it — the same reason `parallel-sessions` makes a
reviewer pin a commit before it quotes a `file:line`. Pinning does not rescue it here,
because the thing the subagent has to understand is the work still being written.

**When the signal and the comment header disagree about `blocking`, use the signal.**
It is the newer value and it is addressed to this delivery; the header records only
what the sender believed when it wrote that comment. Continue the work, and say in
your reply that the two disagreed — it is a defect of the sender, not a reason to
stop. Stopping to ask is right while a protocol is silent and wrong once it has
answered. `coordinating-across-repos` §8 owns the field and carries the full rule.

`blocking=yes` is the sender's statement that it cannot continue without an answer, not
a priority field. Treat it as true. If a peer marks everything blocking, that is a
defect to raise with its human partner, not a flag to start discounting.

Either way the reading is frugal: the issue named in the signal, its protocol comments,
and the code they point at. Nothing else.

## 3. Subagent dispatch boilerplate

Paste this verbatim into the dispatch. Fill in the placeholders; change nothing else.

> **You own no files.** You read, and you run `gh`. You never edit, stage, commit,
> branch, tag or push — not in this repository and not in any other. The only things you
> write anywhere are GitHub issue comments, the two `session-relay:` labels on the issue
> you were sent to, and — only when one of those two labels does not exist yet — that
> label itself, in **this** repository, with the exact name, colour and description in
> `coordinating-across-repos` §9. All of those live in GitHub, not in the checkout, and
> none of them is in any repository but this session's own.
>
> **Triage `<owner>/<repo>#<number>`.** A peer session signalled it with
> `kind=<kind>`. Read that issue and its protocol comments, and read code only where
> the issue points. Do not survey the repository.
>
> **Sign every comment with this session's identity, not your own:** `from=<session
> name>`, `ref=<session short ref>`. Those are the literal values to write. You never
> invent either of them and you never substitute your own — you are this session
> speaking, not a third party. The comment format is defined in
> `coordinating-across-repos` §8; follow it exactly, including the visible attribution
> line.
>
> **If you need a decision from our human partner, come back and report it. Never ask
> them yourself.** A subagent asking the human is `parallel-sessions` §4 again: the
> answer arrives in a chat that does not own the work, and this session never learns
> it was asked.
>
> **Signal the peer yourself only if you wrote a comment that needs an answer, or that
> ends a thread the peer is waiting on.** That is the rule in
> `coordinating-across-repos` §3 and it is unchanged for you. A comment that needs
> nothing back produces no signal.
>
> **Carry the label transition with the comment that causes it.** The labels are what
> the manual recovery check reads, so a comment that ended a thread next to a label
> that still says the thread is live is a finished thread nobody can see has finished.
> A `kind=conclusion` comment: remove `session-relay:open`. A `kind=stalemate` comment:
> remove `session-relay:open` and add `session-relay:stalled`. Any other kind leaves
> the labels alone, except that it adds `session-relay:open` if the issue does not
> carry it yet. **If the label does not exist in this repository, create it** with the
> `gh label create` in `coordinating-across-repos` §9, copying its name, colour and
> description exactly — invent none of the three. This is the one exception to owning
> nothing: a label is in GitHub, not in the tree, and a label call you come back to
> this session to make leaves the thread invisible to the recovery check for as long as
> that takes, which is the window the transition exists to close.
>
> **A stuck exit is still not yours to escalate.** Post the `kind=stalemate` comment,
> swap the labels, signal the peer — then come back and report. Raising the decision
> with our human partner is step 4 of `coordinating-across-repos` §10 and it belongs
> to this session.
>
> **Report back:** what the issue says, what you wrote, which labels you changed,
> whether you signalled and whom, and any decision you need from this session.

**Before you dispatch, replace every placeholder with a literal value** — the issue
reference, the `kind`, and `<session name>` and `<session short ref>` as `ListAgents`
prints them for this session. A subagent cannot read its parent's `ListAgents` entry, so
one left unfilled is one a subagent will guess at, and `ref` is the field that must
never be invented: a guess signs a permanent GitHub comment with an identity nobody can
trace.

## 4. Manual recovery

A signal reaches only a running session, so signals are missed: no session was open in
that repository, the peer was on another machine, the host did not list it. Recovery is
your human partner asking — "are there new issues to discuss?"

**The check itself is `coordinating-across-repos` §9**: one `gh issue list` filtered to
`session-relay:open`, then the newest protocol comment of each result and nothing more.
Run it from there. The reason it must stay that cheap is written there too, and it is
not repeated here.

What this skill adds is what happens next. **That newest comment's header carries
`blocking`**, so section 2's decision rule applies to a recovered thread exactly as it
does to a live signal — an issue picked up late is as likely to be blocking as one that
arrived by signal, and you read the flag rather than assuming it.

**Nothing else looks.** There is nothing behind this check but your human partner's
question; `coordinating-across-repos` §3 owns that rule and names what the protocol
refuses to install to get it.

## Red flags — stop

| About to… | Do this instead |
|---|---|
| Reply `not-mine` to a message whose body does not begin with `session-relay:` | Say nothing. A reply is a form of consumption |
| Test the raw delivered text for the prefix | Strip whatever the transport wrapped around the message first. Its shape is unconfirmed, but if the delivered text is wrapped at all the positional test rejects every real signal |
| Claim a message because it mentions another repository, an issue or a peer session | Run guard 1. This skill owns one envelope and nothing else |
| Reject `whois` as an unknown `kind` | Accept both vocabularies. Refusing `whois` makes addressing impossible |
| Answer `not-mine` to a `mine`, `not-mine`, `not-enabled` or `unsupported` reply because it names a repository that is not yours | A reply names the repository you addressed, not a claim about who owns the work. Guard 3 does not run on a control reply, and neither does the decision rule |
| Answer `not-mine` because this repository has not opted in | Answer `not-enabled`. `not-mine` means keep looking; `not-enabled` means stop looking |
| Clone the peer, or open the issue, to answer a guard | No guard reads the issue or the network. Ownership is `git remote get-url origin`, enablement is this repository's `CLAUDE.md`, and the signal names the rest |
| Guess at the semantics of a version you do not implement | `session-relay:v1 unsupported version=<v> <subject>`, and tell your human partner |
| Answer a control message with a GitHub comment, or write one into an issue | `SendMessage` back to the sender's session name. Control replies never appear in an issue |
| Restate the comment header format, the `<subject>` grammar, the recovery command or the not-enabled offer here | `coordinating-across-repos` §8, §6, §9 and §1 own them. Two copies of one rule is the `completing-a-correction` failure |
| Dispatch a subagent for a `mine`, `not-mine`, `not-enabled` or `unsupported` reply | A control reply is an answer to something you sent, not work. Take it to `coordinating-across-repos` §6 |
| Hand a `blocking=yes` signal that touches your in-flight files to a subagent | Finish the current step, then answer in this session |
| Let the subagent edit a file, stage anything, sign with its own name, or ask your human partner | Paste section 3's boilerplate unchanged, with the name and ref filled in |
| Post a `conclusion` or `stalemate` and leave the label transition for later, or for this session | Whoever posts the comment swaps the label in the same act. A finished thread still labelled `session-relay:open` comes back from the recovery check for ever |
| Read every open issue to answer "is there anything new?" | Run the `session-relay:open` check in `coordinating-across-repos` §9, then the newest protocol comment of each result |
