import re
import yaml
from .errors import DeclarationError
from .machine import FIELDS, REQUIRED, Machine, State, Transition

_FENCE = re.compile(r"^```machine[ \t]*\n(.*?)^```[ \t]*$", re.MULTILINE | re.DOTALL)

_STATE_KEYS = {"name", "holder", "terminal", "accepting"}
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
        if key not in FIELDS:
            raise DeclarationError("unknown field %r" % key, field=key)
    for key in REQUIRED:
        if key not in data:
            raise DeclarationError("missing field %r" % key, field=key)

    for key in ("machine", "version", "prefix", "initial"):
        _require_string(data[key], key)

    _require_prefix_length(data["prefix"])

    # `cap` is optional, and its absence is meaningful: this protocol
    # declares no bound. No default is substituted -- a cap the publisher
    # did not write is a bound nobody agreed to, and `check_machine` skips
    # the satisfiability check outright rather than measuring against an
    # invented number. Optional is not unvalidated, though: a cap that *is*
    # written must be a real count, and must not be a bool (Python
    # considers `True` an `int`, so `cap: true` would otherwise land as 1).
    cap = data.get("cap")
    if cap is not None:
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
                              _bool_field(raw, "terminal", False),
                              _bool_field(raw, "accepting", False))

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
# `RecursionError` out of `compile_pattern`, reached via `check_all` (see
# registry.py), past every shape guard above, as an uncaught traceback --
# exit 1 from `machines-check` for a crash, not a finding.
#
# 400 is the limit for *this* route: two orders of magnitude above
# `session-relay:v1 ` (17 characters) or any other plausible protocol
# prefix, comfortably under the 498 where a bare literal's recursion
# fails, checked here -- before the pattern parser ever sees the text --
# so the publisher gets a named field and a stated limit instead of a
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
# whatever either guard misses is caught as a last resort where
# `compile_pattern` is called (see registry.py's `RecursionError` handler)
# rather than propagating as a traceback.
_MAX_PREFIX_LENGTH = 400


def _require_prefix_length(prefix):
    if len(prefix) > _MAX_PREFIX_LENGTH:
        raise DeclarationError(
            "prefix is %d characters long; the limit is %d characters"
            % (len(prefix), _MAX_PREFIX_LENGTH),
            field="prefix")


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
