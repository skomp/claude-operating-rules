import unittest
from machines.declaration import extract_block, parse
from machines.errors import DeclarationError

ONE = "intro\n\n```machine\nmachine: x\n```\n\ntrailing prose\n"
NONE = "intro only, no block\n"
TWO = "```machine\na: 1\n```\ntext\n```machine\nb: 2\n```\n"
OTHER_FENCE = "```yaml\nmachine: x\n```\n"

class TestExtractBlock(unittest.TestCase):
    def test_returns_block_contents_without_the_fences(self):
        self.assertEqual(extract_block(ONE), "machine: x\n")

    def test_no_block_raises(self):
        with self.assertRaises(DeclarationError):
            extract_block(NONE)

    def test_two_blocks_raises(self):
        with self.assertRaises(DeclarationError):
            extract_block(TWO)

    def test_a_yaml_fence_is_not_a_machine_fence(self):
        with self.assertRaises(DeclarationError):
            extract_block(OTHER_FENCE)

VALID = """
```machine
machine: session-relay
version: v1
prefix: "session-relay:v1 "
roles:
  initiator: repository
  responder: repository
kinds: [triage, question, answer, conclusion, stalemate]
cap: 10
initial: awaiting-triage
states:
  - { name: awaiting-triage, holder: responder }
  - { name: awaiting-answer, holder: initiator }
  - { name: concluded, terminal: true }
  - { name: stalled, terminal: true }
transitions:
  - { from: awaiting-triage, on: question, by: responder, to: awaiting-answer, signal: true }
  - { from: awaiting-answer, on: answer, by: initiator, to: awaiting-triage, signal: true }
  - { from: awaiting-triage, on: conclusion, by: responder, to: concluded, signal: true,
      effects: ["label.remove:session-relay:open"] }
  - { from: awaiting-triage, on: stalemate, by: responder, to: stalled, signal: true,
      effects: ["label.remove:session-relay:open", "label.add:session-relay:stalled", "escalate"] }
```
"""

class TestParse(unittest.TestCase):
    def test_parses_every_declared_field(self):
        m = parse(VALID)
        self.assertEqual(m.name, "session-relay")
        self.assertEqual(m.version, "v1")
        self.assertEqual(m.prefix, "session-relay:v1 ")
        self.assertEqual(m.cap, 10)
        self.assertEqual(m.initial, "awaiting-triage")
        self.assertEqual(set(m.roles), {"initiator", "responder"})
        self.assertEqual(len(m.states), 4)
        self.assertEqual(len(m.transitions), 4)

    def test_transition_fields_land_on_the_right_attributes(self):
        m = parse(VALID)
        t = m.transitions[0]
        self.assertEqual(t.frm, "awaiting-triage")
        self.assertEqual(t.on, "question")
        self.assertEqual(t.by, "responder")
        self.assertEqual(t.to, "awaiting-answer")
        self.assertTrue(t.signal)
        self.assertEqual(t.effects, [])

    def test_terminal_state_is_terminal_and_others_are_not(self):
        m = parse(VALID)
        self.assertTrue(m.states["concluded"].terminal)
        self.assertFalse(m.states["awaiting-triage"].terminal)

    def test_unknown_top_level_field_raises_and_names_it(self):
        bad = VALID.replace("cap: 10", "cap: 10\ncaps: 12")
        with self.assertRaises(DeclarationError) as ctx:
            parse(bad)
        self.assertEqual(ctx.exception.field, "caps")

    def test_missing_required_field_raises_and_names_it(self):
        bad = VALID.replace("cap: 10\n", "")
        with self.assertRaises(DeclarationError) as ctx:
            parse(bad)
        self.assertEqual(ctx.exception.field, "cap")

    def test_cap_must_be_a_positive_integer(self):
        for value in ("0", "-1", '"ten"', "true", "false"):
            with self.assertRaises(DeclarationError):
                parse(VALID.replace("cap: 10", "cap: " + value))

    def test_duplicate_state_name_raises(self):
        bad = VALID.replace(
            "- { name: concluded, terminal: true }",
            "- { name: awaiting-triage, terminal: true }",
        )
        with self.assertRaises(DeclarationError):
            parse(bad)


class TestBooleanTokenWordsStayStrings(unittest.TestCase):
    """PyYAML's default resolver treats yes/no/on/off (and case variants)
    as booleans in *any* scalar position -- a mapping key as much as a
    value. A publisher choosing one of those words as an ordinary name
    must get that name back, not a Python bool, in every position the
    schema exposes: a kind, a state name, a role name, a transition's
    `on`, and a `holder`. A test that only covers the `on:` key leaves
    the other four positions exactly as exposed as before.
    """

    def test_kind_named_with_a_boolean_token_word_stays_a_string(self):
        bad = VALID.replace(
            "kinds: [triage, question, answer, conclusion, stalemate]",
            "kinds: [yes, question, answer, conclusion, stalemate]",
        )
        m = parse(bad)
        self.assertIn("yes", m.kinds)
        self.assertNotIn(True, m.kinds)

    def test_state_named_with_a_boolean_token_word_stays_a_string(self):
        bad = VALID.replace(
            "- { name: stalled, terminal: true }",
            "- { name: yes, terminal: true }",
        )
        m = parse(bad)
        self.assertIn("yes", m.states)
        self.assertEqual(m.states["yes"].name, "yes")

    def test_role_named_with_a_boolean_token_word_stays_a_string(self):
        bad = VALID.replace("initiator: repository", "yes: repository")
        m = parse(bad)
        self.assertIn("yes", m.roles)

    def test_transition_on_a_boolean_token_word_stays_a_string(self):
        bad = VALID.replace("on: question", "on: yes")
        m = parse(bad)
        self.assertEqual(m.transitions[0].on, "yes")

    def test_holder_set_to_a_boolean_token_word_stays_a_string(self):
        bad = VALID.replace("holder: responder", "holder: yes")
        m = parse(bad)
        self.assertEqual(m.states["awaiting-triage"].holder, "yes")

    def test_signal_no_longer_accepts_yes_as_true(self):
        # The cost of narrowing the resolver: `signal: yes` is now the
        # string "yes", not the boolean True, and this field requires an
        # actual boolean rather than falling back to Python truthiness.
        bad = VALID.replace("signal: true", "signal: yes", 1)
        with self.assertRaises(DeclarationError):
            parse(bad)


_STATES_BLOCK = """states:
  - { name: awaiting-triage, holder: responder }
  - { name: awaiting-answer, holder: initiator }
  - { name: concluded, terminal: true }
  - { name: stalled, terminal: true }
"""

_TRANSITIONS_BLOCK = """transitions:
  - { from: awaiting-triage, on: question, by: responder, to: awaiting-answer, signal: true }
  - { from: awaiting-answer, on: answer, by: initiator, to: awaiting-triage, signal: true }
  - { from: awaiting-triage, on: conclusion, by: responder, to: concluded, signal: true,
      effects: ["label.remove:session-relay:open"] }
  - { from: awaiting-triage, on: stalemate, by: responder, to: stalled, signal: true,
      effects: ["label.remove:session-relay:open", "label.add:session-relay:stalled", "escalate"] }
"""

class TestMalformedListShapedFields(unittest.TestCase):
    def test_kinds_that_is_not_a_list_raises_and_names_it(self):
        bad = VALID.replace(
            "kinds: [triage, question, answer, conclusion, stalemate]",
            "kinds: yes",
        )
        with self.assertRaises(DeclarationError) as ctx:
            parse(bad)
        self.assertEqual(ctx.exception.field, "kinds")

    def test_states_that_is_not_a_list_raises_and_names_it(self):
        bad = VALID.replace(_STATES_BLOCK, "states: not-a-list\n")
        with self.assertRaises(DeclarationError) as ctx:
            parse(bad)
        self.assertEqual(ctx.exception.field, "states")

    def test_transitions_that_is_not_a_list_raises_and_names_it(self):
        bad = VALID.replace(_TRANSITIONS_BLOCK, "transitions: not-a-list\n")
        with self.assertRaises(DeclarationError) as ctx:
            parse(bad)
        self.assertEqual(ctx.exception.field, "transitions")

if __name__ == "__main__":
    unittest.main()
