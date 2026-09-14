# Evaluation — can distributed-systems protocols be declared on `machines`?

**Written** 2026-09-14, during cycle A. **Asked by** the author, in two parts: *"can I implement
Paxos on this?"* and *"investigate if I could implement a gossip protocol."*
**Evaluates** `docs/superpowers/specs/2026-09-14-machines-framework-design.md` as built in
cycle A. **Status** analysis only; nothing here was implemented or tested.

---

## The short answer

| Protocol family | The exchange | The process |
|---|---|---|
| **Paxos** (single-decree) | expressible | not expressible |
| **Raft / KRaft** | expressible | not expressible |
| **Gossip / anti-entropy** | expressible | not expressible |

The column split is the finding. **This framework models a bounded conversation: a question, an
answer, an end.** Consensus and gossip are *continuous processes assembled out of bounded
exchanges*. The framework can describe the exchange and cannot describe the process.

That is not three separate gaps. It is one boundary, met three times.

## What the framework gives a protocol

Established by cycle A, and by the backport walk recorded in the spec's §10:

- States, roles, and transitions on `(from, kind, by) → to`. **A transition fires on a message
  `kind` and on nothing else.**
- A cap on outbound (signalling) messages.
- Terminal states, with a checked guarantee that every state can reach one.
- Effects: transport verbs with typed arguments, and actions required of Claude.
- The channel's trace as the state. No runtime, no daemon, no stored state.

And, decisively for everything below:

- **No epsilon transitions.** Every transition requires a `kind`, so a state that consumes
  nothing can never be left. Nothing happens unless a message arrives.
- **No message attributes.** The machine sees a `kind`. It does not see a payload, a number, a
  version, or a flag. `session-relay`'s own `blocking=`, `seq=` and `ref=` are invisible to it —
  that is row 7 of the backport, and the spec accepts it.
- **A fixed role set.** Declared once. Occupancy is dynamic; the number of roles is not.

## Paxos

### Liveness — no, and it was worth understanding why

FLP: deterministic consensus is impossible in an asynchronous system with one faulty process.
Every practical algorithm escapes it through timeouts and partial synchrony. So liveness needs a
timer.

**An earlier draft of this evaluation said the framework structurally cannot have one. That was
wrong**, and the author supplied the counterexample: a **`wait` transport** — a verb whose
implementation sleeps — makes a timeout into a *local observation that produces a `kind`*. The
transport sleeps, returns, and something emits `timeout`. The engine still never executes; it
requires an effect, exactly as it does for `label.add`. Nothing persists between turns.

So a timer is expressible. What it is not:

- **It blocks the session.** The transport is called synchronously inside a turn. `sleep 300` is
  a session idle for five minutes with a human watching. The practical ceiling is seconds, not
  the minutes a leader-election timeout wants.
- **It fires only while a session is awake and in that state.** A real timer fires whether or
  not anyone is watching. This one detects *a silent peer, provided the detector is awake* —
  enough for two-party "the other side stopped answering", not a failure detector that runs
  unattended.

Paxos's liveness argument needs a timeout that eventually fires at a correct process.
*"Eventually, if a session is still open"* is not that guarantee.

### Safety — no, and this is the more interesting refusal

Paxos's safety proof rests entirely on comparing ballot numbers: `if n > highest_promised`. A
ballot number is **content**, and this framework refuses to look at content *by construction*,
not by omission. The machine sees a `kind`.

So the framework cannot express the single comparison the correctness argument turns on. This is
§4's stated boundary — *checkable: alternation, legal kinds, the cap; not checkable: whether a
sender set a flag honestly* — arriving at the most consequential possible case.

### Quorums

Roles are fixed and named, so there is no "any majority of N". There is `acceptor1`, `acceptor2`,
`acceptor3`. "Any 2 of 3" is enumerable as explicit states; the enumeration is combinatorial in
N and there is no general form.

### What is expressible

The message skeleton: `prepare → promise | nack → accept → accepted`. And one construction gets
further than it first appears:

> **Let the participants decide and report their conclusions as kinds.** A proposer counts
> promises itself — content work — then emits `quorum-reached`, which *is* a kind the machine can
> transition on. The machine enforces that `accept` cannot precede `quorum-reached`.

What that enforces is that the conclusion was **reported in a legal order**. What it cannot
enforce is that the conclusion was **true**. Structure, never meaning.

## Gossip and anti-entropy

Gossip fails in a different place from Paxos, and the difference is worth stating.

### The category mismatch, which is the real finding

Gossip is not a conversation that ends. It is a continuous process: periodically pick a peer,
exchange digests, reconcile. Its guarantee is probabilistic convergence over many rounds.

**Every check the framework performs assumes a protocol terminates.** Terminal states, "every
state can reach a terminal state", and the cap all encode *a conversation is a bounded exchange
that ends*. A gossip machine would have to either declare a cap it does not mean — "ten rounds
of gossip and then stop" is not gossip — or declare a bound so large it is decorative.

That is a **category mismatch, not a missing feature**. Paxos is refused because it needs to see
content. Gossip is refused because it is not a conversation.

### Membership is the second wall

Gossip is frequently *about* membership — SWIM, Serf, Cassandra's failure detector. Nodes join
and leave, and the protocol's job is to discover that.

The framework fixes the role set at declaration time. Under the negotiator design (spec §12)
occupancy is dynamic — a session takes or releases a role — but **the number of roles is not**,
because unbounded participant creation is full π-calculus mobility and costs the decidability the
install-time check depends on.

So: a cluster of **at most N**, with vacancies, is expressible. Open membership is not. And the
machine has no way to *know* how many roles are occupied — occupancy is channel-layer state, not
something the fold over a trace produces.

### Peer selection

Choosing a random peer is content work. With named roles, a machine would need a transition per
peer (`gossip-to-peer1`, `gossip-to-peer2`, …) and the participant would choose which to send.
Expressible for small fixed N, ugly, and it makes the declaration's size linear in the cluster.

### State merge

Version vectors, digests, deltas, reconciliation — all content, all invisible. The same wall as
Paxos ballots, reached by a different road.

### Convergence

Gossip's guarantee is that with high probability all nodes converge in O(log N) rounds. That is a
**statistical property over content across many runs**. The framework checks structural
properties of a single declaration. It cannot express convergence, let alone check it.

### What is expressible

**One anti-entropy exchange.** `digest → delta-request → delta → ack` has a defined shape, and
getting that shape wrong — sending a delta nobody asked for, acting on a digest from a superseded
round — is a real bug class. A machine can enforce it.

So: the exchange, yes. The epidemic, no.

## The general result

Everything these protocols need is something the framework **deliberately traded away in order
to be checkable**:

| What they need | What it would cost |
|---|---|
| decisions based on message *values* (ballots, versions, digests) | the content boundary — §4's guarantee that the framework can never *appear* to check meaning |
| a protocol that does not terminate | the termination check, which is the framework's headline guarantee |
| unbounded, dynamic membership | decidability — full π-calculus mobility, per §7 |
| unattended timers | a runtime, which §14's non-goals forbid (the `wait` transport is a partial, attended substitute) |

Each extension buys a protocol family and sells the install-time check. The spec already says
the decidability limit and the trust limit are the same limit; this evaluation adds that **the
expressiveness limit is that same limit a third time.**

## The thing to be careful about

**A machine that *looks* like it encodes Paxos, Raft or gossip is more dangerous than prose**,
because a reader will believe consensus safety or convergence was verified when only message
ordering was.

Spec §4: *"A machine that looked like it checked meaning would be worse than prose, because a
reader would believe the semantic rules were verified."* That warning was written about
`session-relay`'s loop test. It applies with far more force here.

**If such a machine is ever declared, its own prose must say that it checks sequencing and not
agreement.** That is a requirement on the declaration, not a note in this file.

## What this evaluation is not

No part of this was built or tested. It is reasoning from the shipped cycle A schema and from the
backport walk in spec §10. The `wait` transport does not exist; it is the author's proposal, and
its two limits above are derived, not measured.

**One consequence was found by this reasoning and does affect shipped behaviour** — the cap
counts only signalling transitions, so a loop of non-signalling transitions (such as
`wait → timeout → wait`) is uncapped, reaches a terminal state, and passes every check. It is
filed against `claude-operating-rules#28` as a second bound cycle B must add.
