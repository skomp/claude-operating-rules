# machines

Declare a communication protocol as a state machine, next to the prose that explains it,
and check it before you trust it.

## What this ships, and what it does not

**Cycle A ships the schema and the checker only.** There is no engine — nothing here runs
a machine, advances a state, or emits a message. There is no installer — nothing wires a
declared machine into anything that dispatches real traffic. There is no dispatcher —
nothing routes an inbound message to the machine that owns it. What exists is a closed
declaration language, a parser for it, a set of checks that a single machine is
well-formed and terminates, and a checker that runs those checks over every machine handed
to it and reports whether any two claim the same message. That is the whole of cycle A.
Anything that talks about a machine actually running is a later cycle.

## The declaration

A machine is a single ` ```machine ` fenced YAML block inside a bundle's `SKILL.md` — nine
required fields: `machine`, `version`, `prefix`, `roles`, `kinds`, `cap`, `initial`,
`states`, `transitions`. Any other top-level field is rejected by name, not silently
ignored. `SCHEMA.md` documents every field and why it exists, including the two hazards
worth knowing before you write a declaration by hand.

**`prefix` is a pattern, not literal text.** It is read as an expression in a small regular
language, so a prefix containing `( ) [ ] . * + ? | \ { }` does not claim the characters you
typed — `proto(v1) ` claims `protov1 `, and `[proto] ` claims `p `, `r `, `o ` and `t ` —
while the checker still exits `0`. Escape those characters with `\` (`proto\(v1\) `) or keep
the prefix to letters, digits, spaces, `:` and `-`. `SCHEMA.md` carries the whole grammar.

**`yes` and `no` are not booleans here.** PyYAML's default loader treats the bare words
`yes`, `no`, `on` and `off` as booleans anywhere a string can appear, including a mapping key
(`on: yes` is exactly the kind of word this catches) — this parser narrows that resolution to
`true`/`false` only, so a state or role named `no` stays the string you wrote.

## The checker

`bin/machines-check <path>...` — each path is a declaration file directly, or a directory
to search for a `SKILL.md`. It parses every machine it finds, checks each one for
well-formedness, and checks every pair of distinctly-named machines for a prefix collision
— two protocols that could both claim the same message.

What "well-formed" covers: every referenced state, role and kind is actually declared; at
least one state is terminal; no state is stranded past a terminal one; nothing is
unreachable from `initial`; no two transitions share a trigger and disagree about where it
leads; a state's declared `holder` is the role that actually acts on the way out of it; the
declared `cap` is large enough for the shortest run that can reach a terminal state; and no
declared kind sits there with no transition firing on it.

```
plugins/machines/bin/machines-check plugins/machines/tests/fixtures/valid-session-relay.md
Examined 1 machine
```

**Three exit codes, not two:**

| Exit | Means |
|---|---|
| `0` | Every machine examined is well-formed and none collide |
| `1` | The tool ran and found a problem — a bad declaration, or a collision |
| `2` | The tool could not run at all — no paths given, a path that doesn't exist, PyYAML missing, or a broken interpreter |

A tool that cannot run must never exit `1`: that code reads as "I checked, and found a
problem," and a broken install is not a finding. `bin/machines-check` checks for `python3`
and for PyYAML before it ever tries to parse anything, and if that probe itself fails for a
reason that has nothing to do with PyYAML — a pyenv shim pointed at an interpreter that
isn't installed, say — it lets that interpreter's own error reach stderr rather than
reporting a misleading "install PyYAML" for a problem that isn't about PyYAML at all.

**The output always states how many machines were examined, including zero — and only
claims "No collisions found" when it examined a pair.** "No collisions found" after looking
at nothing is the failure `evidence-discipline` documents under a different name: a check
that passed because it checked nothing. Every run of `machines-check` that gets past the
exit-2 checks prints `Examined N machine(s)` before anything else, whether `N` is eleven or
zero; the collision verdict appears only when `N` is at least two, because a collision takes
two machines and one machine is no pair. That is why the example above, on a single file,
prints the count and stops.

## Dependency

PyYAML. Not standard library, so `bin/machines-check` checks for it and fails with the
install command (`python3 -m pip install PyYAML`) rather than a traceback if it's missing.
Everything under `lib/` besides the YAML dependency is standard library, Python 3.8+.

## Running the tests

```
cd plugins/machines && PYTHONPATH=lib:. python3 -m unittest discover -s tests -t .
```

pytest is not assumed to be installed; the suite is plain `unittest`.

## Install it if

You are declaring a communication protocol between two agents, sessions, or services as an
explicit state machine and want it checked before you rely on it. There is no skill here to
trigger — cycle A is a library and a command-line checker, nothing that fires on its own.

Skip it if you want something that actually runs a protocol at conversation time; that is
not built yet.
