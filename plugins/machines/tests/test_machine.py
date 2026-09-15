import unittest
from machines.declaration import parse
from machines.machine import (Machine, State, Transition, check_machine,
                               _MAX_PREFIX_LENGTH)
from tests.test_declaration import VALID  # the known-good declaration

def mutate(old, new):
    # Assert the splice landed. A `str.replace` whose `old` no longer
    # occurs in VALID returns VALID unchanged, so the test would go on
    # checking the known-good machine and pass while testing nothing --
    # which is exactly what happened to two of these when VALID's
    # `initial` changed.
    assert old in VALID, "mutate(%r, ...) matched nothing in VALID" % old
    return parse(VALID.replace(old, new))


def _linear_machine(cap):
    """start -(signal)-> middle -(signal)-> done, and only `done` accepts.

    Two signalling transitions to the one place a run may legitimately
    stop, so the shortest signalling distance to an accepting state is
    exactly 2 and the cap check has a boundary to be right or wrong about.
    """
    return Machine(
        "linear-test", "v1", "x",
        {"role": "party"}, {"step1", "step2"}, cap,
        "start",
        {
            "start": State("start"),
            "middle": State("middle"),
            "done": State("done", terminal=True, accepting=True),
        },
        [
            Transition("start", "step1", "role", "middle", signal=True),
            Transition("middle", "step2", "role", "done", signal=True),
        ],
    )

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

    def test_an_unreachable_state_is_reported(self):
        m = parse(VALID)
        m.states["orphan"] = type(m.states["concluded"])(
            "orphan", terminal=True, accepting=True)
        self.assertTrue(any("orphan" in p for p in check_machine(m)))

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

    def test_a_prefix_that_will_not_compile_is_reported_by_check_machine(self):
        m = _linear_machine(cap=2)
        m.prefix = "a*"          # nullable: claims every message
        problems = check_machine(m)
        self.assertTrue(any("prefix" in p for p in problems), problems)

    def test_a_compiling_prefix_adds_no_problem(self):
        self.assertEqual(check_machine(_linear_machine(cap=2)), [])

    def test_a_prefix_over_the_length_limit_is_reported_by_check_machine(self):
        # `declaration.parse` rejects this before a Machine ever exists
        # (see declaration.py's `_require_prefix_length`), so this only
        # exercises a hand-built Machine -- exactly the case check_machine
        # is now the sole gate for.
        m = _linear_machine(cap=2)
        m.prefix = "a" * (_MAX_PREFIX_LENGTH + 1)
        problems = check_machine(m)
        self.assertEqual(len(problems), 1, problems)
        self.assertIn("prefix", problems[0])

    def test_a_prefix_at_the_length_limit_adds_no_problem(self):
        m = _linear_machine(cap=2)
        m.prefix = "a" * _MAX_PREFIX_LENGTH
        self.assertEqual(check_machine(m), [])


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
        # start -> middle -> done is two signalling transitions to the only
        # accepting state, so cap 1 makes settling and staying under the cap
        # mutually exclusive. `m.cap` was read by nothing before this check.
        #
        # This used to be `mutate("cap: 10", "cap: 1")` against VALID, and
        # it cannot be any more: `unopened` is now accepting, and it is also
        # `initial`, so VALID's shortest signalling run to an accepting
        # state is zero transitions long and *every* positive cap satisfies
        # it. That is the correct answer under the accepting-state model --
        # a session-relay run may legitimately stop before filing anything,
        # having emitted nothing -- but it means VALID no longer exercises
        # this check at all, so the check needs a machine of its own.
        m = _linear_machine(cap=1)
        problems = check_machine(m)
        self.assertTrue(any("cap 1" in p for p in problems), problems)

    def test_a_cap_exactly_equal_to_the_shortest_run_is_not_reported(self):
        # The boundary, in the direction that matters: a cap of 2 permits
        # the two-transition run, so it must not be reported. An off-by-one
        # here would reject machines that are perfectly runnable.
        self.assertEqual(check_machine(_linear_machine(cap=2)), [])

    def test_an_accepting_initial_state_satisfies_every_cap(self):
        # The consequence of the line above, pinned rather than left
        # implicit: a machine whose initial state is accepting can stop
        # having emitted nothing, so no positive cap can be too small for
        # it. VALID is exactly that machine now.
        m = mutate("cap: 10", "cap: 1")
        self.assertEqual([p for p in check_machine(m) if "cap" in p], [])

    def test_local_moves_on_the_shortest_run_do_not_count_against_the_cap(self):
        # The re-reviewer's own machine: two purely-local moves
        # (`signal: false`) followed by one signalling move, and cap 1.
        # `cap` bounds outbound *messages*, and a local move emits none --
        # so this run costs 1, not 3, and cap 1 must accept it. Counting
        # every transition (the pre-fix behaviour) wrongly rejected this
        # exact shape.
        m = Machine(
            "local-moves-test", "v1", "x",
            {"role": "party"}, {"step1", "step2", "step3"}, 1,
            "start",
            {
                "start": State("start"),
                "middle": State("middle"),
                "late": State("late"),
                "done": State("done", terminal=True, accepting=True),
            },
            [
                Transition("start", "step1", "role", "middle", signal=False),
                Transition("middle", "step2", "role", "late", signal=False),
                Transition("late", "step3", "role", "done", signal=True),
            ],
        )
        self.assertEqual(check_machine(m), [])

    def test_a_cap_exceeded_by_signalling_transitions_alone_is_reported(self):
        # Two consecutive `signal: true` transitions and nothing else on
        # the only run to a terminal state, cap 1. The direction that
        # matters most to get right: under-counting here would silently
        # accept a machine that really does exceed its cap.
        m = Machine(
            "signal-only-test", "v1", "x",
            {"role": "party"}, {"step1", "step2"}, 1,
            "start",
            {
                "start": State("start"),
                "middle": State("middle"),
                "done": State("done", terminal=True, accepting=True),
            },
            [
                Transition("start", "step1", "role", "middle", signal=True),
                Transition("middle", "step2", "role", "done", signal=True),
            ],
        )
        problems = check_machine(m)
        cap_problems = [p for p in problems if "cap" in p]
        self.assertEqual(len(cap_problems), 1, problems)
        self.assertIn("2 signalling transitions", cap_problems[0])

    def test_a_declared_kind_no_transition_fires_on_is_reported(self):
        m = mutate("kinds: [triage, question, answer, conclusion, stalemate]",
                   "kinds: [triage, question, answer, conclusion, stalemate, shouting]")
        problems = check_machine(m)
        self.assertTrue(any("'shouting'" in p for p in problems), problems)


class TestAcceptingStates(unittest.TestCase):
    """Accepting is not terminal, and the checks that tell them apart.

    Cycle A shipped a schema that required `cap`, required at least one
    *terminal* state, and required every state to reach one -- which bakes
    "a protocol terminates" into the framework as a law. It is not one. It
    is a property of some protocols, and requiring it forces an author with
    a continuous protocol to declare a bound they do not mean, which is the
    exact failure this framework exists to answer.

    **Accepting** means nothing further is *required*: it is fine for the
    conversation to stop here. **Terminal** means nothing further is
    *possible*. The two are independent, and all four combinations are
    legal:

    - accepting and terminal -- `concluded`. Done, and nothing was left owed.
    - accepting, not terminal -- a responder sitting idle, willing to answer
      another question but owing nobody anything. The gossip shape.
    - neither -- a session that has just sent a message and is waiting for
      the reply. Something is owed and the conversation can continue.
    - **terminal and not accepting** -- an error state. The conversation
      ended while something was still owed, *and that is the point of
      reaching it*: an abort, a protocol violation, a peer that went away.
      The machine stops, the effects notify the peers, and the fact that
      the conversation was unfinished is exactly what is being reported.

    That fourth row is the one this class exists to protect. An earlier
    draft of these checks required every terminal state to be accepting,
    which would have forbidden the most useful error state a protocol can
    have.
    """

    def test_a_machine_with_no_accepting_state_is_reported(self):
        # Assert the *specific* message, not merely the word "accepting".
        # The predecessor of this test (against `terminal`) was shown to
        # pass with the check under test deleted outright, because the
        # per-state reachability messages contain the same word. A test a
        # deleted check still satisfies is not testing that check.
        m = parse(VALID)
        for s in m.states.values():
            s.accepting = False
        problems = check_machine(m)
        self.assertTrue(any("no state is accepting" in p for p in problems))
        # And exactly that, once. Every state can still reach a terminal
        # state, so the reachability check has nothing to say -- the
        # cascade its `terminal`-era predecessor produced (one message per
        # state on top of the real finding) does not happen here.
        self.assertEqual(len(problems), 1, problems)

    def test_a_branch_whose_every_future_ends_badly_is_deliberately_not_reported(self):
        # `doomed` is non-accepting and its only future is `aborted`, which
        # is terminal and non-accepting. Entering `doomed` commits the run
        # to ending with something still owed.
        #
        # That is legal, on purpose, and this test pins the decision rather
        # than the absence of a thought. The checker cannot tell a bug from
        # a correctly-modelled doomed branch -- "once the versions are
        # incompatible, every route aborts" is a true thing to declare --
        # and there is no field with which an author could say "yes, I mean
        # it". An unsuppressible complaint about a valid machine is worse
        # than a missing one. Recorded as an open question in the design
        # spec, not decided here.
        m = Machine(
            "doomed-branch", "v1", "x",
            {"role": "party"}, {"fork", "fail"}, None,
            "idle",
            {
                "idle": State("idle", holder="role", accepting=True),
                "doomed": State("doomed", holder="role"),
                "aborted": State("aborted", terminal=True),
            },
            [
                Transition("idle", "fork", "role", "doomed", signal=True),
                Transition("doomed", "fail", "role", "aborted", signal=True,
                           effects=["escalate"]),
            ],
        )
        self.assertEqual(check_machine(m), [])

    def test_a_state_owed_something_with_no_way_to_stop_at_all_is_reported(self):
        # Remove both exits from awaiting-triage, leaving awaiting-triage
        # and awaiting-answer trading messages forever with no route to
        # anywhere a run may stop -- not to an accepting state, and not to
        # a terminal one either. Being owed something forever with no exit
        # is the property this check protects.
        m = parse(VALID)
        m.transitions = [t for t in m.transitions
                         if t.on not in ("conclusion", "stalemate")]
        problems = check_machine(m)
        self.assertTrue(
            any("awaiting-triage" in p and "cannot reach a state where a run "
                "may stop" in p for p in problems), problems)
        self.assertTrue(
            any("awaiting-answer" in p and "cannot reach a state where a run "
                "may stop" in p for p in problems), problems)

    def test_an_accepting_state_needs_no_path_to_anywhere(self):
        # The other direction of the same check: an accepting state is
        # already somewhere a run may stop, so it owes no path onward. A
        # check that flooded backwards and then complained about every
        # state outside the flood would report the seeds themselves.
        m = parse(VALID)
        self.assertEqual(
            [p for p in check_machine(m) if "may stop" in p], [])

    def test_a_terminal_state_that_is_not_accepting_is_legal(self):
        # The error state. `stalled` is terminal and not accepting: the
        # thread stops with the initiator's question unanswered, the label
        # is swapped and a human is escalated to. Something is still owed
        # -- by a person, outside the machine -- and saying so is the whole
        # purpose of the state.
        #
        # This is asserted against the shipped fixture rather than a
        # hand-built machine because it is the fixture's own shape, and
        # because a check requiring terminal states to be accepting would
        # reject `session-relay` itself.
        m = parse(VALID)
        self.assertTrue(m.states["stalled"].terminal)
        self.assertFalse(m.states["stalled"].accepting)
        self.assertEqual(check_machine(m), [])

    def test_a_terminal_non_accepting_state_is_not_asked_to_reach_anything(self):
        # Directly, on a machine that is nothing but the abort: a terminal
        # non-accepting state can reach nothing at all, by definition, so
        # a reachability check that did not exempt it would report every
        # error state in every protocol as a defect.
        m = Machine(
            "abort-test", "v1", "x",
            {"role": "party"}, {"go", "give-up"}, None,
            "idle",
            {
                "idle": State("idle", holder="role", accepting=True),
                "aborted": State("aborted", terminal=True),
            },
            [
                Transition("idle", "go", "role", "idle", signal=True),
                Transition("idle", "give-up", "role", "aborted", signal=True,
                           effects=["escalate"]),
            ],
        )
        self.assertEqual(check_machine(m), [])

    def test_a_machine_with_no_cap_at_all_passes_every_check(self):
        # The case this change exists to permit, pinned so it cannot be
        # taken away again by accident: a protocol that declares no bound.
        # `cap` is absent, not zero and not a sentinel, and nothing here
        # reports it.
        m = Machine(
            "uncapped", "v1", "x",
            {"role": "party"}, {"ping"}, None,
            "idle",
            {"idle": State("idle", holder="role", accepting=True)},
            [Transition("idle", "ping", "role", "idle", signal=True)],
        )
        self.assertEqual(check_machine(m), [])

    def test_the_cap_check_is_skipped_entirely_when_cap_is_absent(self):
        # Not merely "an uncapped machine happens to pass": the machine
        # here is one that *would* fail the cap check for any cap under 2,
        # and with no cap declared there is nothing to compare against.
        m = _linear_machine(cap=None)
        self.assertEqual([p for p in check_machine(m) if "cap" in p], [])

    def test_a_machine_that_is_entirely_accepting_and_never_terminates_passes(self):
        # The gossip shape. Every state is accepting: at any moment it is
        # fine for the conversation to stop, and it is equally fine for
        # another message to arrive. No state is terminal, because nothing
        # ever makes a further message impossible. Cycle A rejected this
        # machine outright ("no state is terminal; the machine cannot
        # terminate") even though there is nothing wrong with it.
        m = Machine(
            "gossip", "v1", "x",
            {"peer": "session"}, {"rumour", "ack"}, None,
            "idle",
            {
                "idle": State("idle", holder="peer", accepting=True),
                "informed": State("informed", holder="peer", accepting=True),
            },
            [
                Transition("idle", "rumour", "peer", "informed", signal=True),
                Transition("informed", "rumour", "peer", "informed", signal=True),
                Transition("informed", "ack", "peer", "idle", signal=True),
            ],
        )
        problems = check_machine(m)
        self.assertEqual(problems, [])
        self.assertEqual([s for s in m.states.values() if s.terminal], [])

    def test_a_cap_too_small_for_the_shortest_run_to_an_accepting_state_is_reported(self):
        # The cap check re-targeted: the goal set is the accepting states,
        # not the terminal ones. Here `done` is accepting and *not*
        # terminal -- it has an outgoing transition -- so a check still
        # measuring to terminal states would find no goal at all and report
        # nothing, which is the failure this test exists to catch.
        m = Machine(
            "recap", "v1", "x",
            {"role": "party"}, {"a", "b", "c"}, 1,
            "start",
            {
                "start": State("start", holder="role"),
                "middle": State("middle", holder="role"),
                "done": State("done", holder="role", accepting=True),
            },
            [
                Transition("start", "a", "role", "middle", signal=True),
                Transition("middle", "b", "role", "done", signal=True),
                Transition("done", "c", "role", "start", signal=True),
            ],
        )
        problems = check_machine(m)
        cap_problems = [p for p in problems if "cap" in p]
        self.assertEqual(len(cap_problems), 1, problems)
        self.assertIn("2 signalling transitions", cap_problems[0])
        self.assertIn("accepting state", cap_problems[0])

    def test_local_moves_are_still_free_on_the_way_to_an_accepting_state(self):
        # Re-targeting the goal set must not have disturbed the 0-1 BFS
        # weighting underneath it: a `signal: false` edge still costs
        # nothing, so this three-transition run costs 1 and cap 1 accepts
        # it. Asserted against an accepting, non-terminal goal, which the
        # pre-change check could not have reached.
        m = Machine(
            "free-moves", "v1", "x",
            {"role": "party"}, {"a", "b", "c", "d"}, 1,
            "start",
            {
                "start": State("start", holder="role"),
                "middle": State("middle", holder="role"),
                "late": State("late", holder="role"),
                "done": State("done", holder="role", accepting=True),
            },
            [
                Transition("start", "a", "role", "middle", signal=False),
                Transition("middle", "b", "role", "late", signal=False),
                Transition("late", "c", "role", "done", signal=True),
                Transition("done", "d", "role", "start", signal=True),
            ],
        )
        self.assertEqual(check_machine(m), [])


if __name__ == "__main__":
    unittest.main()
