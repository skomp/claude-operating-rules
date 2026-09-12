---
name: writing-plans-and-dispatches
description: "Read BEFORE anything another agent will execute. Load when you are about to write an implementation plan or spec document; write a dispatch prompt for a subagent; put code into a plan; label or scope an issue for an autonomous agent seat; or re-dispatch after an escalation that said a retry cap was exhausted. Applies alongside superpowers:writing-plans, which fires at the same moment."
---

# Writing Plans and Dispatches

Both rules are failures of the thing you hand an agent **before** it starts. By the time it reports, the cost is paid.

## Rule 1 — Plan code is untested code that looks authoritative

A GPU renderer project, 2026-08-20, uniform-editor branch. A seven-task plan was written containing complete code for every task — the skill asks for real code, not placeholders, and that was taken to mean *finished* code. Across eight tasks, **fourteen real defects were found, and every one of them was in code that had been written into the plan.** Four would have caused silent corruption or an unbuildable artifact:

- a fold predicate testing `=` against a whole line including its comment, which would have folded a host-supplied uniform into an uncompilable `const`
- a member regex unscoped to its struct, so local declarations elsewhere in the file became struct members and literals mapped to the wrong fields
- a literal scanner matching the `3` inside `vec3(`, shifting every field one slot
- an `apply` comparing GL float32 read-back against file literals with exact equality, so "apply all changed" would rewrite every value with float32 noise while reporting success

An implementer transcribes plan code faithfully, because it arrived as requirements. The facts probed before writing that plan — API shapes, byte-identity, actual enumeration output — held perfectly. Only the code that was reasoned out was wrong.

- **Probe first, and put the measurements in the plan.** Return shapes, real enumerated names, whether the thing compiles at all — what an implementer cannot cheaply re-derive and most needs. An "Already measured — do not re-derive" table earned its keep every task.
- **Prefer specifying the contract to specifying the body.** Exact names, signatures, types, and the failure the code must prevent. A wrong signature is caught in seconds; a wrong body ships.
- **If you do include code, label it a proposal, not requirements**, and say so in every dispatch: *"be sceptical, report defects rather than fixing silently."* That one clause is what surfaced most of the fourteen.
- **Write tests that check the value, not the shape.** Every check written for the slot parser asserted which *line* a slot pointed at, none its decoded *value*. A parser can point at exactly the right line and return the wrong number.
- **Never build a numeric test from exact binary fractions.** A float32 round-trip check written with 0.5, 0.25 and 0.75 passes before and after the fix. Use 0.74.
- **Keep this clause in every fix dispatch:** *"if you conclude one of these findings is wrong, say so with evidence rather than implementing something you believe is incorrect."*

### "Real code, not placeholders" does not mean code as requirements

`superpowers:writing-plans` fires at the same moment and looks opposed. It forbids **placeholders** — `// TODO: implement the parser here` defers every real decision. This skill forbids **passing untested code off as requirements**. One plan satisfies both.

What a plan task can carry, best to worst:

1. **A contract** — exact names, signatures, types, and the failure the code must prevent. A wrong signature is caught in seconds.
2. **A measurement** — return shapes, real enumerated output, whether the thing compiles. What the implementer cannot cheaply re-derive.
3. **Code labelled a proposal**, with *"be sceptical, report defects rather than fixing silently"* in the dispatch.
4. **Code presented as requirements.** This is what produced the fourteen defects above.
5. **A placeholder.** Worse than all of these, and what `superpowers:writing-plans` warns you off.

So "real code, not placeholders" means do not write 1 and 2 as stubs. It does not mean write 4.

## Rule 2 — Check what an agent is ALLOWED to write before you scope work to it

An agent-seat plugin repo, issue 196, 2026-09-02. Two full dispatches to the autonomous agent seat burned, both stuck, both for the same reason: four of the seven files the issue required live under `constructs/quest/`, which is hard read-only for that seat in every mode. Refusals there are **format-budget** failures, so each run spent its entire budget refusing itself and escalated having written only the files it was allowed to touch.

The tell was in the seat's own README, read at the start of the session: "never edits its own ruler — `constructs/quest/` and `.github/CODEOWNERS` are read-only in every mode." It was read, never connected to the file list, and then **made worse** — a spec revision added a third prompt file and a `plugin.json` version bump, taking the blocked set from two files to four.

Before labelling anything for an autonomous seat:

- **Diff the issue's file list against the agent's deny-list**, mechanically. Find the deny-list in the source (`_GOVERNANCE_NAMESPACES`, protected-path constants, the App's GitHub permissions), not in your memory of the docs.
- **Watch for a deny-listed file dragged in by a lockstep constraint.** Here a test pinned `plugin.json` + `<PROJECT>_VERSION` + `package.json` together, and only the first was blocked — so *any issue that ships a release* was a human issue, which nothing in the issue text suggested.
- **A capability the agent lacks is not fixable by writing a better spec.** A revision was spent resolving genuine spec defects, and then re-dispatched into a wall that no spec could move. Ask "can it physically do this" before "have I explained this well enough".
- **Split the issue at the boundary** rather than relaxing the guard. The guard was correct: a builder that can edit its own reviewer can weaken its own gate.
- **An escalation that says "retry cap exhausted" describes the budget, not the cause.** Read what it was actually failing at before re-dispatching. The first report's failure text was test output; the second's was the refusal message in full, and that is where the answer was.
