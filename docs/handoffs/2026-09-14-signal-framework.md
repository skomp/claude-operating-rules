# Handoff — a signal framework plugin, with `session-relay` backported onto it

**Written** 2026-09-14, at the end of the session that built `session-relay`.
**Tracked in** `claude-operating-rules#26`. Related: `#24`, `#17`, `#15`, and the router repository's first issue.
**Status** design agreed in outline, nothing built.

---

## What to build, in one sentence

A plugin that lets a person **declare a communication protocol as a state machine bound to a
message prefix**, checks declared protocols against each other **at installation**, and
carries the content of a conversation **without ever inspecting it**.

Then re-express `session-relay` as the first protocol declared on it.

## Why, and what the evidence actually is

`#24` records that sessions invent a way to coordinate when nobody gives them one. On
2026-09-13 two sessions in this repository invented six conventions in one day, none
requested: a freeze during a history rewrite; an explicit completion signal, because a
session reporting `idle` may be unfinished; a provenance label on relayed decisions;
ref ownership with a disclosure rule; hand over measurements and not conclusions; and a
correction path.

**Every one was a good rule. Every one existed only in two transcripts the author could not
read.** The defect was never the invention — it was that the agreements were invisible,
pair-specific, renegotiated each time, and detectable only by a person watching.

`#24` answers with a prohibition. This plugin answers by making the invention declarable,
checkable and readable. That is the better answer if it can be built.

**One caution about the evidence.** The six conventions are verified: they are in this
session's own transcripts. The author also reports the same behaviour across a fleet of four
sessions in three other repositories; **nobody has read those transcripts.** Do not cite the
fleet as established.

---

## The design, as far as it is settled

### Three layers, each checkable alone

| Layer | Holds | Checked by |
|---|---|---|
| **Channel** | which issue, who holds it, who acts next | linearity |
| **Protocol** | states, legal message kinds per state, the cap, terminal states | product construction, at installation |
| **Content** | the comment body | **nothing, deliberately** |

The third row is the point. The framework never holds content, so it can never *appear* to
verify content. A machine that looked like it checked meaning would be worse than prose,
because a reader would believe the semantic rules were verified.

### The state is a fold over the issue, not a runtime

`session-relay` has no executable parts, and that property should survive.

It can. Every protocol comment already carries `from`, `kind` and `seq` in an HTML header, so
**the comments of one issue are a word in the language of the protocol**. Current state is a
fold over that word. Nothing needs to run, nothing needs to be stored, no daemon, no state
file. The durable record *is* the tape.

### Prefix registry, and conflict detection at installation

A protocol claims a prefix. The plugin matches an incoming message by prefix, finds the
machine, and knows from the state which role acts next and which kinds are legal.

If protocols are regular, conflict detection is a product construction: two machines conflict
when a word both accept leads to different required actions. The Myhill–Nerode congruence
gives the canonical minimal machine, so *"are these the same protocol"* and *"do these
diverge after a shared prefix"* are both decidable. **The check runs once, at installation.**

**This subsumes the router.** The router repository's open question — who dispatches an
envelope, and what happens to one nobody claims — is answered statically: an unclaimed prefix
is a machine-not-found and is reported rather than dropped; two protocols claiming one prefix
are an installation error rather than a runtime race.

### Channel and content are separate, as in the π-calculus

`session-relay` already does name-passing without saying so: a signal carries
`<owner>/<repo>#<number>` and routing flags and never a question or an answer; the
conversation happens on the named channel. Formalising it buys **delegation** — send the
channel to a third session, which continues without you.

That matters because `session-relay` is strictly two-party and the live test met the limit on
its first run: the authoring session found no grader in its own repository and said the cause
might be in a released package or the runner — a third place it had no way to hand the thread
to. **In a layered project that is the normal shape of a real fault, not an edge case.**

**The limit to enforce:** full π-calculus mobility makes the useful properties undecidable.
Linear channels and session types keep them decidable. So: one holder at a time; bounded
delegation; no unbounded channel creation. Write the restrictions into the design — a
framework permitting the general case cannot give the installation check it exists for.

---

## The backport, which is the framework's first test

Re-expressing a protocol already known to work asks: *can the formalism express it?* Every
part it cannot express is a framework defect found before anything depends on it. Every part
the formalism forces to be explicit is a finding about `session-relay`, where prose left it
implicit.

Each row below is a fact `session-relay` already implements. The answers are known, so each
is a test with a expected result:

| Fact | What the framework must express |
|---|---|
| Four guards in fixed order; guard 1 never replies | a pre-state that consumes nothing and emits nothing |
| Control replies skip guard 3; `whois` does not | one transition exempt from a check, one not |
| The cap is ten comments per sender per issue | a bounded counter — states, not prose |
| A `conclusion` signals although it needs no answer | a terminal transition that still emits |
| A stuck exit swaps a label and escalates | a terminal state with a non-message effect |
| The issue body is the first comment, `seq=1` | the initial state is created by the channel, not by a message on it |
| The signal and the header can disagree about `blocking`; the signal wins | a state carrying a value a message can contradict |

**The last row is the hardest and the most valuable.** `#17` records a rule that was correct
and never fired, because it was written as a condition — "when you see them disagree" —
and nothing told a session to compare. **A state machine cannot express a condition nobody
evaluates: a transition is present or absent.** If the backport can express that rule, the
framework has earned its place.

**What the backport cannot test: delegation.** Design the channel layer for it anyway, and do
not mistake a passing backport for evidence that part works.

---

## Decisions the framework must make, which this session did not

1. **Does the framework have executable parts?** `session-relay` deliberately has none. An
   installation-time conflict checker is code. That is a real departure and should be a
   conscious one — it may be the right trade, since the check runs once and never in the
   message path.
2. **What language declares a machine?** JSON, a DSL, prose the plugin parses. Whatever it is,
   a human must be able to read a protocol and see the cap.
3. **Where does a declared protocol live** — in the plugin, in the repository that uses it, or
   in the `CLAUDE.md` declaration that already opts a repository in?
4. **What happens to a thread whose protocol is uninstalled or upgraded mid-conversation?**
   The trace is durable; the machine may not be.
5. **How does a role map to a session?** `session-relay` binds one session to one repository
   by `git remote get-url origin`. Linearity suggests the same shape, but delegation needs a
   role to move.

---

## Measurements to carry over, verbatim

These cost a day to obtain. Do not re-derive them, and do not soften them.

- **A signal arrives wrapped.** The real form is a fixed lead line, a
  `<cross-session-message from="uds:…sock" from-name="…" from-mode="prompting">` envelope, an
  `<agent-message from="<agentId>">` envelope nested inside **only when a subagent sent it**,
  and a fixed trailing advisory. A guard must strip the wrapper before matching.
- **A pane is not evidence.** The Claude Code TUI runs on the alternate screen, so
  `tmux capture-pane -S -` returns about 24 lines regardless of `history-limit`, and tool
  calls are never in the buffer. Only a session's transcript JSONL under `~/.claude/projects/`
  can say what a session read. Two separate false reports on 2026-09-13 came from reading a
  pane as data — see `#15`, instances 9 and 10.
- **`ListAgents` is not available to a subagent.** A dispatch that tells an agent to read peer
  session names will fail. Confirm a peer by successful delivery instead.
- **A subagent's `SendMessage` goes out under the parent session's address**, so a subagent
  driving a protocol cannot receive its own replies.
- **Live verification results for `session-relay`:** items 1, 2, 3, 4, 5, 7 PASS; item 6 NOT
  RUN at the time of writing. Evidence in
  `docs/superpowers/verification/2026-09-13-session-relay-live.md`. Item 2 passed with a
  finding: the session volunteered relay commentary inside an ordinary reply, which guard 1
  forbids.

---

## Prior art worth reading before designing

- **Multiparty session types** — this design is close to them; well-formedness and projection
  to per-role machines are the solved problems here.
- **Communicating finite state machines** — Turing-complete in general, which is why the
  restrictions above are not optional.
- **π-calculus, and session delegation** — for the channel layer and name passing.
- **Myhill–Nerode** — the canonical minimal automaton, and why the installation check is
  decidable.

---

## Where things stand

- `session-relay` is written, reviewed and pushed at `origin/session-relay`, **not merged**.
- `origin/main` moved while it was built; the branch needs a catch-up before it lands.
- `#24`'s rule is in `parallel-sessions` and the README, but **the global `CLAUDE.md` tripwire
  is not applied** — until it is, that rule is documentation and not prevention.
- A live test rig exists: `skomp/courseware-bundles` and `skomp/courseware-authoring`, private,
  seeded with the skills and the opt-in declaration, with two sessions in tmux `cwbundles` and
  `cwauthor`. Delete the repos when done.

## The first thing to do

**Run item 6 before designing anything.** It exercises the cap, the loop exit and the
stalemate — the three behaviours this framework would make structural. If they hold as prose,
the machine is a refinement. If they do not, item 6 is the measurement that justifies the
whole plugin, and the design starts from evidence rather than from an intuition.
