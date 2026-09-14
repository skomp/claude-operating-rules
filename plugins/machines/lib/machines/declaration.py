import re
import yaml
from .errors import DeclarationError
from .machine import REQUIRED, Machine, State, Transition

_FENCE = re.compile(r"^```machine[ \t]*\n(.*?)^```[ \t]*$", re.MULTILINE | re.DOTALL)

_STATE_KEYS = {"name", "holder", "terminal"}
_TRANSITION_KEYS = {"from", "on", "by", "to", "signal", "effects"}


class MachineSafeLoader(yaml.SafeLoader):
    """A SafeLoader whose implicit boolean resolution is narrowed to
    true/false (and case variants) only.

    PyYAML's default resolver follows YAML 1.1, under which the bare words
    yes/no/on/off (and their case variants -- Yes, ON, off, ...; bare y/n
    alone are unaffected) also resolve to booleans, in *any* scalar position
    a publisher can write -- a mapping key as much as a value. For this
    schema that is not a cosmetic surprise, it is a correctness hole: a kind
    declared `on`, a state named `no`, a role called `yes`, a transition's
    `on: yes` -- each would silently become a Python bool instead of the
    string the publisher wrote, and every check built on equality
    (`t.on in m.kinds`, a dict key lookup) keeps "working" against the
    corrupted value with no error raised anywhere. That is worse than a
    crash: coherent-looking data that is simply wrong.

    Narrowing the resolver removes the landmine in one place, for every
    field, present and future, rather than patching each exposed position
    by hand. The cost: `signal: yes` no longer means true. A publisher must
    write `signal: true`. Documented in SCHEMA.md.
    """


MachineSafeLoader.yaml_implicit_resolvers = {
    first: [(tag, regexp) for tag, regexp in resolvers
            if tag != "tag:yaml.org,2002:bool"]
    for first, resolvers in yaml.SafeLoader.yaml_implicit_resolvers.items()
}
MachineSafeLoader.add_implicit_resolver(
    "tag:yaml.org,2002:bool",
    re.compile(r"^(?:true|True|TRUE|false|False|FALSE)$"),
    list("tTfF"),
)


def extract_block(text):
    blocks = _FENCE.findall(text)
    if not blocks:
        raise DeclarationError("no ```machine block found")
    if len(blocks) > 1:
        raise DeclarationError(
            "found %d ```machine blocks; a bundle declares exactly one" % len(blocks)
        )
    return blocks[0]

def parse(text):
    data = yaml.load(extract_block(text), Loader=MachineSafeLoader)
    if not isinstance(data, dict):
        raise DeclarationError("a machine block must be a mapping")

    for key in data:
        if key not in REQUIRED:
            raise DeclarationError("unknown field %r" % key, field=key)
    for key in REQUIRED:
        if key not in data:
            raise DeclarationError("missing field %r" % key, field=key)

    cap = data["cap"]
    if not isinstance(cap, int) or isinstance(cap, bool) or cap < 1:
        raise DeclarationError("cap must be a positive integer", field="cap")

    kinds = data["kinds"]
    if not isinstance(kinds, list):
        raise DeclarationError("kinds must be a list of strings", field="kinds")

    raw_states = data["states"]
    if not isinstance(raw_states, list):
        raise DeclarationError("states must be a list", field="states")

    raw_transitions = data["transitions"]
    if not isinstance(raw_transitions, list):
        raise DeclarationError("transitions must be a list", field="transitions")

    states = {}
    for raw in raw_states:
        _reject_unknown(raw, _STATE_KEYS, "states")
        name = raw["name"]
        if name in states:
            raise DeclarationError("duplicate state %r" % name, field="states")
        states[name] = State(name, raw.get("holder"),
                              _bool_field(raw, "terminal", False))

    transitions = []
    for raw in raw_transitions:
        _reject_unknown(raw, _TRANSITION_KEYS, "transitions")
        transitions.append(Transition(
            raw["from"], raw["on"], raw["by"], raw["to"],
            _bool_field(raw, "signal", False), raw.get("effects"),
        ))

    return Machine(
        data["machine"], data["version"], data["prefix"],
        dict(data["roles"]), set(kinds), cap,
        data["initial"], states, transitions,
    )

def _reject_unknown(raw, allowed, where):
    for key in raw:
        if key not in allowed:
            raise DeclarationError("unknown field %r in %s" % (key, where), field=key)

def _bool_field(raw, key, default):
    # Narrowing MachineSafeLoader's bool resolution (above) stops YAML from
    # silently turning `signal: yes` into the boolean True at parse time --
    # but Python's own bool() is just as happy to turn the resulting string
    # "yes" into True by truthiness, which is the same silent corruption
    # wearing a different hat. Require an actual bool here instead.
    if key not in raw:
        return default
    value = raw[key]
    if not isinstance(value, bool):
        raise DeclarationError(
            "%s must be true or false, not %r" % (key, value), field=key)
    return value
