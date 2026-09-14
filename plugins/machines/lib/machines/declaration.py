import re
import yaml
from .errors import DeclarationError
from .machine import REQUIRED, Machine, State, Transition

_FENCE = re.compile(r"^```machine[ \t]*\n(.*?)^```[ \t]*$", re.MULTILINE | re.DOTALL)

_STATE_KEYS = {"name", "holder", "terminal"}
_TRANSITION_KEYS = {"from", "on", "by", "to", "signal", "effects"}

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
    data = yaml.safe_load(extract_block(text))
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

    states = {}
    for raw in data["states"]:
        _reject_unknown(raw, _STATE_KEYS, "states")
        name = raw["name"]
        if name in states:
            raise DeclarationError("duplicate state %r" % name, field="states")
        states[name] = State(name, raw.get("holder"), bool(raw.get("terminal", False)))

    transitions = []
    for raw in data["transitions"]:
        raw = _coerce_on_key(raw)
        _reject_unknown(raw, _TRANSITION_KEYS, "transitions")
        transitions.append(Transition(
            raw["from"], raw["on"], raw["by"], raw["to"],
            bool(raw.get("signal", False)), raw.get("effects"),
        ))

    return Machine(
        data["machine"], data["version"], data["prefix"],
        dict(data["roles"]), set(data["kinds"]), cap,
        data["initial"], states, transitions,
    )

def _reject_unknown(raw, allowed, where):
    for key in raw:
        if key not in allowed:
            raise DeclarationError("unknown field %r in %s" % (key, where), field=key)

def _coerce_on_key(raw):
    # PyYAML's default (YAML 1.1) resolver treats the bare word "on" as the
    # boolean True, even when it appears as a mapping key -- so a transition
    # written as `{ on: question, ... }` parses with key True, not "on". Put
    # it back under the real field name before validating or reading it.
    if True in raw and "on" not in raw:
        raw = dict(raw)
        raw["on"] = raw.pop(True)
    return raw
