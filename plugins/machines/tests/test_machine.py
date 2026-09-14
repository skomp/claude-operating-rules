import unittest
from machines.declaration import parse
from machines.machine import check_machine
from tests.test_declaration import VALID  # the known-good declaration

def mutate(old, new):
    # Assert the splice landed. A `str.replace` whose `old` no longer
    # occurs in VALID returns VALID unchanged, so the test would go on
    # checking the known-good machine and pass while testing nothing --
    # which is exactly what happened to two of these when VALID's
    # `initial` changed.
    assert old in VALID, "mutate(%r, ...) matched nothing in VALID" % old
    return parse(VALID.replace(old, new))

class TestCheckMachine(unittest.TestCase):
    def test_the_known_good_machine_has_no_problems(self):
        self.assertEqual(check_machine(parse(VALID)), [])

    def test_initial_must_name_a_declared_state(self):
        m = mutate("initial: unopened", "initial: nowhere")
        self.assertTrue(any("nowhere" in p for p in check_machine(m)))

    def test_transition_to_an_undeclared_state_is_reported(self):
        m = mutate("to: awaiting-answer, signal: true }",
                   "to: nowhere, signal: true }")
        self.assertTrue(any("nowhere" in p for p in check_machine(m)))

    def test_transition_from_an_undeclared_state_is_reported(self):
        m = mutate("from: awaiting-triage, on: question",
                   "from: nowhere, on: question")
        self.assertTrue(any("nowhere" in p for p in check_machine(m)))

    def test_transition_on_an_undeclared_kind_is_reported(self):
        m = mutate("on: question", "on: shouting")
        self.assertTrue(any("shouting" in p for p in check_machine(m)))

    def test_transition_by_an_undeclared_role_is_reported(self):
        m = mutate("by: responder, to: awaiting-answer",
                   "by: bystander, to: awaiting-answer")
        self.assertTrue(any("bystander" in p for p in check_machine(m)))

    def test_a_state_with_an_undeclared_holder_is_reported(self):
        m = mutate("holder: responder", "holder: bystander")
        self.assertTrue(any("bystander" in p for p in check_machine(m)))

    def test_a_terminal_state_with_an_outgoing_transition_is_reported(self):
        # Give the terminal state `concluded` an exit back to a state that
        # already exists. No new state, no YAML indentation splice.
        m = parse(VALID)
        m.transitions.append(type(m.transitions[0])(
            "concluded", "question", "responder", "awaiting-triage"))
        self.assertTrue(any("concluded" in p for p in check_machine(m)))

    def test_a_machine_with_no_terminal_state_is_reported(self):
        # Assert the *specific* message, not just the word "terminal".
        # Deleting this check entirely left all 132 tests passing when
        # this assertion read `any("terminal" in p ...)`: with no terminal
        # state, the can-reach-a-terminal-state check fires for every
        # state, and its messages contain "terminal" too. A test that a
        # deleted check still satisfies is not testing that check.
        m = parse(VALID)
        for s in m.states.values():
            s.terminal = False
        self.assertTrue(
            any("no state is terminal" in p for p in check_machine(m)))

    def test_an_unreachable_state_is_reported(self):
        m = parse(VALID)
        m.states["orphan"] = type(m.states["concluded"])("orphan", terminal=True)
        self.assertTrue(any("orphan" in p for p in check_machine(m)))

    def test_a_state_that_cannot_reach_a_terminal_state_is_reported(self):
        # Remove both exits from awaiting-triage, leaving a two-state loop.
        m = parse(VALID)
        m.transitions = [t for t in m.transitions
                         if t.on not in ("conclusion", "stalemate")]
        problems = check_machine(m)
        self.assertTrue(any("awaiting-triage" in p and "terminal" in p
                            for p in problems))

    def test_an_effect_outside_the_vocabulary_is_reported(self):
        m = mutate('"label.add:session-relay:stalled"', '"run:curl example.com"')
        self.assertTrue(any("run:curl" in p for p in check_machine(m)))

    def test_each_permitted_effect_form_is_accepted(self):
        for effect in ("escalate", "label.add:anything", "label.remove:anything"):
            m = mutate('"escalate"', '"%s"' % effect)
            self.assertEqual(check_machine(m), [], effect)

    def test_a_label_effect_with_an_empty_name_is_reported(self):
        for effect in ("label.add:", "label.remove:"):
            m = mutate('"escalate"', '"%s"' % effect)
            self.assertTrue(
                any(repr(effect) in p for p in check_machine(m)), effect)

    def test_an_undeclared_initial_does_not_cascade_into_reachability_noise(self):
        # A typo in `initial` should not amplify into one "not reachable"
        # problem per declared state plus a spurious "cannot reach a
        # terminal state" -- only check 1's message should appear.
        m = mutate("initial: unopened", "initial: nowhere")
        problems = check_machine(m)
        self.assertEqual(len(problems), 1, problems)
        self.assertTrue(any("nowhere" in p for p in problems))


class TestChecksNoTaskOwned(unittest.TestCase):
    """Four properties the schema documents, the design says are checked at
    install, and nothing checked: every one of these machines returned `[]`
    from `check_machine`.

    A declared, documented, inert field reads as checked to every publisher
    who writes one. That is the failure this whole framework exists to
    answer, and it had appeared inside the framework: `cap` was parsed,
    validated as a positive integer, documented as "what makes termination
    checkable at all", and then compared to nothing.
    """

    def test_two_transitions_with_one_trigger_and_two_targets_are_reported(self):
        # Same (from, on, by), different `to`. The engine is specified as a
        # fold over the trace, and a fold has exactly one result per step,
        # so this machine cannot be run at all -- while every other check
        # passes on it.
        m = parse(VALID)
        m.transitions.append(type(m.transitions[0])(
            "awaiting-triage", "question", "responder", "stalled"))
        problems = check_machine(m)
        self.assertTrue(any("nondeterministic" in p for p in problems), problems)
        self.assertTrue(any("'awaiting-triage'" in p and "'question'" in p
                            for p in problems), problems)

    def test_two_transitions_with_one_trigger_and_one_target_are_not_reported(self):
        # A duplicate transition is redundant, not ambiguous: the fold
        # still has one result. Only a *divergent* target is a problem.
        m = parse(VALID)
        m.transitions.append(type(m.transitions[0])(
            "awaiting-triage", "question", "responder", "awaiting-answer"))
        self.assertEqual(
            [p for p in check_machine(m) if "nondeterministic" in p], [])

    def test_a_holder_contradicting_every_outgoing_by_is_reported(self):
        # `holder` and `by` both answer "who acts next". Declared twice,
        # never reconciled: this state says the initiator holds it and
        # that only the responder can move out of it.
        m = parse(VALID)
        m.states["awaiting-triage"].holder = "initiator"
        problems = check_machine(m)
        self.assertTrue(any("awaiting-triage" in p and "holder" in p
                            for p in problems), problems)

    def test_a_terminal_state_holder_is_not_required_to_agree(self):
        # Nobody acts next in a terminal state, so there is nothing for a
        # `holder` there to contradict.
        m = parse(VALID)
        m.states["concluded"].holder = "initiator"
        self.assertEqual(check_machine(m), [])

    def test_a_cap_smaller_than_the_shortest_run_is_reported(self):
        # unopened -> awaiting-triage -> concluded is two transitions, so
        # cap 1 makes terminating and staying under the cap mutually
        # exclusive. `m.cap` was read by nothing before this check.
        m = mutate("cap: 10", "cap: 1")
        problems = check_machine(m)
        self.assertTrue(any("cap 1" in p for p in problems), problems)

    def test_a_cap_exactly_equal_to_the_shortest_run_is_not_reported(self):
        # The boundary, in the direction that matters: a cap of 2 permits
        # the two-transition run, so it must not be reported. An off-by-one
        # here would reject machines that are perfectly runnable.
        m = mutate("cap: 10", "cap: 2")
        self.assertEqual(check_machine(m), [])

    def test_a_declared_kind_no_transition_fires_on_is_reported(self):
        m = mutate("kinds: [triage, question, answer, conclusion, stalemate]",
                   "kinds: [triage, question, answer, conclusion, stalemate, shouting]")
        problems = check_machine(m)
        self.assertTrue(any("'shouting'" in p for p in problems), problems)


if __name__ == "__main__":
    unittest.main()
