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
