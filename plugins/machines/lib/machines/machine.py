import re
from collections import deque

from .pattern import PatternError, compile_pattern

# Every top-level field the parser accepts, and the subset of them a
# declaration must actually carry. `cap` is the one that is accepted and
# not required: a protocol that has no reason to terminate has no bound to
# declare, and forcing one would make its author write a number nobody
# believes -- which is the failure this framework exists to answer, not one
# it should cause. Absent means "this protocol declares no bound"; it does
# not mean zero, and there is no default.
#
# `fields` and `registers` are optional the same way: a protocol with
# nothing to guard on declares neither, and gets an empty mapping rather
# than a required field it never wanted.
FIELDS = ("machine", "version", "prefix", "roles", "kinds", "fields",
          "registers", "cap", "initial", "states", "transitions")
REQUIRED = tuple(f for f in FIELDS if f not in ("cap", "fields", "registers"))

_INFINITY = float("inf")

# A declared header field's name, reused unchanged for register names:
# both live in the same namespace a publisher writes into, and both must
# stay out of the dotted `envelope.*` namespace a later cycle reserves for
# the message envelope itself (the Lamport clock among it) -- forbidding
# `.` here is what keeps a declared field from ever colliding with it.
NAME = re.compile(r"^[a-z][a-z0-9_-]*$")

# The closed set of types a declared field may carry. Closed on purpose:
# an open type word (`integer`, `number`, ...) would let a publisher write
# something the engine's guard comparison (cycle B) cannot evaluate, and
# the failure would surface far from the declaration that caused it.
# Deliberately no `string` -- a guard compares a register's fold to a
# field by equality or order (cycle B), and every comparison this schema
# can express is arithmetic or boolean; there is no string fold or string
# ordering defined anywhere in the spec for one to compare against.
FIELD_TYPES = ("int", "bool")


class Field(object):
    """A declared header field: a name and its type, nothing else.

    `type` is one of `FIELD_TYPES`. There is no default and no value here
    -- a `Field` describes what a header position must contain, not what
    any one message carries in it.
    """

    def __init__(self, name, type):
        self.name = name
        self.type = type


# The closed set of ways a register may fold a field's value across a
# trace. Closed for the same reason `FIELD_TYPES` is: an open fold word
# would let a publisher declare a register that cycle B's engine (the
# fold itself is cycle B's job; this schema only declares its shape)
# cannot evaluate, and the failure would surface far from the declaration
# that caused it. See the comment on the R1-R4 checks in `check_machine`
# for the fold/argmax boundary this set is drawn at, and SCHEMA.md's
# `registers` section for why `min`, `first`, `count` and `sum` are not
# here either.
FOLDS = ("max", "last")


class Register(object):
    """A declared register: one remembered scalar, folded from the trace.

    `fold` is one of `FOLDS`. `field` names the declared header field
    (see `Field`, above) whose value is read on every matching message.
    `on` is the non-empty list of kinds that feed the register -- a
    message of any other declared kind leaves it untouched. `initial` is
    the value the register holds before any matching message has arrived,
    an `int` or a `bool`, and (once a machine has passed `check_machine`)
    the same Python type as the field it folds.

    This class only declares the fold; it does not perform one. Nothing
    in cycle A reads a channel, folds a trace, or evaluates a guard --
    that is cycle B's engine. A `Register` is what a guard (cycle B) will
    compare a field against once one exists.
    """

    def __init__(self, name, fold, field, on, initial):
        self.name = name
        self.fold = fold
        self.field = field
        self.on = on
        self.initial = initial


# A guard's operator vocabulary, spelled as words rather than symbols --
# see declaration.py's `_guard_field` for the measurement that makes a
# symbol form actively unsafe, not merely a style choice.
#
# `LT`, `EQ`, `GT` are the three possible outcomes of comparing two values
# of a totally ordered type -- there are no others. Every operator below
# is the union of the outcomes that make it true: `eq` accepts only `EQ`,
# `ne` accepts everything that is not `EQ`, and the four ordering
# operators each accept one or two of the three. This table is what makes
# a guard's truth decidable from which atom a comparison produced,
# without a check ever interpreting the compared values themselves --
# it only has to know which of `LT`/`EQ`/`GT` two values produced, once,
# and this table answers every operator from that one fact.
OP_ATOMS = {
    "eq": frozenset(["EQ"]),
    "ne": frozenset(["LT", "GT"]),
    "lt": frozenset(["LT"]),
    "le": frozenset(["LT", "EQ"]),
    "gt": frozenset(["GT"]),
    "ge": frozenset(["EQ", "GT"]),
}

# The operators that require an ordering, not merely an equality test.
# `eq`/`ne` are meaningful on any totally ordered type, `bool` included
# (there are only two values, so equal-or-not is all there is to ask);
# the four here ask "which is bigger", which a `bool` field has no
# declared meaning for. See G3 in `check_machine`.
ORDERING_OPS = ("lt", "le", "gt", "ge")


class Guard(object):
    """A transition's guard: one declared field compared to one declared
    register's remembered value, by one operator.

    `field` names a declared header field (see `Field`, above); `register`
    names a declared `Register`; `op` is one of `OP_ATOMS`'s six keys.

    This class only declares the comparison. Nothing in cycle A evaluates
    one -- comparing a guard against an arriving message and a register's
    current value, and deciding whether the transition fires, is cycle
    B's engine, the same boundary `Register`'s docstring draws for a fold.
    """

    def __init__(self, field, op, register):
        self.field = field
        self.op = op
        self.register = register


class State(object):
    """A state, with two independent properties that are easy to conflate.

    `accepting` -- nothing further is *required*. It is fine for the
    conversation to stop here, with nothing owed to anybody.

    `terminal` -- nothing further is *possible*. No transition leaves.

    All four combinations are meaningful. A conclusion is both. A responder
    sitting idle, willing to answer another question but owing nobody
    anything, is accepting and not terminal. A session that has just sent a
    message and is waiting for the reply is neither. And an abort -- a
    protocol violation, a peer that went away -- is terminal and *not*
    accepting: the conversation ended while something was still owed, and
    saying so is the whole point of the state.

    `accepting` defaults to False, which is the conservative direction: an
    author who declares nothing accepting gets a machine the checker
    rejects by name, rather than one where stopping anywhere is silently
    fine.
    """

    def __init__(self, name, holder=None, terminal=False, accepting=False):
        self.name = name
        self.holder = holder
        self.terminal = terminal
        self.accepting = accepting


class Transition(object):
    def __init__(self, frm, on, by, to, signal=False, effects=None, guard=None):
        self.frm = frm
        self.on = on
        self.by = by
        self.to = to
        self.signal = signal
        self.effects = list(effects or [])
        # `Guard` or `None`. `None` means this transition fires
        # unconditionally -- there is no empty `Guard` standing in for
        # "no guard", the same reasoning `Register`'s absence-is-`None`
        # comment gives for `fields`/`registers` on `Machine`.
        self.guard = guard


class Machine(object):
    def __init__(self, name, version, prefix, roles, kinds, cap,
                 initial, states, transitions, fields=None, registers=None):
        self.name = name
        self.version = version
        self.prefix = prefix
        self.roles = roles
        self.kinds = kinds
        self.cap = cap
        self.initial = initial
        self.states = states
        self.transitions = transitions
        # Dict[str, Field], keyed by field name. Defaults to `{}`, not
        # `None`: a machine with no declared fields still has something
        # iterable and indexable, the same reasoning `Transition.effects`
        # already applies to `effects=None`.
        self.fields = fields if fields is not None else {}
        # Dict[str, Register], keyed by register name. Defaults to `{}`
        # for the same reason `fields` does.
        self.registers = registers if registers is not None else {}


# `prefix` is not just a string -- it is source text pattern.py compiles to
# an NFA. `_parse_cat` (the recursive-descent parser's grammar production
# for concatenation) is an iterative loop, not per-character recursion, so
# parsing itself survives a long bare literal; but it builds a left-deep
# `Cat(Cat(Cat(...), Lit), Lit)` tree, one level per character, and the
# Thompson NFA compiler's `_compile_cat` walks that tree by recursing into
# `node.left` -- so a long enough literal exhausts Python's call stack
# during *compilation*, with no `(`, `|`, or repetition operator anywhere
# in it, and nothing about the parse stage itself at fault.
#
# Measured: a 498-character literal prefix compiles; 499 raises
# `RecursionError` out of `compile_pattern`, reached via `check_machine`
# (see `prefix_problem` below) or via `declaration.parse` (see
# declaration.py's `_require_prefix_length`, which enforces this same
# limit at parse time, before a `Machine` even exists), past every shape
# guard above, as an uncaught traceback -- exit 1 from `machines-check`
# for a crash, not a finding.
#
# 400 is the limit for *this* route: two orders of magnitude above
# `session-relay:v1 ` (17 characters) or any other plausible protocol
# prefix, comfortably under the 498 where a bare literal's recursion
# fails, checked both here and in declaration.py's `_require_prefix_length`
# before the pattern parser ever sees the text, so a publisher -- or, for
# a hand-built `Machine` that skipped the parser, a caller of
# `check_machine` -- gets a named field and a stated limit instead of a
# stack trace for that shape of input.
#
# CORRECTION: an earlier version of this comment called 498 "the exact
# failure this module's shape guards otherwise exist to prevent" -- true
# only for a bare literal. A prefix built from nested `(...)` groups
# recurses in the *parser*, not just the compiler, and hits it far
# shallower: `'(' * 199 + 'a' + ')' * 199` is 399 characters -- under this
# 400-character guard -- and still raised an uncaught `RecursionError`
# through the shipped CLI. This length guard bounds the concatenation-
# chain route (a long flat Cat/Alt tree, whatever it's built from --
# literals, `|` branches, or short reps) and nothing else; it was never a
# bound on nesting depth. Nesting depth has its own guard now
# (`_MAX_GROUP_DEPTH` in pattern.py, checked in `_parse_group`), and
# whatever either guard misses is caught as a last resort by
# `prefix_problem`'s `RecursionError` handler, rather than propagating as
# a traceback.
#
# This constant used to live only in declaration.py, and so did the check
# against it: a `Machine` built by `declaration.parse` could never carry
# an over-length prefix, because `_require_prefix_length` raises before
# one is constructed. But `prefix_problem` exists precisely so a
# hand-built `Machine` -- one that skipped the parser and its shape
# guards entirely, the same case the module docstring on `check_all`
# already names for `TypeError` -- gets the same answer `check_machine`
# gives everyone else. Defined here, once, and imported into
# declaration.py, so the two enforcement points share one number rather
# than risking two.
_MAX_PREFIX_LENGTH = 400


def prefix_problem(prefix):
    """Check a prefix pattern for whether a `Machine` can actually use it:
    whether it is short enough, and whether it will compile.

    Returns None when `prefix` is fine; otherwise a human-readable problem
    string naming the field, `"prefix pattern %r: ..."`. This is a
    property of one machine's own declaration, not of a set of them, and
    used to be checked only in `registry.py`'s `check_all` (compilation)
    and `declaration.py`'s `_require_prefix_length` (length, at parse
    time, before a `Machine` exists) -- which meant a caller that used
    `check_machine` directly on a hand-built `Machine` (the documented
    answer to "is this machine well-formed", and exactly what cycle B's
    engine does) got no prefix validation at all. It is called from
    `check_machine` below for exactly that reason, and from `check_all` to
    decide whether a machine is fit to compare against others for a
    collision -- a pattern that will not compile cannot be intersected
    with anything.

    The length check first: over `_MAX_PREFIX_LENGTH` characters is
    rejected by name before `compile_pattern` is even called, the same as
    declaration.py's `_require_prefix_length` does at parse time -- see
    that constant, above, for the measurement and reasoning. A `Machine`
    built by `declaration.parse` can never reach here with an over-length
    prefix (that function already raised), so this cannot double-report
    against a parsed machine; it only ever fires for a hand-built one.

    Then `compile_pattern` itself, which catches `PatternError` -- from an
    unparseable prefix, or one that is nullable (matches the empty string,
    and would therefore claim every message; see pattern.py's
    `compile_pattern`) -- and nothing else, except one backstop.

    A prefix nested deep enough in `(...)` groups is named by `PatternError`
    too -- pattern.py's parser tracks nesting depth and rejects past 100
    levels, well short of where it would recurse into a raw
    `RecursionError`. That guard is the ordinary case; `RecursionError`
    itself is also caught here, alongside `PatternError`, as a backstop --
    converted to the same kind of named problem -- for whatever AST shape
    (if any) reaches a deep stack some other way, in either the parser or
    the compiler. See pattern.py's `_MAX_GROUP_DEPTH` for the measurement
    and reasoning; the handler below stays trivial on purpose (no
    formatting that calls back into pattern code, no further recursion),
    since `RecursionError` fires with the stack nearly exhausted. This
    backstop is what keeps SCHEMA.md's promise that nothing a publisher
    writes reaches them as a Python traceback true of a bad prefix
    specifically, and it must move with the compile call rather than stay
    behind in `registry.py` -- a raw 399-character nested prefix reached an
    uncaught traceback through the shipped CLI before this guard existed.
    """
    if len(prefix) > _MAX_PREFIX_LENGTH:
        return ("prefix pattern %r: prefix is %d characters long; the "
                "limit is %d characters"
                % (prefix, len(prefix), _MAX_PREFIX_LENGTH))
    try:
        compile_pattern(prefix)
    except PatternError as exc:
        # Name the field. Every other `check_machine` message says which
        # field it is about; without the prefix here, a publisher reads
        # `unclosed group starting at position 0` and has to guess which
        # of eleven fields is a pattern at all.
        return "prefix pattern %r: %s" % (prefix, exc)
    except RecursionError:
        return "prefix pattern %r: too deeply nested to analyse" % (prefix,)
    return None


def check_machine(m):
    """Check a machine for well-formedness.

    Returns a list of human-readable problems. An empty list means the
    machine is well-formed. This returns problems rather than raising,
    because a publisher wants every problem at once, not the first one.

    **This no longer checks that the machine terminates, and that is
    deliberate.** An earlier version required `cap`, required at least one
    terminal state, and required every state to reach one -- which writes
    "a protocol terminates" into the framework as a law. It is not one. It
    is a property of some protocols, and requiring it of all of them forces
    an author with a continuous protocol to declare a bound they do not
    mean. A declared bound nobody believes is the exact failure this
    framework exists to answer.

    What is checked instead is that nobody is ever owed something forever
    with no exit: at least one state must be somewhere nothing is owed, and
    every state where something *is* owed must be able to reach somewhere a
    run may legitimately stop -- an accepting state, or a terminal one.
    Stopping badly is still an exit, and a protocol that stops badly on
    purpose, with effects that tell the peers, is doing its job.
    """
    problems = []

    bad_prefix = prefix_problem(m.prefix)
    if bad_prefix is not None:
        problems.append(bad_prefix)

    names = set(m.states)

    initial_declared = m.initial in names
    if not initial_declared:
        problems.append("initial state %r is not declared" % m.initial)

    for t in m.transitions:
        for label, value in (("from", t.frm), ("to", t.to)):
            if value not in names:
                problems.append("transition %s names undeclared state %r"
                                % (label, value))
        if t.on not in m.kinds:
            problems.append("transition on names undeclared kind %r" % t.on)
        if t.by not in m.roles:
            problems.append("transition by names undeclared role %r" % t.by)

    for s in m.states.values():
        if s.holder is not None and s.holder not in m.roles:
            problems.append("state %r has undeclared holder %r" % (s.name, s.holder))

    for t in m.transitions:
        for effect in t.effects:
            if effect == "escalate":
                continue
            prefix = next(
                (p for p in ("label.add:", "label.remove:") if effect.startswith(p)),
                None,
            )
            if prefix is None or len(effect) == len(prefix):
                problems.append("effect %r is not in the vocabulary "
                                "(label.add:<name>, label.remove:<name>, escalate)"
                                % effect)

    terminals = set(n for n, s in m.states.items() if s.terminal)
    accepting = set(n for n, s in m.states.items() if s.accepting)

    # At least one place where nothing is owed. This is the one property of
    # the old termination requirement worth keeping, restated: a protocol
    # with no state in which the conversation may rest is a protocol that
    # is never in a good state. It is not the same as "must terminate" --
    # an accepting state may have any number of transitions out of it --
    # and a machine with no terminal state at all satisfies it happily.
    #
    # Note this is *not* redundant with the reachability check below, and
    # deleting it would not be caught there: a machine whose every state is
    # non-accepting but which does have terminal states passes reachability
    # (everything can reach a terminal state) and would sail through with
    # nowhere for a run to rest.
    if not accepting:
        problems.append("no state is accepting; at least one state must be "
                        "a place the conversation may rest with nothing owed")

    for t in m.transitions:
        if t.frm in terminals:
            problems.append("terminal state %r has an outgoing transition" % t.frm)

    # Determinism. Two transitions sharing (from, on, by) with different
    # `to` states leave the machine with a choice no declaration resolves.
    # The engine is specified as a fold over the message trace, and a fold
    # is a function: it has exactly one result per (state, message). A
    # nondeterministic declaration therefore cannot be run at all, and
    # nothing else here says so -- every other check passes on it.
    destinations = {}
    for t in m.transitions:
        destinations.setdefault((t.frm, t.on, t.by), set()).add(t.to)
    for trigger in sorted(destinations):
        targets = destinations[trigger]
        if len(targets) > 1:
            problems.append(
                "transitions from %r on %r by %r are nondeterministic: they "
                "lead to %s" % (trigger[0], trigger[1], trigger[2],
                                ", ".join(repr(x) for x in sorted(targets))))

    # Holder agreement. A state's `holder` and a transition's `by` both
    # answer "who acts next" -- the channel-layer property the design makes
    # checkable. Declared twice and never reconciled, they can disagree:
    # a state held by `initiator` whose only exits are `by: responder` says
    # the initiator must act and that only the responder can.
    #
    # Terminal states are exempt (nobody acts next), and so is a state with
    # no `holder` at all, which is optional: with nothing declared there is
    # nothing to contradict. A non-terminal state with no outgoing
    # transition agrees vacuously; if something is owed there, the
    # can-a-run-stop check below reports it, and if nothing is owed there
    # (it is accepting) it is a resting place that simply happens not to be
    # declared terminal, which is not a defect.
    #
    # Accepting states are *not* exempt. Accepting says nothing is
    # *required* next, not that nothing can happen next: an accepting state
    # with outgoing transitions still has a role who acts if anyone does,
    # and `holder` naming a different one is still a contradiction.
    outgoing_by = {}
    for t in m.transitions:
        outgoing_by.setdefault(t.frm, set()).add(t.by)
    for name in sorted(names):
        s = m.states[name]
        if s.terminal or s.holder is None:
            continue
        disagreeing = sorted(a for a in outgoing_by.get(name, ()) if a != s.holder)
        if disagreeing:
            problems.append(
                "state %r declares holder %r but has outgoing transitions by %s"
                % (name, s.holder, ", ".join(repr(a) for a in disagreeing)))

    # An unused kind. A kind nobody fires on is vocabulary a publisher
    # believes is part of the protocol and that the protocol cannot
    # receive: the declaration says the machine understands it, and no
    # state does anything with it.
    fired_on = set(t.on for t in m.transitions)
    for kind in sorted(set(m.kinds) - fired_on):
        problems.append("kind %r is declared but no transition fires on it" % kind)

    # Registers: R1-R4. `declaration.parse` already enforced everything
    # about a register's own shape (a mapping, a `NAME`-shaped key,
    # exactly the four keys `fold`/`field`/`on`/`initial`, `fold` in
    # `FOLDS`, `on` a non-empty list of strings, `initial` an `int` or a
    # `bool`); what is left is cross-referencing one register's
    # declaration against `fields` and `kinds`, both declared elsewhere
    # in the same document, which is exactly what a parser -- reading one
    # key at a time -- cannot do.
    #
    # R3 is skipped for a register whose `field` is itself undeclared
    # (R1 already fired): there is no field type left to compare
    # `initial` against, the same reason the reachability and cap checks
    # below are skipped when `initial` (the state) is undeclared.
    #
    # The fold/argmax boundary, recorded here because a later session
    # reaching for `argmax` will look here first. A register remembers
    # one scalar, seeded at `initial`, and updated by exactly one field
    # read per matching step: conceptually, `register = fold(register,
    # message.field)` for every message whose kind is in `on`. `max` and
    # `last` both fit that shape, and both keep the register's value the
    # same Python type as the field across every step -- `max` because
    # comparing two values of the same type produces one of that same
    # type, `last` because it never combines anything, it only replaces.
    # That is what makes R3's type check ("`initial`'s type matches the
    # field's declared type") a promise that holds for the register's
    # entire life, not just at the start.
    #
    # `argmax` does not fit the shape: "the message that produced the
    # maximum" is a second value remembered alongside the scalar -- which
    # message, or which of its other fields -- and that second value is
    # not in general an `int` or a `bool` either. Admitting `argmax`
    # would mean admitting a second remembered value and a second type
    # for it, which is a different, larger feature than a bigger fold
    # over the one scalar this schema declares. `FOLDS` stays closed to
    # `max` and `last` until that is designed on purpose, not backed into
    # by one more string in a tuple.
    #
    # A third property, easy to read past: `FIELD_TYPES` is closed to
    # `int` and `bool`, so there is nothing a register could ever hold
    # that is a *payload* -- only a value a guard can order or test for
    # equality. Paxos's own next step needs exactly a payload: once a
    # proposer holds a quorum's worth of promises, it must propose the
    # *value* one of them already carried, not just the ballot that won.
    # That value is content, and content has no declarable field to carry
    # it in -- so no fold over this schema's fields, `max`, `last`, or a
    # future `argmax`, can ever be the register that remembers it.
    #
    # Nor can two registers forge it. `highest_ballot: max(ballot)`
    # alongside `chosen: last(value)` looks like it tracks both halves,
    # but `value` is content with no field to name it in the first place,
    # and even granting one, `last` remembers the *most recent* reading,
    # not the one paired with the maximum -- the two folds run
    # independently and go out of step on the first message that arrives
    # out of order. The forgery is not merely outside the vocabulary; it
    # computes the wrong answer, silently, the first time it matters.
    for name in sorted(m.registers):
        r = m.registers[name]
        field_declared = r.field in m.fields
        if not field_declared:                                        # R1
            problems.append(
                "register %r names undeclared field %r" % (name, r.field))
        for kind in r.on:                                              # R2
            if kind not in m.kinds:
                problems.append(
                    "register %r is fed by undeclared kind %r"
                    % (name, kind))
        if field_declared:                                             # R3
            field_type = m.fields[r.field].type
            initial_type = "bool" if isinstance(r.initial, bool) else "int"
            if initial_type != field_type:
                problems.append(
                    "register %r has initial %r, which is %s, but field "
                    "%r is declared %s"
                    % (name, r.initial, initial_type, r.field, field_type))
        if name in m.fields:                                           # R4
            problems.append(
                "register %r shares its name with a declared field"
                % (name,))

    # Guards: G1-G5. `declaration.parse` already enforced everything about
    # a guard's own shape (a mapping, exactly the three keys
    # `field`/`op`/`register`, each a string, `op` in `OP_ATOMS`); what is
    # left is cross-referencing a guard's `field` and `register` against
    # `fields` and `registers`, both declared elsewhere in the same
    # document, the same split the R1-R4 comment above draws for a
    # register's own `field` and `on`.
    #
    # G3 and G4 are both skipped when a name they would need is itself
    # undeclared -- G1/G2 already fired for that name, or (G4 only) the
    # register's own `field` is undeclared and R1 already fired for it --
    # the same reason R3 above is skipped for a register whose `field` is
    # undeclared: there is no field type left to compare against.
    #
    # One check named in the design this schema follows has no code here
    # on purpose: that the value a guard compares against is derivable
    # from the trace and nowhere else. It is enforced by construction, not
    # by a check that could fail -- a register's only source is a `fold`
    # over a `field` of messages of declared `kinds` (see `Register`,
    # above), and there is no syntax anywhere in this schema for a
    # register to come from anything else. A check here would have
    # nothing to reject.
    guarded_registers = set()
    for t in m.transitions:
        g = t.guard
        if g is None:
            continue
        where = "guard on transition from %r on %r by %r" % (t.frm, t.on, t.by)
        field_declared = g.field in m.fields
        if not field_declared:                                        # G1
            problems.append("%s names undeclared field %r" % (where, g.field))
        register_declared = g.register in m.registers
        if not register_declared:                                     # G2
            problems.append("%s names undeclared register %r" % (where, g.register))
        else:
            guarded_registers.add(g.register)
        if field_declared and g.op in ORDERING_OPS:                    # G3
            field_type = m.fields[g.field].type
            if field_type != "int":
                problems.append(
                    "%s uses ordering operator %r on field %r, which is "
                    "declared %s, not int -- ordering has no meaning the "
                    "engine could implement for a non-int field"
                    % (where, g.op, g.field, field_type))
        if field_declared and register_declared:                       # G4
            register_field = m.registers[g.register].field
            if register_field in m.fields:
                field_type = m.fields[g.field].type
                register_field_type = m.fields[register_field].type
                if field_type != register_field_type:
                    problems.append(
                        "%s compares field %r (%s) against register %r "
                        "(%s)" % (where, g.field, field_type, g.register,
                                 register_field_type))

    for name in sorted(m.registers):                                   # G5
        if name not in guarded_registers:
            problems.append(
                "register %r is declared but no guard names it" % (name,))

    # The reachability and cap checks both need a declared `initial` to
    # mean anything: with an undeclared initial state, forward-flooding
    # from it reaches nothing, which would report every other declared
    # state as unreachable *and* as unable to stop -- N+2 derivative
    # problems burying the one real one. Skip them and let the `initial`
    # message stand alone; the publisher re-runs after fixing `initial`,
    # which is cheap.
    if initial_declared:
        forward = {}
        backward = {}
        for t in m.transitions:
            forward.setdefault(t.frm, set()).add(t.to)
            backward.setdefault(t.to, set()).add(t.frm)

        reachable = _flood({m.initial}, forward)
        for name in sorted(names - reachable):
            problems.append("state %r is not reachable from the initial state" % name)

        # Nobody is owed something forever with no exit. The property is
        # "can this run ever stop", not "does this run terminate", so the
        # goal set is every state where a run may legitimately stop: an
        # accepting state (nothing further required) *or* a terminal one
        # (nothing further possible).
        #
        # Terminal non-accepting states must be seeds, not subjects. Such a
        # state is an error state -- an abort, a protocol violation, a peer
        # that went away -- and reaching it on purpose, with effects that
        # notify the peers, is a protocol doing its job. It can reach
        # nothing at all, by construction, so asking it to reach an
        # accepting state would report every error state in every protocol
        # as a defect. Seeding it instead says the right thing: arriving
        # there is a way for the conversation to stop.
        #
        # Accepting states are seeds for the same structural reason -- a
        # state a run may rest in owes no path onward.
        #
        # This is a seed change from the check it replaces (which flooded
        # backwards from `terminals` alone), not an algorithm change:
        # `_flood` takes its starting set as an argument and assumes
        # nothing about what the members are.
        can_stop = _flood(terminals | accepting, backward)
        for name in sorted(reachable - can_stop):
            problems.append(
                "state %r cannot reach a state where a run may stop; it owes "
                "a response and can reach no accepting state and no terminal "
                "state" % name)

        # Cap satisfiability, and only when a cap was declared at all.
        # `cap` is optional: absent means this protocol states no bound,
        # and there is then nothing to compare the machine against. Skipped
        # entirely rather than defaulted, because inventing a bound here
        # would put a number in front of the publisher that they never
        # wrote.
        #
        # When present, `cap` bounds the outbound messages one run may
        # emit -- the transitions it fires with `signal: true`, not every
        # transition it fires. A `signal: false` move is purely local: it
        # is not an outbound message and does not cost against the cap
        # (see SCHEMA.md's `cap` and `signal` sections). If even the
        # cheapest run from `initial` to an *accepting* state fires more
        # signalling transitions than the cap allows, no run can both stay
        # under the cap and reach a point where nothing is owed.
        #
        # The goal set is the accepting states, not the terminal ones and
        # not `terminals | accepting`: the question a cap answers is
        # whether the budget suffices to get somewhere *good*, and an abort
        # is not somewhere good. A cap that only reaches the error state is
        # a cap that cannot be satisfied.
        #
        # Consequence worth stating: when `initial` is itself accepting --
        # as `session-relay`'s `unopened` is -- the shortest distance is
        # zero and no positive cap can be too small. That is the correct
        # answer, not a hole: a run that may legitimately stop before
        # saying anything has emitted nothing, and nothing fits in any
        # budget. It does mean the check is vacuous for that shape of
        # machine.
        #
        # This makes it a shortest *weighted* path problem, not a plain
        # BFS: a `signal: true` edge costs 1, a `signal: false` edge costs
        # 0, and a run may freely spend any number of free local moves.
        # 0-1 BFS (a deque, pushing a 0-weight relaxation to the front and
        # a 1-weight relaxation to the back) finds that shortest weighted
        # distance in linear time, same as plain BFS would for the
        # unweighted graph it replaces.
        #
        # Nothing is reported when no accepting state is reachable at all:
        # that is already the reachability check's finding (or the
        # no-accepting-state one), and a cap message on top of it would be
        # a second symptom of one cause.
        if m.cap is not None:
            signal_forward = {}
            for t in m.transitions:
                signal_forward.setdefault(t.frm, []).append(
                    (t.to, 1 if t.signal else 0))

            shortest = _shortest_signal_distance(
                m.initial, accepting, signal_forward)
            if shortest is not None and shortest > m.cap:
                problems.append(
                    "cap %d is too small: the shortest run from %r to an "
                    "accepting state fires %d signalling transitions"
                    % (m.cap, m.initial, shortest))

    return problems


def _shortest_signal_distance(start, goals, graph):
    """Shortest weighted distance from `start` to the nearest member of
    `goals`, where `graph[node]` is a list of `(target, weight)` edges and
    `weight` is 1 for a `signal: true` transition, 0 for `signal: false`.
    Returns None when no member of `goals` is reachable at all.

    `goals` used to be the terminal states, which are sinks by
    construction; it is now the accepting states, which need not be --
    an accepting state may have any number of transitions out of it, and
    `start` may itself be a goal. Neither disturbs anything here. The goal
    set is read in exactly one place (the early return below), the search
    stops at the first goal it pops rather than expanding through it, and
    `start in goals` correctly answers 0. A goal's out-degree is never
    consulted, so re-targeting is a change of argument, not of algorithm.

    This is 0-1 BFS, not plain BFS: a graph with only 0/1 edge weights has
    a shortest-path structure plain (unweighted) BFS cannot compute
    correctly, because a 0-weight edge can make a "farther" node (by hop
    count) actually cheaper. A deque keeps the frontier ordered by
    distance without a heap: relaxing a node along a weight-0 edge pushes
    it to the *front* (it belongs at the current distance), and along a
    weight-1 edge pushes it to the *back* (it belongs one distance further
    out) -- so the deque is popped in non-decreasing distance order, same
    as plain BFS's FIFO queue is when every edge costs 1.
    """
    dist = {start: 0}
    frontier = deque([start])
    while frontier:
        node = frontier.popleft()
        d = dist[node]
        if node in goals:
            return d
        for target, weight in graph.get(node, ()):
            candidate = d + weight
            if candidate < dist.get(target, _INFINITY):
                dist[target] = candidate
                if weight == 0:
                    frontier.appendleft(target)
                else:
                    frontier.append(target)
    return None


def _flood(seeds, graph):
    seen = set()
    stack = list(seeds)
    while stack:
        node = stack.pop()
        if node in seen:
            continue
        seen.add(node)
        stack.extend(graph.get(node, ()))
    return seen
