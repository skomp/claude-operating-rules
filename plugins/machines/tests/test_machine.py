import unittest
from machines.declaration import parse
from machines.machine import check_machine
from tests.test_declaration import VALID  # the known-good declaration

def mutate(old, new):
    return parse(VALID.replace(old, new))

class TestCheckMachine(unittest.TestCase):
    def test_the_known_good_machine_has_no_problems(self):
        self.assertEqual(check_machine(parse(VALID)), [])

    def test_initial_must_name_a_declared_state(self):
        m = mutate("initial: awaiting-triage", "initial: nowhere")
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
        m = parse(VALID)
        for s in m.states.values():
            s.terminal = False
        self.assertTrue(any("terminal" in p for p in check_machine(m)))

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
        m = mutate("initial: awaiting-triage", "initial: nowhere")
        problems = check_machine(m)
        self.assertEqual(len(problems), 1, problems)
        self.assertTrue(any("nowhere" in p for p in problems))

if __name__ == "__main__":
    unittest.main()
