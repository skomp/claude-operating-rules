REQUIRED = ("machine", "version", "prefix", "roles", "kinds",
            "cap", "initial", "states", "transitions")


class State(object):
    def __init__(self, name, holder=None, terminal=False):
        self.name = name
        self.holder = holder
        self.terminal = terminal


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


def check_machine(m):
    """Check a machine for well-formedness and termination.

    Returns a list of human-readable problems. An empty list means the
    machine is well-formed. This returns problems rather than raising,
    because a publisher wants every problem at once, not the first one.
    """
    problems = []
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
    if not terminals:
        problems.append("no state is terminal; the machine cannot terminate")

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
    # transition agrees vacuously, and is already reported by the
    # termination check below.
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

    # The reachability, termination and cap checks all need a declared
    # `initial` to mean anything: with an undeclared initial state,
    # forward-flooding from it reaches nothing, which would report every
    # other declared state as unreachable *and* unable to terminate --
    # N+2 derivative problems burying the one real one. Skip them and let
    # the `initial` message stand alone; the publisher re-runs after fixing
    # `initial`, which is cheap.
    if initial_declared:
        forward = {}
        backward = {}
        for t in m.transitions:
            forward.setdefault(t.frm, set()).add(t.to)
            backward.setdefault(t.to, set()).add(t.frm)

        reachable = _flood({m.initial}, forward)
        for name in sorted(names - reachable):
            problems.append("state %r is not reachable from the initial state" % name)

        can_finish = _flood(terminals, backward)
        for name in sorted(reachable - can_finish):
            problems.append("state %r cannot reach a terminal state" % name)

        # Cap satisfiability. `cap` bounds the outbound messages one run
        # may emit, i.e. the transitions it may fire. If even the shortest
        # path from `initial` to a terminal state is longer than the cap,
        # no run can both stay under the cap and end legitimately -- the
        # machine is declared to terminate and declared unable to. BFS,
        # because it is the shortest path that decides this, not any path.
        #
        # Nothing is reported when no terminal state is reachable at all:
        # that is already the termination check's finding, and a cap
        # message on top of it would be a second symptom of one cause.
        shortest = _shortest_distance(m.initial, terminals, forward)
        if shortest is not None and shortest > m.cap:
            problems.append(
                "cap %d is too small: the shortest run from %r to a terminal "
                "state fires %d transitions" % (m.cap, m.initial, shortest))

    return problems


def _shortest_distance(start, goals, graph):
    """Breadth-first distance in edges from `start` to the nearest member of
    `goals`, or None when no member of `goals` is reachable.
    """
    frontier = [start]
    seen = {start}
    distance = 0
    while frontier:
        if any(node in goals for node in frontier):
            return distance
        following = []
        for node in frontier:
            for target in graph.get(node, ()):
                if target not in seen:
                    seen.add(target)
                    following.append(target)
        frontier = following
        distance += 1
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
