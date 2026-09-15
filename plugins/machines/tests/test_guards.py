import unittest

from machines.declaration import parse
from machines.errors import DeclarationError
from tests.test_declaration import VALID  # the known-good declaration


# `GUARDED` grows across three tasks of this cycle, the way `VALID`
# (test_declaration.py) stays fixed but `test_machine.py`'s tests mutate
# copies of it: Task 3 (this one) adds `fields`; Task 5 adds a `guard:`
# mapping to two of the transitions below; Task 7 converts the bare
# `cap: 6` to the mapping form. That growth is intentional, not drift --
# each task's tests build on what the one before it left in place -- and
# this is the same declaration `valid-paxos-acceptor.md` (a fixture Task 9
# will create) carries.
#
# Two controller rulings shape the block exactly as written here:
#
# Ruling A -- `cap: 6` is bare, not `{ limit: 6, per: role }`. Measured:
# `declaration.py`'s cap handling accepts only `isinstance(cap, int)`, so
# the mapping form raises `DeclarationError` until Task 7 lands. Do not
# write the mapping form before then.
#
# Ruling B -- no transition below carries `guard:`. Measured:
# `declaration.py`'s `_TRANSITION_KEYS` does not include `"guard"`, so a
# transition that carried one would raise `DeclarationError` by name until
# Task 5 extends that set. Left unguarded, this declaration has two
# genuinely nondeterministic groups (`idle` on `prepare` by `proposer`,
# and `promised` on `accept-request` by `proposer`), which the shipped
# determinism check in `check_machine` reports for both. No test in this
# file asserts `check_machine(parse(GUARDED))` is empty -- Task 3's tests
# are all parse-level.
GUARDED = """
The paxos-acceptor protocol carries a single Paxos ballot number as a
declared header field. `registers` below is tolerated and parsed into
nothing until Task 4 gives the key meaning; this task is only about the
`fields` block -- the `ballot: int` line nothing yet guards on.

```machine
machine: paxos-acceptor
version: v1
prefix: "paxos:v1 "
roles:
  proposer: session
  acceptor: session
kinds: [prepare, promise, accept-request, accepted, rejected]
fields:
  ballot: int
registers:
  highest_promised: { fold: max, field: ballot, on: [prepare], initial: 0 }
cap: 6
initial: idle
states:
  - { name: idle,     holder: proposer, accepting: true }
  - { name: prepared, holder: acceptor }
  - { name: promised, holder: proposer, accepting: true }
  - { name: proposed, holder: acceptor }
  - { name: decided,  terminal: true, accepting: true }
transitions:
  - { from: idle, on: prepare, by: proposer, to: prepared, signal: true }
  - { from: idle, on: prepare, by: proposer, to: idle, signal: true }
  - { from: prepared, on: promise, by: acceptor, to: promised, signal: true }
  - { from: promised, on: accept-request, by: proposer, to: proposed, signal: true }
  - { from: promised, on: accept-request, by: proposer, to: idle, signal: true }
  - { from: proposed, on: accepted, by: acceptor, to: decided, signal: true }
  - { from: proposed, on: rejected, by: acceptor, to: idle, signal: true }
```
"""


def splice_guarded(old, new):
    # Assert the splice landed -- the same discipline `test_machine.py`'s
    # `mutate()` applies to `VALID` (see tests/test_machine.py:7-15). A
    # `str.replace` whose `old` no longer occurs in `GUARDED` returns it
    # unchanged, so a test that only inspects the parse result would go on
    # checking the unmodified declaration and pass while testing nothing.
    assert old in GUARDED, "splice_guarded(%r, ...) matched nothing in GUARDED" % old
    return GUARDED.replace(old, new)


class TestFields(unittest.TestCase):
    def test_a_declared_field_lands_with_its_type(self):
        m = parse(GUARDED)
        self.assertEqual(m.fields["ballot"].type, "int")

    def test_a_machine_with_no_fields_gets_an_empty_mapping_not_none(self):
        m = parse(VALID)
        self.assertEqual(m.fields, {})

    def test_an_explicit_empty_fields_mapping_is_also_empty(self):
        # "absent or empty" -- VALID (no `fields` key at all) covers absent;
        # this covers a publisher who writes the key with nothing under it.
        m = parse(splice_guarded("fields:\n  ballot: int", "fields: {}"))
        self.assertEqual(m.fields, {})

    def test_an_unknown_type_is_rejected_by_name(self):
        for bad in ("integer", "number", "string", "float"):
            with self.subTest(bad=bad):
                with self.assertRaises(DeclarationError) as ctx:
                    parse(splice_guarded("ballot: int", "ballot: " + bad))
                self.assertEqual(ctx.exception.field, "fields")

    def test_a_non_string_type_word_is_rejected(self):
        # `fields: {ballot: 3}` -- the brief's own motivating failure: an
        # integer reaching the guard's type check instead of a type word.
        with self.assertRaises(DeclarationError) as ctx:
            parse(splice_guarded("ballot: int", "ballot: 3"))
        self.assertEqual(ctx.exception.field, "fields")

    def test_a_field_name_with_a_dot_is_rejected(self):
        # The dotted namespace is reserved for the envelope (spec section 7):
        # the clock must never become something an author can declare.
        with self.assertRaises(DeclarationError):
            parse(splice_guarded("ballot: int", "envelope.clock: int"))

    def test_a_bool_field_is_accepted(self):
        m = parse(splice_guarded(
            "ballot: int", "ballot: int\n  blocking: bool"))
        self.assertEqual(m.fields["blocking"].type, "bool")


if __name__ == "__main__":
    unittest.main()
