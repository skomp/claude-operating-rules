import copy
import unittest

from machines.pattern import compile_pattern
from machines.product import patterns_collide, ranges_intersect, _with_sigma_star_loops


class TestRangesIntersect(unittest.TestCase):
    def test_overlapping(self):
        self.assertTrue(ranges_intersect(frozenset([(1, 5)]), frozenset([(3, 9)])))

    def test_adjacent_but_disjoint(self):
        # (1,5) and (6,9) share no codepoint. An off-by-one here (treating
        # the boundary as inclusive of the gap) would wrongly report True
        # and invent a collision that doesn't exist.
        self.assertFalse(ranges_intersect(frozenset([(1, 5)]), frozenset([(6, 9)])))

    def test_touching_at_one_codepoint(self):
        # (1,5) and (5,9) share exactly codepoint 5.
        self.assertTrue(ranges_intersect(frozenset([(1, 5)]), frozenset([(5, 9)])))

    def test_one_range_wholly_inside_another(self):
        self.assertTrue(ranges_intersect(frozenset([(1, 100)]), frozenset([(40, 50)])))

    def test_disjoint_single_ranges(self):
        self.assertFalse(ranges_intersect(frozenset([(1, 5)]), frozenset([(100, 200)])))

    def test_multi_range_only_one_pair_overlaps(self):
        x = frozenset([(1, 5), (50, 60), (1000, 1010)])
        y = frozenset([(6, 9), (58, 65), (2000, 2010)])
        # Only (50,60) vs (58,65) overlaps; every other pair is disjoint or
        # merely adjacent.
        self.assertTrue(ranges_intersect(x, y))

    def test_multi_range_no_pair_overlaps(self):
        x = frozenset([(1, 5), (50, 60)])
        y = frozenset([(6, 9), (61, 70)])
        self.assertFalse(ranges_intersect(x, y))

    def test_empty_charset_never_intersects(self):
        self.assertFalse(ranges_intersect(frozenset(), frozenset([(1, 5)])))
        self.assertFalse(ranges_intersect(frozenset([(1, 5)]), frozenset()))


class TestPatternsCollide(unittest.TestCase):
    def test_identical_patterns_collide(self):
        self.assertTrue(patterns_collide("abc", "abc"))

    def test_disjoint_literals_do_not_collide(self):
        self.assertFalse(patterns_collide("abc", "xyz"))

    def test_a_proper_prefix_collides(self):
        self.assertTrue(patterns_collide("session-relay:", "session-relay:v1 "))

    def test_disjoint_classes_do_not_collide(self):
        self.assertFalse(patterns_collide("[a-c]x", "[d-f]x"))

    def test_overlapping_classes_collide(self):
        self.assertTrue(patterns_collide("[a-d]x", "[c-f]x"))

    def test_star_can_reach_the_other_pattern(self):
        self.assertTrue(patterns_collide("a*b", "aab"))

    def test_alternation_collides_when_one_branch_does(self):
        self.assertTrue(patterns_collide("foo|bar", "bar"))
        self.assertFalse(patterns_collide("foo|bar", "baz"))

    def test_two_real_looking_protocol_prefixes_do_not_collide(self):
        self.assertFalse(patterns_collide("session-relay:v1 ", "machines:v1 "))

    def test_collision_is_symmetric(self):
        # assertEqual alone would also pass if both directions were wrongly
        # False, so pin down the actual truth value in both directions.
        self.assertTrue(patterns_collide("session-relay:", "session-relay:v1 "))
        self.assertTrue(patterns_collide("session-relay:v1 ", "session-relay:"))

        # A second pair with very different shapes, where the only witness
        # ("cb") exists purely through the Sigma* extension rather than
        # through any literal text the two patterns share: L(".*b") claims
        # any string containing a "b"; L("c").Sigma* claims any string
        # starting with "c". "cb" is in both.
        self.assertTrue(patterns_collide(".*b", "c"))
        self.assertTrue(patterns_collide("c", ".*b"))

    def test_a_pattern_always_collides_with_itself(self):
        for src in ("a", "a*b", "[a-c]x", "foo|bar", "session-relay:v1 "):
            self.assertTrue(patterns_collide(src, src), src)

    def test_negated_class_does_not_collide_with_the_char_it_excludes(self):
        # [^a]x compiles to a Lit with a multi-range charset (the complement
        # of 'a' within the full codepoint span, split around it), which
        # ranges_intersect's hand-built multi-range tests never exercise
        # end-to-end. "ax" starts with the excluded 'a', so no overlap.
        self.assertFalse(patterns_collide("[^a]x", "ax"))

    def test_negated_class_collides_with_a_char_it_does_not_exclude(self):
        self.assertTrue(patterns_collide("[^a]x", "bx"))


class TestNoMutation(unittest.TestCase):
    """Protects the non-mutation invariant _with_sigma_star_loops relies
    on: it must build a new moves dict rather than editing the source
    NFA's moves/epsilon in place. Nothing else in this suite would catch a
    regression to in-place append -- all 18-plus tests above would still
    pass, since they only ever compile fresh NFAs and never inspect the
    same NFA object before and after augmentation. This test is the one
    that would fail if product.py:80 changed from rebuilding a list to
    mutating it -- confirmed by hand: temporarily replacing the rebuild
    with `augmented[state].append((_SIGMA, state))` makes this test fail
    (see the fix-round report for the exact command and output) while
    every other test in this file keeps passing.
    """

    def test_with_sigma_star_loops_does_not_mutate_the_source_nfa(self):
        nfa = compile_pattern("a*b|[c-e]+")
        moves_before = copy.deepcopy(nfa.moves)
        epsilon_before = copy.deepcopy(nfa.epsilon)

        _with_sigma_star_loops(nfa)

        self.assertEqual(nfa.moves, moves_before)
        self.assertEqual(nfa.epsilon, epsilon_before)


if __name__ == "__main__":
    unittest.main()
