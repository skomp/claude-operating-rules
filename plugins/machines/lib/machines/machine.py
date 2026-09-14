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

    if m.initial not in names:
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
            if effect != "escalate" and not (
                effect.startswith("label.add:") or effect.startswith("label.remove:")
            ):
                problems.append("effect %r is not in the vocabulary "
                                "(label.add:<name>, label.remove:<name>, escalate)"
                                % effect)

    terminals = set(n for n, s in m.states.items() if s.terminal)
    if not terminals:
        problems.append("no state is terminal; the machine cannot terminate")

    for t in m.transitions:
        if t.frm in terminals:
            problems.append("terminal state %r has an outgoing transition" % t.frm)

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

    return problems


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
