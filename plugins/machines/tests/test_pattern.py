import unittest

from machines.pattern import (
    parse_pattern,
    compile_pattern,
    PatternError,
    Lit,
    Cat,
    Alt,
    Star,
    Empty,
    NFA,
    _MAX_NFA_STATES,
    _MAX_GROUP_DEPTH,
    _complement,
    _merge_ranges,
)


def lit(*chars):
    """A Lit over exactly the given single characters, for compact expected ASTs."""
    return Lit(frozenset((ord(c), ord(c)) for c in chars))


class TestParsePattern(unittest.TestCase):
    # --- from the brief ---

    def test_accepts_a_plain_literal(self):
        self.assertIsNotNone(parse_pattern("session-relay:v1 "))

    def test_accepts_the_documented_example(self):
        self.assertIsNotNone(parse_pattern('received from: [^ ]*, type: "force"'))

    def test_accepts_alternation_grouping_and_repetition(self):
        for src in ("a|b", "(ab)*", "a+b?", "[a-z0-9]+", "."):
            self.assertIsNotNone(parse_pattern(src), src)

    def test_rejects_a_backreference(self):
        with self.assertRaises(PatternError):
            parse_pattern(r"(a)\1")

    def test_rejects_lookaround(self):
        with self.assertRaises(PatternError):
            parse_pattern("(?=a)b")

    def test_rejects_a_counted_repetition(self):
        with self.assertRaises(PatternError):
            parse_pattern("a{2,3}")

    def test_rejects_an_unclosed_group(self):
        with self.assertRaises(PatternError):
            parse_pattern("(ab")

    def test_rejects_an_unclosed_class(self):
        with self.assertRaises(PatternError):
            parse_pattern("[a-z")

    def test_escaped_metacharacter_is_a_literal(self):
        self.assertIsNotNone(parse_pattern(r"a\*b"))

    # --- structural checks: verify meaning, not just "it didn't crash" ---

    def test_plain_literal_compiles_to_a_cat_of_lits(self):
        self.assertEqual(parse_pattern("ab"), Cat(lit("a"), lit("b")))

    def test_alternation_compiles_to_alt(self):
        self.assertEqual(parse_pattern("a|b"), Alt(lit("a"), lit("b")))

    def test_star_compiles_to_star(self):
        self.assertEqual(parse_pattern("a*"), Star(lit("a")))

    def test_plus_desugars_to_cat_of_x_and_star_x(self):
        # Point 4: `+` must desugar to Cat(x, Star(x)), not a sixth node type.
        self.assertEqual(parse_pattern("a+"), Cat(lit("a"), Star(lit("a"))))

    def test_question_desugars_to_alt_of_x_and_empty(self):
        # Point 4: `?` must desugar to Alt(x, Empty()).
        self.assertEqual(parse_pattern("a?"), Alt(lit("a"), Empty()))

    def test_dot_matches_the_entire_codepoint_span_including_newline(self):
        # Point 3: '.' must include newline -- a prefix pattern runs against
        # a message body, not a line.
        self.assertEqual(parse_pattern("."), Lit(frozenset([(0, 0x10FFFF)])))

    def test_group_is_transparent_to_the_ast(self):
        self.assertEqual(parse_pattern("(a)"), lit("a"))

    def test_escaped_metacharacter_produces_the_literal_character(self):
        self.assertEqual(parse_pattern(r"a\*b"), Cat(Cat(lit("a"), lit("*")), lit("b")))

    def test_class_is_a_lit_of_its_ranges(self):
        self.assertEqual(parse_pattern("[a-c]"), Lit(frozenset([(ord("a"), ord("c"))])))

    def test_class_merges_overlapping_and_adjacent_items(self):
        # [a-cb-d] -> a-c and b-d overlap -> should collapse to a single a-d range.
        self.assertEqual(parse_pattern("[a-cb-d]"), Lit(frozenset([(ord("a"), ord("d"))])))

    def test_negated_class_is_the_complement_over_the_full_span(self):
        node = parse_pattern("[^ ]")
        space = ord(" ")
        expected = frozenset([(0, space - 1), (space + 1, 0x10FFFF)])
        self.assertEqual(node, Lit(expected))

    def test_rejects_an_empty_character_class(self):
        # class := '[' '^'? item+ ']' -- item+ requires at least one item.
        with self.assertRaises(PatternError):
            parse_pattern("[]")

    def test_rejects_an_empty_negated_character_class(self):
        with self.assertRaises(PatternError):
            parse_pattern("[^]")

    # --- decision 2: reject the syntactically empty pattern / branch ---
    #
    # A prefix pattern that can match the empty string means the machine
    # claims every message -- it collides with every other installed
    # machine while every other check still passes. That failure must be
    # silent nowhere, so it is caught here, at parse time, for the two
    # syntactic forms that are visible without compiling anything.
    #
    # The general form (a*, a? at top level are also nullable) needs the
    # compiled NFA, so it belongs to compile_pattern, not to this parser
    # -- see the module docstring in pattern.py.

    def test_rejects_the_empty_pattern(self):
        with self.assertRaises(PatternError):
            parse_pattern("")

    def test_rejects_an_empty_trailing_alternation_branch(self):
        with self.assertRaises(PatternError):
            parse_pattern("a|")

    def test_rejects_an_empty_leading_alternation_branch(self):
        with self.assertRaises(PatternError):
            parse_pattern("|a")

    def test_rejects_an_empty_middle_alternation_branch(self):
        with self.assertRaises(PatternError):
            parse_pattern("a||b")

    def test_rejects_an_empty_branch_inside_a_group(self):
        with self.assertRaises(PatternError):
            parse_pattern("(a|)b")

    # --- decision 2: named rejections, not a generic "bad escape" ---

    def test_backreference_message_names_backreferences(self):
        with self.assertRaisesRegex(PatternError, "(?i)backreference"):
            parse_pattern(r"(a)\1")

    def test_lookaround_message_names_extended_group_syntax(self):
        # CORRECTION (fix round 1): the brief's decision 2 said to name
        # "lookaround", but '(?' also opens named and non-capturing groups,
        # which aren't lookaround at all -- the message names what's true
        # of the whole family instead. See pattern.py's _parse_group.
        with self.assertRaisesRegex(PatternError, "(?i)extended group"):
            parse_pattern("(?=a)b")

    def test_negative_lookaround_is_also_rejected_and_named(self):
        with self.assertRaisesRegex(PatternError, "(?i)extended group"):
            parse_pattern("(?!a)b")

    def test_named_group_is_rejected_via_the_same_extended_group_path(self):
        # (?P<name>...) also starts with '(?' -- there is no separate
        # "named group" branch in this grammar, it is caught by the same
        # check that rejects lookaround, and gets the same message.
        with self.assertRaisesRegex(PatternError, "(?i)extended group"):
            parse_pattern("(?P<x>a)")

    def test_non_capturing_group_is_also_rejected_via_the_same_path(self):
        with self.assertRaisesRegex(PatternError, "(?i)extended group"):
            parse_pattern("(?:a)")

    # --- decision 2, fix round 1: the narrowed brace rule ---
    #
    # Finding 1: reserving '{' wholesale deleted a legitimate character
    # from the language -- there was no way, escaped or not, to match a
    # literal brace, and a JSON-shaped prefix is a plausible thing to want
    # to match. '{' is rejected only when it opens something shaped like a
    # genuine counted repetition (\d+(,\d*)?\} immediately after it); a
    # bare '{' that doesn't have that shape is an ordinary literal.

    # test_rejects_a_counted_repetition (in "from the brief" above) already
    # covers "a{2,3}" -- add the bound-free form here, since {n} alone
    # (no comma) is a distinct branch of _COUNTED_REPETITION_RE.

    def test_rejects_a_counted_repetition_without_an_upper_bound(self):
        with self.assertRaises(PatternError):
            parse_pattern("a{2}")

    def test_json_shaped_brace_literal_parses(self):
        # A '{' not followed by digits+'}' doesn't open a counted
        # repetition -- it's just a character in the message prefix.
        self.assertIsNotNone(parse_pattern('{"type":"force"}'))

    def test_brace_not_shaped_like_a_counted_repetition_is_a_literal(self):
        self.assertIsNotNone(parse_pattern("a{oops}"))

    def test_escaped_braces_are_literals(self):
        self.assertEqual(
            parse_pattern(r"\{a\}"), Cat(Cat(lit("{"), lit("a")), lit("}"))
        )


class TestComplementHelper(unittest.TestCase):
    """Point 1: character-class complement is the defect most likely to
    survive into `patterns_collide`, where it becomes a wrong collision
    verdict rather than a visible crash. Test it directly, not just
    through parse_pattern.
    """

    FULL = (0, 0x10FFFF)

    def test_complement_of_the_whole_span_is_empty(self):
        self.assertEqual(_complement([self.FULL]), frozenset())

    def test_complement_of_empty_is_the_whole_span(self):
        self.assertEqual(_complement([]), frozenset([self.FULL]))

    def test_complement_of_codepoint_zero(self):
        self.assertEqual(_complement([(0, 0)]), frozenset([(1, 0x10FFFF)]))

    def test_complement_of_a_class_ending_at_the_top_codepoint(self):
        self.assertEqual(
            _complement([(0x100000, 0x10FFFF)]),
            frozenset([(0, 0x0FFFFF)]),
        )

    def test_complement_of_a_middle_range(self):
        self.assertEqual(
            _complement([(10, 20)]),
            frozenset([(0, 9), (21, 0x10FFFF)]),
        )

    def test_complement_is_its_own_inverse(self):
        ranges = [(5, 10), (20, 30)]
        self.assertEqual(
            _complement(_complement(ranges)), frozenset(_merge_ranges(ranges))
        )


class TestMergeRangesHelper(unittest.TestCase):
    def test_adjacent_ranges_merge(self):
        # 0-5 and 6-10 touch with no gap -- must merge into one range.
        self.assertEqual(_merge_ranges([(0, 5), (6, 10)]), [(0, 10)])

    def test_overlapping_ranges_merge(self):
        self.assertEqual(_merge_ranges([(0, 10), (5, 15)]), [(0, 15)])

    def test_non_adjacent_ranges_stay_separate(self):
        self.assertEqual(_merge_ranges([(0, 5), (7, 10)]), [(0, 5), (7, 10)])

    def test_unsorted_input_is_sorted_first(self):
        self.assertEqual(_merge_ranges([(20, 25), (0, 5)]), [(0, 5), (20, 25)])

    def test_empty_input(self):
        self.assertEqual(_merge_ranges([]), [])


class TestCompilePattern(unittest.TestCase):
    """`accepts` matches the whole string -- the prefix semantics
    (L(a).Sigma*) belong to `product.py`, not to this module; see
    NFA.accepts's docstring.
    """

    def check(self, src, yes, no):
        nfa = compile_pattern(src)
        for s in yes:
            self.assertTrue(nfa.accepts(s), "%r should match %r" % (src, s))
        for s in no:
            self.assertFalse(nfa.accepts(s), "%r should not match %r" % (src, s))

    def test_literal(self):
        self.check("abc", ["abc"], ["ab", "abcd", "", "abd"])

    def test_alternation(self):
        self.check("a|bc", ["a", "bc"], ["b", "abc", ""])

    def test_star_matches_zero_or_more(self):
        self.check("ab*", ["a", "ab", "abbb"], ["b", "", "ba"])

    def test_plus_requires_one(self):
        self.check("ab+", ["ab", "abbb"], ["a", "", "b"])

    def test_question_is_zero_or_one(self):
        self.check("ab?", ["a", "ab"], ["abb", ""])

    def test_class_and_negated_class(self):
        self.check("[a-c]", ["a", "b", "c"], ["d", "", "aa"])
        self.check("[^a-c]", ["d", "z"], ["a", "b", ""])

    def test_dot_matches_one_of_anything(self):
        self.check(".", ["a", "Z", "9"], ["", "ab"])

    def test_the_documented_example(self):
        self.check('received from: [^ ]*, type: "force"',
                   ['received from: alpha, type: "force"',
                    'received from: , type: "force"'],
                   ['received from: two words, type: "force"',
                    'received from: alpha, type: "soft"'])

    # --- the node-sharing defect ---
    #
    # The parser desugars `x+` to Cat(x, Star(x)) using the *same* AST
    # object in both positions (_parse_rep). A compiler that
    # memoises Thompson fragments by node identity -- or by id(), or by
    # relying on Node.__eq__ making structurally-equal nodes interchangeable
    # -- would wire both occurrences of `x` to a single shared fragment
    # instead of two independent ones. (ab)+ against "abab" is the
    # smallest shape that can tell the two constructions apart: a
    # single-state `x` (e.g. plain "a+") happens to survive naive sharing
    # by accident, but a multi-state `x` like "(ab)" does not.

    def test_plus_of_a_multistate_group_matches_repetitions_of_the_group(self):
        self.check("(ab)+", ["ab", "abab", "ababab"],
                    ["", "a", "aba", "abb", "abba"])

    def test_question_of_a_multistate_group_is_independent_per_branch(self):
        # (ab)?(ab) desugars `?` to Alt(x, Empty()) with x = (ab) appearing
        # once there and again as the literal second (ab) -- same shape of
        # risk as the `+` case, via a different desugaring.
        self.check("(ab)?(ab)", ["ab", "abab"], ["", "a", "aba"])

    # --- the general nullability check (point 2 in the dispatch) ---
    #
    # The parser only rejects the two *syntactic* forms of an empty match
    # ("" and an empty alternation branch, both in _parse_cat). `a*`, `a?`
    # and `(ab)*` are all nullable at top level but parse fine --
    # compile_pattern must catch them by inspecting the compiled NFA's
    # epsilon-closure of its start state against its accept set. A pattern that can match empty
    # means L(a).Sigma* becomes Sigma*: it would collide with every other
    # installed machine while every other check still passes.

    def test_rejects_star_at_top_level(self):
        with self.assertRaises(PatternError):
            compile_pattern("a*")

    def test_rejects_question_at_top_level(self):
        with self.assertRaises(PatternError):
            compile_pattern("a?")

    def test_rejects_an_empty_branch_via_trailing_alternation_in_a_group(self):
        # CORRECTION: this comment used to claim `(a|)` is caught by the
        # compiled nullability check. It is not. `_parse_cat` reaches the
        # `)` having consumed zero reps and raises "empty alternation
        # branch at position 3" before any NFA is built -- the same
        # syntactic check that rejects `a|`, just one nesting level in.
        # The test is still worth keeping (an empty branch inside a group
        # must be rejected however it is reached), but it is evidence
        # about `_parse_cat`, not about compile_pattern, and a reader who
        # believed the old comment would think the nullability check had
        # coverage it does not have. `a*`, `a?` and `(ab)*` above are that
        # check's real coverage.
        with self.assertRaises(PatternError) as ctx:
            compile_pattern("(a|)")
        self.assertIn("empty alternation branch", str(ctx.exception))

    def test_rejects_a_nullable_group_under_star(self):
        with self.assertRaises(PatternError):
            compile_pattern("(ab)*")

    def test_accepts_a_non_nullable_pattern_containing_a_nested_star(self):
        # Sanity check on the above: nullability is about the *whole*
        # pattern, not "does it contain a Star anywhere".
        self.assertIsNotNone(compile_pattern("a(b*)c"))

    # --- the NFA contract `product.py` depends on ---

    def test_nfa_exposes_the_documented_contract_shape(self):
        nfa = compile_pattern("ab")
        self.assertIsInstance(nfa, NFA)
        self.assertIsInstance(nfa.start, int)
        self.assertIsInstance(nfa.accept, set)
        self.assertIsInstance(nfa.moves, dict)
        self.assertIsInstance(nfa.epsilon, dict)
        self.assertIn(nfa.start, nfa.moves)
        for state, edges in nfa.moves.items():
            self.assertIsInstance(state, int)
            for charset, target in edges:
                self.assertIsInstance(charset, frozenset)
                for lo, hi in charset:
                    self.assertIsInstance(lo, int)
                    self.assertIsInstance(hi, int)
                self.assertIsInstance(target, int)
        for state, targets in nfa.epsilon.items():
            self.assertIsInstance(state, int)
            self.assertIsInstance(targets, set)


class TestStateCeiling(unittest.TestCase):
    """Thompson construction here allocates fresh states per *occurrence*
    of a node, which is required for correctness (see the node-sharing
    tests above) and is also what makes nested repetition exponential:
    `x+` compiles Cat(x, Star(x)) with two independent copies of `x`, so
    each further level of `+` roughly doubles the state count.

    Measured on this compiler with the ceiling lifted: the 52-character
    pattern `a` wrapped in `+` seventeen times compiles to 524,286 states
    in 0.80s, and twenty-two levels extrapolates to about 8.4 million. No
    message prefix needs that, and a checker whose job is to name what is
    wrong must say so rather than allocate until the process dies.
    """

    def nested_plus(self, depth):
        src = "a"
        for _ in range(depth):
            src = "(%s)+" % src
        return src

    def test_a_deeply_nested_plus_is_rejected_by_name(self):
        with self.assertRaises(PatternError) as ctx:
            compile_pattern(self.nested_plus(17))
        self.assertIn(str(_MAX_NFA_STATES), str(ctx.exception))

    def test_the_rejection_is_immediate_not_after_the_explosion(self):
        # The point of a ceiling is that it stops allocation, not that it
        # reports afterwards. Twenty-five levels is ~67 million states
        # unbounded; this must return in the time 10,000 states take.
        import time
        start = time.time()
        with self.assertRaises(PatternError):
            compile_pattern(self.nested_plus(25))
        self.assertLess(time.time() - start, 1.0)

    def test_an_ordinary_message_prefix_is_nowhere_near_the_ceiling(self):
        # The ceiling must not be a tax on real declarations. A literal
        # prefix costs two states per character, so the shipped fixture's
        # prefix uses 34 of 10,000.
        nfa = compile_pattern("session-relay:v1 ")
        self.assertLess(len(nfa.moves), _MAX_NFA_STATES // 100)

    def test_a_moderate_nested_plus_still_compiles(self):
        # And it must not reject repetition as such: five levels is 126
        # states, well inside the limit.
        self.assertIsNotNone(compile_pattern(self.nested_plus(5)))


class TestGroupNestingDepth(unittest.TestCase):
    """`(...)` nesting is the one recursive production in this grammar
    (see `_MAX_GROUP_DEPTH`'s comment in pattern.py): a chain of literals,
    `|` branches, or `*`/`+`/`?` suffixes is consumed in a loop and never
    deepens the parser's call stack, but each nested group recurses back
    into `_parse_alt`, in both the parser and (via the resulting AST
    shape) the Thompson compiler.

    Found end to end through the shipped CLI: `'(' * 199 + 'a' + ')' *
    199` is 399 characters -- one under declaration.py's 400-character
    length guard, which bounds a different route (a long flat
    concatenation/alternation chain) and does nothing for nesting depth.
    That prefix used to reach `compile_pattern` and blow the stack with a
    raw `RecursionError`, reported through `bin/machines-check` as exit 1
    with a Python traceback instead of a named problem.
    """

    def nested_group(self, depth):
        return "(" * depth + "a" + ")" * depth

    def test_a_199_deep_prefix_is_rejected_by_name(self):
        # The reviewer's reproduction, verbatim: 399 characters, under the
        # 400-character length guard, so that guard cannot be why this is
        # rejected -- only the nesting-depth guard can be.
        prefix = "(" * 199 + "a" + ")" * 199
        self.assertEqual(len(prefix), 399)
        with self.assertRaises(PatternError) as ctx:
            compile_pattern(prefix)
        message = str(ctx.exception)
        self.assertIn("nesting", message)
        self.assertIn(str(_MAX_GROUP_DEPTH), message)

    def test_a_60_deep_prefix_is_accepted(self):
        # Under the new guard -- must not reject a legitimate pattern just
        # because a guard now exists.
        nfa = compile_pattern(self.nested_group(60))
        self.assertIsNotNone(nfa)

    def test_the_rejection_is_immediate_not_after_a_stack_dive(self):
        # Same discipline as TestStateCeiling's timing test: the guard
        # must stop the parser at the boundary, not let it recurse close
        # to the limit and merely catch the resulting RecursionError.
        import time
        start = time.time()
        with self.assertRaises(PatternError):
            compile_pattern(self.nested_group(199))
        self.assertLess(time.time() - start, 1.0)

    def test_exactly_the_limit_is_accepted_not_off_by_one_rejected(self):
        self.assertIsNotNone(compile_pattern(self.nested_group(_MAX_GROUP_DEPTH)))

    def test_one_past_the_limit_is_rejected(self):
        with self.assertRaises(PatternError):
            compile_pattern(self.nested_group(_MAX_GROUP_DEPTH + 1))


if __name__ == "__main__":
    unittest.main()
