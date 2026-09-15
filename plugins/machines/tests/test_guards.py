import unittest

from machines.declaration import parse
from machines.errors import DeclarationError
from machines.machine import check_machine
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
declared header field, and one register -- `highest_promised` -- that
folds it by `max` over `prepare` messages. Nothing guards on it yet: no
transition below carries a `guard:` mapping until Task 5 adds one.

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


def _splice_once(text, old, new):
    # Assert the splice landed on exactly the text intended -- the same
    # discipline `test_machine.py`'s `mutate()` applies to `VALID` (see
    # tests/test_machine.py:7-15), strengthened one step further. A
    # `str.replace` whose `old` no longer occurs in `text` returns it
    # unchanged, so a test that only inspects the parse result would go
    # on checking the unmodified declaration and pass while testing
    # nothing -- that is what `old in text` alone catches. But `old`
    # occurring *more than once* is its own silent failure: `str.replace`
    # rewrites every occurrence, so a caller who means to touch one
    # register's `field: ballot` and forgets that `GUARDED`'s prose above
    # the fence also says "declared header field" would splice text the
    # test never meant to touch, with no error anywhere -- a defect this
    # module's own history has already produced once. Counting `old`'s
    # occurrences and requiring exactly one closes that gap for every
    # caller, not just the one that tripped over it.
    #
    # Takes `text` rather than always reading `GUARDED` so a test that
    # needs more than one substitution -- progressively mutating the same
    # string -- can chain calls (splice `GUARDED` once, then splice the
    # result again) and keep the same exactly-once guarantee at every
    # step, instead of falling back to a raw, unguarded `str.replace`
    # once the text in hand is no longer literally `GUARDED`.
    # `splice_guarded`, below, is the common case (splicing `GUARDED`
    # itself) built on top of this.
    count = text.count(old)
    assert count == 1, (
        "splice(%r, ...) matched %d times, not exactly once -- pick a "
        "more specific target" % (old, count))
    return text.replace(old, new)


def splice_guarded(old, new):
    return _splice_once(GUARDED, old, new)


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


class TestRegisters(unittest.TestCase):
    def test_a_register_lands_with_its_fold_field_kinds_and_initial(self):
        r = parse(GUARDED).registers["highest_promised"]
        self.assertEqual(r.fold, "max")
        self.assertEqual(r.field, "ballot")
        self.assertEqual(r.on, ["prepare"])
        self.assertEqual(r.initial, 0)

    def test_an_unknown_fold_is_rejected(self):
        # `count` is the fold that invites "how many promises have I
        # collected" -- which is quorum, which is aggregation over a set
        # of messages, which the spec forbids a register from expressing.
        # Refusing it here costs nothing and removes the temptation to
        # reach for it as the readable-looking way to smuggle quorum
        # counting past that restriction one message at a time.
        #
        # `argmax` needs a second remembered value (which message, or
        # which of its other fields, produced the maximum) alongside the
        # scalar -- a second thing to remember, not a bigger fold over
        # the one a register holds. See the fold/argmax boundary comment
        # next to the R1-R4 checks in `check_machine`.
        for bad in ("count", "argmax", "sum", "min", "first"):
            with self.subTest(bad=bad):
                with self.assertRaises(DeclarationError) as ctx:
                    parse(splice_guarded("fold: max", "fold: " + bad))
                self.assertEqual(ctx.exception.field, "registers")

    def test_an_empty_on_list_is_rejected(self):
        with self.assertRaises(DeclarationError) as ctx:
            parse(splice_guarded("on: [prepare]", "on: []"))
        self.assertEqual(ctx.exception.field, "registers")

    def test_a_register_on_an_undeclared_field_is_reported(self):
        m = parse(splice_guarded("field: ballot", "field: nope"))
        problems = check_machine(m)
        self.assertTrue(
            any("highest_promised" in p and "nope" in p for p in problems),
            problems)

    def test_a_register_fed_by_an_undeclared_kind_is_reported(self):
        m = parse(splice_guarded("on: [prepare]", "on: [shouting]"))
        problems = check_machine(m)
        self.assertTrue(
            any("highest_promised" in p and "shouting" in p
                for p in problems),
            problems)

    def test_a_bool_initial_on_an_int_field_is_reported(self):
        m = parse(splice_guarded("initial: 0", "initial: true"))
        problems = check_machine(m)
        self.assertTrue(
            any("highest_promised" in p for p in problems), problems)

    def test_an_int_initial_on_a_bool_field_is_reported(self):
        # Two splices, chained: add a bool field, then point the register
        # at it, leaving `initial: 0` (an int) untouched. Both go through
        # `_splice_once`, so each carries the same exactly-once guarantee
        # `splice_guarded` gives `GUARDED` itself -- there is no raw,
        # unguarded `str.replace` against `GUARDED` or text derived from
        # it anywhere in this file.
        text = _splice_once(
            GUARDED, "fields:\n  ballot: int",
            "fields:\n  ballot: int\n  blocking: bool")
        text = _splice_once(text, "field: ballot", "field: blocking")
        m = parse(text)
        problems = check_machine(m)
        self.assertTrue(
            any("highest_promised" in p for p in problems), problems)

    def test_a_register_sharing_a_name_with_a_field_is_reported(self):
        # `highest_promised` occurs twice in GUARDED -- once in the prose
        # above the fence, once as the registers key -- so `old` has to
        # be the unique `registers:` line itself, not the bare name.
        m = parse(splice_guarded(
            "registers:\n  highest_promised:", "registers:\n  ballot:"))
        problems = check_machine(m)
        self.assertTrue(
            any("ballot" in p and "field" in p for p in problems), problems)


if __name__ == "__main__":
    unittest.main()
