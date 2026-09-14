# Design — `machines`, a framework for declared communication protocols

**Written** 2026-09-14. **Tracked in** `claude-operating-rules#26`. **Handoff**
`docs/handoffs/2026-09-14-signal-framework.md` on `origin/session-relay`.
**Status** design agreed; nothing built.

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
evidence, and it is recorded here so that nobody later reads the null as a result. See §9.

## 4. The three layers

| Layer | Holds | Checked by |
|---|---|---|
| **Channel** | which channel, who holds it, who acts next | linearity |
| **Protocol** | states, legal kinds per state, the cap, terminal states | product construction, at install |
| **Content** | the message body | **nothing, deliberately** |

The third row is the point. The framework holds no content, so it can never *appear* to
verify content. A machine that looked like it checked meaning would be worse than prose,
because a reader would believe the semantic rules were verified.

**Checkable:** alternation, the legal kinds in each state, the cap, termination, which
role acts next. **Not checkable:** whether a draft states a new fact, and whether a sender
set a flag honestly.

## 5. Layout

```
~/.claude-machine/
  machines/<publisher>/<name>/<version>/
      machine.yaml        closed data — states, roles, kinds, transitions,
                          cap, terminal states, effects
      transport/          the PUBLISHER'S CODE — narrow verbs only
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
legal?        yes | no, with the reason
holder        which role acts next
may_send      the kinds legal from here
remaining     cap headroom for this sender on this channel
terminal?     and if so, the required effects
```

Claude reads that and writes the content. **The framework never sees the content.**

The engine also gates the *outbound* message's envelope before it is sent. That is where
determinism pays: the engine refusing to emit a message past the cap is the cap becoming
structural. Item 6 showed a competent session doing this by hand; the engine removes the
requirement that the session be competent.

## 7. The declaration

**Closed language.** States, roles, message kinds, transitions, one declared cap, terminal
states, and a fixed effect vocabulary. **No expressions, no scripts, no callbacks.**

The closure is load-bearing twice over, and this is the design's central observation:

- `#26`'s third comment requires restricting the general π-calculus — one holder at a time,
  bounded delegation, no unbounded channel creation — because the general case makes the
  useful properties **undecidable**.
- Keeping the declaration closed is also what stops an installed machine being a **program**.

**The decidability limit and the trust limit are the same limit.** One restriction buys both.

**The cap** is declared per bundle and **counts only outbound messages the machine emits.**
It caps transitions, not comments — `session-relay`'s "ten comments per sender per issue" is
one machine's choice of value, not the framework's rule.

**Placement:** a fenced block inside the bundle's `SKILL.md`, beside the prose that explains
it — one file, edited in one act, reviewed in one diff. A cap that says ten in the machine
and twelve in the prose is hard to produce and obvious when produced.

### Contract, not body

The declaration schema is specified in the implementation plan as **field names, types and
the failure each field prevents**. Any YAML or code that appears in the plan is labelled a
proposal, per `writing-plans-and-dispatches` rule 1.

## 8. The transport, and the narrow cut

A bundle supplies transport code, because the engine cannot know how to reach an arbitrary
channel. **The framework provides the engine; publishers are responsible for their own
machines; the user makes a trust decision at install.**

**The cut is narrow.** The transport implements a fixed, small set of verbs — list the
messages on a channel, append one, send a signal, resolve a peer — taking JSON and returning
JSON, holding nothing between calls. **It never sees the machine, the state, or the cap.**

The consequence is the one that matters: a buggy or hostile transport **can misreport which
messages exist**, but it **cannot forge a transition, skip the cap, or fake a terminal
state**, because the engine is what counts and what decides. The framework's guarantees
survive bundles we did not write. That is the whole reason for having an engine.

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

**This subsumes the router.** An unclaimed prefix is a machine-not-found, reported rather
than dropped. Two protocols claiming one prefix are an installation error rather than a
runtime race. The router repository's first issue can close when this lands.

## 10. The backport, which is the framework's first test

Re-expressing a protocol already known to work asks: *can the formalism express it?* The
handoff's seven rows were walked against the design. **All seven are expressible.** Two
results are worth recording.

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
   front end, and **guard 1 is prose, not structure**, and the design says so.
2. **A thread whose machine is uninstalled or upgraded mid-conversation.** Proposal: the
   trace already names protocol and version; `~/.claude-machine/` keeps old versions; a
   thread pins the version it opened with; uninstalling a machine with live threads warns
   and names them.
3. **Update notification.** Record the installed ref, compare against the remote tag on a
   timestamp gate, report. **Never auto-update.**
4. **What bounds delegation.** `#26` requires that delegation be bounded by something
   stated. This design has not stated it.
5. **The transport's language and invocation mechanism.**

## 12. Sequencing — this is more than one plan

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

## 13. Non-goals

- The framework does not check meaning, and no part of it may appear to.
- The framework does not execute the declaration's *machine* — only its own engine runs.
- The framework does not vouch for a publisher's transport code.
- No daemon, no poller, no watcher, no runtime state store. The durable record is the trace.

## 14. Housekeeping carried into the plan

- `.claude/settings.local.json` in this worktree holds the **throwaway** spike hook. It is
  untracked, this repository has **no `.gitignore`**, and it must not be committed. Remove it
  once the §11.1 measurement is taken.
- `session-relay` is written, reviewed and pushed at `origin/session-relay`, **not merged**,
  and its branch is behind `main`. It is held by another session; it is not this work.
