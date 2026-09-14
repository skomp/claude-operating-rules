# The machine declaration

A machine is a single ` ```machine ` fenced block inside a bundle's `SKILL.md`, next to the
prose that explains it. `machines.declaration.parse(text)` turns that block into a `Machine`.
It is a closed language — no expressions, no scripts, no callbacks — so every field below is
one of the ten the parser accepts. **Any other top-level field is rejected by name**, not
silently ignored: a publisher who writes `caps: 10` is told about `caps`, not handed a machine
with a default cap they never asked for.

Every field in this document is required unless its section says otherwise. A required
field that is missing is rejected by name, the same as an unknown one.

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

**Type:** string. **Required.**

The literal text every message this machine emits begins with. It is what the dispatcher
matches to route an inbound message to this machine (a later task), and what the installer
compares between machines to detect a collision: two machines claiming the same prefix can
never both be enabled. An empty or missing prefix would make that comparison meaningless, so
the field exists to prevent messages from being unroutable and installs from colliding
silently.

## `roles`

**Type:** mapping of string to string (role name to what it binds to). **Required.**

The set of participants who can hold a state or act in a transition. Every `holder` on a
state and every `by` on a transition (below) is checked, at Task 3, against the names
declared here. Without this field, a publisher could write `by: bystander` in a transition
and never learn that no such role exists until it is too late to matter.

## `kinds`

**Type:** list of strings. **Required.**

The closed vocabulary of message kinds this machine recognises. Every transition's `on`
(below) is checked, at Task 3, against this list. This is what keeps the language closed:
a transition cannot fire on a kind nobody declared, and a reader can find every kind the
protocol understands by reading one list instead of hunting through every transition.

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

## `initial`

**Type:** string. **Required.**

The name of the state a run starts in. Task 3 checks that this names a state actually
declared under `states` below — a publisher who mistypes it would otherwise get a machine
that can never legally start.

## `states`

**Type:** list of state objects. **Required.** At least one entry.

Each entry is a state, with these fields:

- **`name`** (string, required) — the state's identifier. Every other reference to a state
  (`initial`, a transition's `from`/`to`) is checked against these names. **Two states
  sharing a name is rejected at parse time** — without that check, the second `states` entry
  would silently replace the first in the `states` dict, and half the declared transitions
  would land on a state that was never declared as its author intended.
- **`holder`** (string, optional, default: none) — which declared role acts while the machine
  is in this state. Checked at Task 3 against `roles` above.
- **`terminal`** (boolean, optional, default: `false`) — whether a run may legitimately end
  here. Task 3 checks that a terminal state has no outgoing transition (a run cannot end and
  continue in the same breath) and that at least one state is terminal at all (a machine with
  no exit is a machine that never legitimately ends).

Any field on a state entry other than `name`, `holder` and `terminal` is rejected by name.

## `transitions`

**Type:** list of transition objects. **Required.** May be empty, though a machine with no
transitions can never leave its initial state.

Each entry is a transition, with these fields:

- **`from`** (string, required) — the state this transition fires out of. The declared
  attribute is `frm`, not `from`: `from` is a Python keyword, so the YAML field name and the
  attribute name differ on purpose. Checked at Task 3 against `states`.
- **`on`** (string, required) — the message kind that fires this transition. Checked at
  Task 3 against `kinds`. **Written in YAML flow-mapping style, the bare word `on` parses as
  the boolean `True`** under PyYAML's default resolver (the same rule that turns `no` into
  `False`), so `declaration.py` recovers the intended field name before validating it — a
  publisher writing `on: question` gets the field they wrote, not a parse error explainable
  only by reading PyYAML's source.
- **`by`** (string, required) — the role that must hold the state for this transition to
  fire. Checked at Task 3 against `roles`.
- **`to`** (string, required) — the state this transition lands in. Checked at Task 3 against
  `states`.
- **`signal`** (boolean, optional, default: `false`) — whether firing this transition emits a
  signal to a peer, as opposed to a purely local move.
- **`effects`** (list of strings, optional, default: empty list) — side effects to apply when
  this transition fires. Task 3 restricts every entry to the fixed vocabulary
  `label.add:<name>`, `label.remove:<name>` and `escalate` — nothing else. This is what
  keeps the declaration inert data rather than a program: an unvalidated effect such as
  `run:curl ...` would be an instruction, and an engine that later grew to honour it would be
  executing a stranger's command.

Any field on a transition entry other than `from`, `on`, `by`, `to`, `signal` and `effects`
is rejected by name.
