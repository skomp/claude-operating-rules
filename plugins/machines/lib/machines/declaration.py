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

    for key in ("machine", "version", "prefix", "initial"):
        _require_string(data[key], key)

    cap = data["cap"]
    if not isinstance(cap, int) or isinstance(cap, bool) or cap < 1:
        raise DeclarationError("cap must be a positive integer", field="cap")

    kinds = data["kinds"]
    if not isinstance(kinds, list):
        raise DeclarationError("kinds must be a list of strings", field="kinds")
    for kind in kinds:
        _require_string(kind, "kinds", "each entry of ")

    roles = data["roles"]
    if not isinstance(roles, dict):
        raise DeclarationError(
            "roles must be a mapping of role name to what it binds to",
            field="roles")

    raw_states = data["states"]
    if not isinstance(raw_states, list):
        raise DeclarationError("states must be a list", field="states")

    raw_transitions = data["transitions"]
    if not isinstance(raw_transitions, list):
        raise DeclarationError("transitions must be a list", field="transitions")

    states = {}
    for raw in raw_states:
        _require_mapping(raw, "states")
        _reject_unknown(raw, _STATE_KEYS, "states")
        name = _require_string(_require_present(raw, "name", "states"),
                               "name", "a states entry's ")
        if name in states:
            raise DeclarationError("duplicate state %r" % name, field="states")
        holder = raw.get("holder")
        if holder is not None:
            _require_string(holder, "holder", "a states entry's ")
        states[name] = State(name, holder,
                              _bool_field(raw, "terminal", False))

    transitions = []
    for raw in raw_transitions:
        _require_mapping(raw, "transitions")
        _reject_unknown(raw, _TRANSITION_KEYS, "transitions")
        field = {}
        for key in ("from", "on", "by", "to"):
            field[key] = _require_string(
                _require_present(raw, key, "transitions"),
                key, "a transitions entry's ")
        transitions.append(Transition(
            field["from"], field["on"], field["by"], field["to"],
            _bool_field(raw, "signal", False), _effects_field(raw),
        ))

    return Machine(
        data["machine"], data["version"], data["prefix"],
        dict(roles), set(kinds), cap,
        data["initial"], states, transitions,
    )

def _reject_unknown(raw, allowed, where):
    for key in raw:
        if key not in allowed:
            raise DeclarationError("unknown field %r in %s" % (key, where), field=key)

# --- shape guards -------------------------------------------------------
#
# Everything below exists so that no hand-written declaration can reach a
# caller as a raw Python traceback. `machines-check` has three exit codes on
# purpose: 1 means "I checked, and found a problem", 2 means "I could not
# check at all". An uncaught KeyError/TypeError/ValueError out of `parse`
# exits 1 with a traceback, which reports the tool's own crash as if it
# were a finding about the publisher's machine -- exactly what exit 2
# exists to prevent. Every guard here raises DeclarationError naming the
# field instead, which the CLI already knows how to report.
#
# The existing list-shape guards above (`kinds`, `states`, `transitions`
# must be lists) are the same idea; these extend it to the containers and
# scalars those guards did not reach.

def _require_mapping(value, where):
    """Each `states`/`transitions` entry must be a mapping.

    Checked before `_reject_unknown` iterates it: `for key in 5` is a
    TypeError, and `for key in "abc"` silently iterates characters.
    """
    if not isinstance(value, dict):
        raise DeclarationError(
            "each %s entry must be a mapping, not %r" % (where, value),
            field=where)
    return value

def _require_present(raw, key, where):
    if key not in raw:
        raise DeclarationError(
            "a %s entry is missing required field %r" % (where, key), field=key)
    return raw[key]

def _require_string(value, field, where=""):
    """A field the schema documents as a string must actually be one.

    Not cosmetic: `prefix: 5` parses fine and then fails with
    `TypeError: object of type 'int' has no len()` deep inside the pattern
    compiler, and a state `name` that is an int becomes a dict key no
    transition can ever name.
    """
    if not isinstance(value, str):
        raise DeclarationError(
            "%s%s must be a string, not %r" % (where, field, value), field=field)
    return value

def _effects_field(raw):
    """`effects` is an optional list of strings.

    The bare-string case is called out separately because it is the one
    that did not crash: `effects: escalate` is iterable, so the effect
    vocabulary check walked it character by character and emitted eight
    problems about `'e'`, `'s'`, `'c'`... -- eight wrong answers instead of
    one right one. Same hazard as `kinds: "yes"`, same fix.
    """
    if "effects" not in raw:
        return []
    effects = raw["effects"]
    if not isinstance(effects, list):
        raise DeclarationError(
            "effects must be a list of strings, not %r" % (effects,),
            field="effects")
    for effect in effects:
        _require_string(effect, "effects", "each entry of ")
    return effects

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
