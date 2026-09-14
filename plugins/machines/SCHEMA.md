# The machine declaration

A machine is a single ` ```machine ` fenced block inside a bundle's `SKILL.md`, next to the
prose that explains it. `machines.declaration.parse(text)` turns that block into a `Machine`.
It is a closed language — no expressions, no scripts, no callbacks — so every field below is
one of the nine the parser accepts. **Any other top-level field is rejected by name**, not
silently ignored: a publisher who writes `caps: 10` is told about `caps`, not handed a machine
with a default cap they never asked for.

Every field in this document is required unless its section says otherwise. A required
field that is missing is rejected by name, the same as an unknown one.

**Every type in this document is enforced, and every failure names the field.** A field
documented as a string must be a string; `roles` must be a mapping; each `states` and
`transitions` entry must be a mapping with its required sub-fields present; `kinds` and
`effects` must be lists of strings. A declaration that gets one of those wrong is told
which field, by name, before anything else looks at it. Nothing a publisher can write in a
machine block reaches you as a Python traceback — a crash reported as a finding would be a
checker telling you your machine is broken when it is the checker that broke.

## Scalars mean what you wrote, not what YAML 1.1 guesses

PyYAML's default loader follows YAML 1.1, under which the bare words `yes`, `no`, `on`,
`off` (and case variants) resolve to booleans — in *any* scalar position, including a
mapping key. Left alone, that is a hole through every string-valued field in this schema: a
kind declared `on`, a state named `no`, a role called `yes`, a transition's `on: yes` would
each silently become a Python `True`/`False` instead of the string the publisher wrote, and
every check built on equality or a dict key (`t.on in m.kinds`, `m.states["no"]`) would keep
working against the corrupted value with no error raised anywhere. That is worse than a
crash: coherent-looking data that is simply wrong.

**This parser narrows boolean resolution to `true`/`false` (and case variants) only,
everywhere in the declaration.** `yes`, `no`, `on` and `off` are always strings here,
whatever position they appear in. **The cost:** `signal: yes` no longer means `signal: true`
— a publisher who wants the boolean must write `true` or `false` literally. The parser
enforces this too: `signal` and `terminal` reject anything that isn't an actual boolean
(so `signal: yes` fails loudly as the string `"yes"` in a boolean field, rather than being
accepted as truthy).

That single rule is what lets every other section below say "string" or "boolean" and mean
exactly one thing.

## `machine`

**Type:** string. **Required.**

The machine's name. Prevents a bundle from shipping a protocol nobody can refer to when two
machines are compared or reported on.

## `version`

**Type:** string. **Required.**

The machine's version. Two machines with the same `machine` name but different `version`
strings are different protocols as far as the checker is concerned — this field is what lets
a publisher change a protocol without silently mutating one that peers already installed.

## `prefix`

**Type:** string. **Required.** **Read as a pattern, not as literal text — see the next
section before you write one.**

What every message this machine emits begins with. It is what the dispatcher matches to
route an inbound message to this machine (a later cycle), and what the installer compares
between machines to detect a collision: two machines claiming the same prefix can never
both be enabled. An empty or missing prefix would make that comparison meaningless, so the
field exists to prevent messages from being unroutable and installs from colliding
silently.

## The prefix is a pattern, not a literal

**`prefix` is parsed as an expression in a small pattern language.** A prefix made only of
ordinary letters, digits, spaces, `:` and `-` means exactly what it says — `session-relay:v1 `
claims the messages that begin with `session-relay:v1 ` and nothing else. But a prefix
containing any of

```
| * + ? ( ) [ ] . \ { }
```

means something other than those characters, and the machine you get is not the machine
you wrote. Measured on this implementation:

| You write | It actually claims |
|---|---|
| `proto(v1) ` | `protov1 ` — the parentheses are grouping, not characters |
| `session-relay:v1. ` | `session-relay:v1X ` for any `X` — `.` is "any character" |
| `[proto] ` | `p `, `r `, `o ` or `t ` — `[...]` is a character class, one character long |

Nothing reports this. Each of those compiles cleanly, `machines-check` exits `0`, and the
machine quietly fails to claim its own messages while claiming other people's.

**To match one of those characters literally, put a `\` in front of it:** `proto\(v1\) `
claims `proto(v1) `, and `session-relay:v1\. ` claims `session-relay:v1. `. A `\` before
any other character is rejected by name rather than guessed at, so there are no silent
half-escapes.

### The whole grammar

```
pattern := alt
alt     := cat ('|' cat)*          alternation
cat     := rep*                    concatenation
rep     := atom ('*' | '+' | '?')? zero-or-more, one-or-more, optional
atom    := literal | '.' | class | '(' alt ')'
class   := '[' '^'? item+ ']'      a character class, negated with '^'
item    := char '-' char | char    a range, or one character
literal := any character except | * + ? ( ) [ ] . \  -- or '\' followed by one of those
```

That is all of it. **No backreferences, no lookaround, no anchors, no `{n,m}` counted
repetition, no named groups, no `\d`/`\w`/`\s` shorthand classes.** Every one of those is
rejected by name at parse time. The restriction is not taste: the installer decides
"can these two machines claim the same message" by intersecting two automata, which is only
decidable because every prefix here is a *regular* expression. A backreference is not
regular, so one accepted here would sail through every other check and silently take the
framework's central guarantee with it.

Two further limits, both reported as errors:

- **A pattern that can match the empty string is rejected.** `a*`, `a?`, `(a|)` and the
  empty prefix all match nothing-at-all, and a prefix that matches the empty string claims
  *every* message — a machine that collides with every other installed machine, forever,
  with no single obviously-wrong machine to point at. Rejecting it at the one machine that
  caused it is the only place that failure is legible.
- **A pattern that compiles to more than 10,000 automaton states is rejected.** Nested
  repetition doubles the state count per level, so a 52-character pattern can reach half a
  million states. No message prefix needs that, and being told the limit is better than
  watching the checker allocate until it dies.

## `roles`

**Type:** mapping of string to string (role name to what it binds to). **Required.**

The set of participants who can hold a state or act in a transition. Every `holder` on a
state and every `by` on a transition (below) is checked, by `check_machine`, against the names
declared here. Without this field, a publisher could write `by: bystander` in a transition
and never learn that no such role exists until it is too late to matter. A role named `yes`
or `no` lands as that literal string, both as the key here and wherever it is referenced —
see "Scalars mean what you wrote" above.

## `kinds`

**Type:** list of strings. **Required.**

The closed vocabulary of message kinds this machine recognises. Every transition's `on`
(below) is checked, by `check_machine`, against this list. This is what keeps the language closed:
a transition cannot fire on a kind nobody declared, and a reader can find every kind the
protocol understands by reading one list instead of hunting through every transition.
**A kind no transition fires on is reported**: the declaration says the machine understands
that message and no state does anything with it, which is vocabulary that reads as
supported and is not. **Must actually be a list** — `kinds: "yes"` is rejected by name rather than silently
iterated character-by-character into `{'y', 'e', 's'}`, which is what `set("yes")` would
otherwise do with no error at all.

## `cap`

**Type:** integer, and it must be a *positive* integer — `0`, a negative number, and a
non-integer (including a quoted string) are all rejected. **Required.**

The transition cap: the maximum number of outbound messages this machine's engine will ever
emit for one run. It caps transitions, not comments — a bundle's "ten comments per sender"
rule is that bundle's choice of value, not the framework's. This is the field that makes
termination checkable at all: a machine that can run forever is exactly a machine with no
enforced cap and no path to a terminal state, so `cap` has to exist, has to be a real count,
and cannot be disguised as `true` (which is why the parser rejects a boolean here even though
Python considers `True` an `int`).

**The cap is compared to the machine, not just validated on its own.** `check_machine`
measures the shortest run from `initial` to a terminal state and reports a cap smaller than
that: a machine declared both to terminate and to exhaust its budget before it can is a
machine that cannot legally finish. A cap that is merely generous is not reported — only
one no run can satisfy.

## `initial`

**Type:** string. **Required.**

The name of the state a run starts in. `check_machine` checks that this names a state actually
declared under `states` below — a publisher who mistypes it would otherwise get a machine
that can never legally start.

## `states`

**Type:** list of state objects. **Required.** At least one entry. Must actually be a list
— `states: not-a-list` is rejected by name rather than raising a bare `TypeError` when the
parser tries to iterate it.

Each entry is a state, with these fields:

- **`name`** (string, required) — the state's identifier. Every other reference to a state
  (`initial`, a transition's `from`/`to`) is checked against these names. **Two states
  sharing a name is rejected at parse time** — without that check, the second `states` entry
  would silently replace the first in the `states` dict, and half the declared transitions
  would land on a state that was never declared as its author intended. A name that happens
  to be a YAML boolean-token word (`no`, `yes`, `on`, `off`) still lands as that literal
  string — see "Scalars mean what you wrote" above.
- **`holder`** (string, optional, default: none) — which declared role acts while the machine
  is in this state. Checked against `roles` above, and against the `by` of every transition
  out of this state: `holder` and `by` both say who acts next, so a state held by one role
  whose only exits are taken by another is reported.
- **`terminal`** (boolean, optional, default: `false`) — whether a run may legitimately end
  here. `check_machine` checks that a terminal state has no outgoing transition (a run cannot end and
  continue in the same breath) and that at least one state is terminal at all (a machine with
  no exit is a machine that never legitimately ends). If present, must be an actual boolean —
  `terminal: yes` is rejected rather than accepted as the string `"yes"` coerced to `True` by
  Python truthiness.

Any field on a state entry other than `name`, `holder` and `terminal` is rejected by name.

## `transitions`

**Type:** list of transition objects. **Required.** May be empty, though a machine with no
transitions can never leave its initial state. Must actually be a list — `transitions:
not-a-list` is rejected by name, the same as a malformed `states`.

Each entry is a transition, with these fields:

- **`from`** (string, required) — the state this transition fires out of. The declared
  attribute is `frm`, not `from`: `from` is a Python keyword, so the YAML field name and the
  attribute name differ on purpose. Checked against `states`.
- **`on`** (string, required) — the message kind that fires this transition. Checked at
  against `kinds`. **The field name most exposed to the YAML boolean hazard above** —
  written as a bare mapping key, `on:` is exactly the word PyYAML's default resolver turns
  into the boolean `True`. Narrowing boolean resolution (see above) is what keeps `on:
  question` — and `on: yes`, should a protocol need that kind name — as the string the
  publisher wrote.
- **`by`** (string, required) — the role that must hold the state for this transition to
  fire. Checked against `roles`.
- **`to`** (string, required) — the state this transition lands in. Checked against
  `states`. Two transitions sharing `from`, `on` and `by` but naming different `to` states
  are reported: the engine is a fold over the message trace, and a fold has exactly one
  result per step, so a machine with that choice in it cannot be run at all.
- **`signal`** (boolean, optional, default: `false`) — whether firing this transition emits a
  signal to a peer, as opposed to a purely local move. If present, must be an actual boolean;
  see "Scalars mean what you wrote" above — `signal: yes` is rejected, not silently accepted
  as true.
- **`effects`** (list of strings, optional, default: empty list) — side effects to apply when
  this transition fires. `check_machine` restricts every entry to the fixed vocabulary
  `label.add:<name>`, `label.remove:<name>` and `escalate` — nothing else. This is what
  keeps the declaration inert data rather than a program: an unvalidated effect such as
  `run:curl ...` would be an instruction, and an engine that later grew to honour it would be
  executing a stranger's command.

Any field on a transition entry other than `from`, `on`, `by`, `to`, `signal` and `effects`
is rejected by name.
