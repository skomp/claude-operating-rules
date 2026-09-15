from collections import deque

from .pattern import PatternError, compile_pattern

# Every top-level field the parser accepts, and the subset of them a
# declaration must actually carry. `cap` is the one that is accepted and
# not required: a protocol that has no reason to terminate has no bound to
# declare, and forcing one would make its author write a number nobody
# believes -- which is the failure this framework exists to answer, not one
# it should cause. Absent means "this protocol declares no bound"; it does
# not mean zero, and there is no default.
FIELDS = ("machine", "version", "prefix", "roles", "kinds",
          "cap", "initial", "states", "transitions")
REQUIRED = tuple(f for f in FIELDS if f != "cap")

_INFINITY = float("inf")


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
    def __init__(self, frm, on, by, to, signal=False, effects=None):
        self.frm = frm
        self.on = on
        self.by = by
        self.to = to
        self.signal = signal
        self.effects = list(effects or [])


class Machine(object):
    def __init__(self, name, version, prefix, roles, kinds, cap,
                 initial, states, transitions):
        self.name = name
        self.version = version
        self.prefix = prefix
        self.roles = roles
        self.kinds = kinds
        self.cap = cap
        self.initial = initial
        self.states = states
        self.transitions = transitions


def prefix_problem(prefix):
    """Check a prefix pattern for whether it will compile at all.

    Returns None when `prefix` compiles; otherwise a human-readable problem
    string naming the field, `"prefix pattern %r: ..."`. This is a
    property of one machine's own declaration, not of a set of them, and
    used to be checked only in `registry.py`'s `check_all` -- which meant a
    caller that used `check_machine` directly (the documented answer to
    "is this machine well-formed") got no prefix validation at all. It is
    called from `check_machine` below for exactly that reason, and from
    `check_all` to decide whether a machine is fit to compare against
    others for a collision -- a pattern that will not compile cannot be
    intersected with anything.

    Catches `PatternError` -- from an unparseable prefix, or one that is
    nullable (matches the empty string, and would therefore claim every
    message; see pattern.py's `compile_pattern`) -- and nothing else,
    except one backstop.

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
    try:
        compile_pattern(prefix)
    except PatternError as exc:
        # Name the field. Every other `check_machine` message says which
        # field it is about; without the prefix here, a publisher reads
        # `unclosed group starting at position 0` and has to guess which
        # of nine fields is a pattern at all.
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
