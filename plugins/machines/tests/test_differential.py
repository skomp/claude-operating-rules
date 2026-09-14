"""`patterns_collide` against a brute-force oracle, over random pattern pairs.

`patterns_collide` decides the installer's central guarantee -- that two
machines cannot both claim the same inbound message -- and it decides it by
searching the product of two epsilon-closed automata. A subtle error there
does not crash. It returns a confident boolean that happens to be wrong,
install-time reports "no collisions", and two machines that both claim a
message are both enabled. There is no later symptom that points back here.

So this test decides the same question a second time, by a method that
shares no code with the first: enumerate strings, ask each compiled NFA
which ones it accepts, and look for one string that both patterns claim.
Agreement over 1,770 random pairs is worth more than any hand-written case,
because the pairs were not chosen by someone who already believed the
implementation was right.

Three properties make this a test rather than a demonstration:

**Seeded.** `random.Random(_SEED)` with a fixed seed, so the 60 patterns
and the 1,770 pairs are the same on every run, on every machine, forever. A
randomised test that draws fresh input each run is a test that fails for
somebody else and passes for you.

**Bounded.** Three-letter alphabet, pattern nesting at most three deep,
strings at most five characters. The whole file runs in about 0.2s.

**Alphabet-closed, which is what makes the oracle exact and not merely
indicative.** Every generated charset is either a subset of `{a, b}` or the
complement of one. The intersection of any collection of those is non-empty
if and only if it contains `a`, `b`, or `c`: if any member is a positive
subset the intersection lies inside `{a, b}`, and if they are all
complements of subsets of `{a, b}` then `c` is in every one of them. That
is why the universe is `abc` and why no pattern ever mentions `c`: without
the spare letter, `[^a]` and `[^b]` would genuinely collide (on `c`, and on
a million other codepoints) while the oracle, seeing only `a` and `b`,
would report no overlap and fail the test for a reason that is not a bug.

The one thing the bound cannot make exact is length. The oracle only ever
looks at strings up to `_MAX_LEN`, so it can miss a collision whose only
witness is longer -- see `test_the_oracle_and_the_implementation_agree`,
which says so in its own failure message and asymmetrically, because the
two directions of disagreement do not mean the same thing.
"""

import itertools
import random
import unittest

from machines.pattern import PatternError, compile_pattern
from machines.product import patterns_collide

_SEED = 20260914
_PATTERN_COUNT = 60          # -> 1,770 unordered pairs
_MAX_LEN = 5                 # -> 364 strings over `abc`
_MAX_DEPTH = 3

# `a` and `b` are the letters patterns are written from; `c` is never
# written, and exists only as the witness that makes every intersection of
# negated classes non-empty inside the universe. See the module docstring.
_ALPHABET = "abc"

_ATOMS = ["a", "b", "[ab]", "[^a]", "[^b]", "[^ab]", "."]

_UNIVERSE = ["".join(letters)
             for length in range(_MAX_LEN + 1)
             for letters in itertools.product(_ALPHABET, repeat=length)]


def _random_pattern(rng, depth):
    """One random pattern source string, at most `depth` combinators deep.

    Covers every combinator in the grammar that takes a sub-pattern:
    concatenation, alternation, `*`, `+` and `?`. Not every draw is a
    legal prefix pattern -- `(a)*` is nullable and `compile_pattern`
    refuses it -- and the caller discards those.
    """
    if depth <= 0:
        return rng.choice(_ATOMS)
    choice = rng.randrange(6)
    if choice == 0:
        return _random_pattern(rng, depth - 1) + _random_pattern(rng, depth - 1)
    if choice == 1:
        return "(%s|%s)" % (_random_pattern(rng, depth - 1),
                            _random_pattern(rng, depth - 1))
    if choice == 2:
        return "(%s)*" % _random_pattern(rng, depth - 1)
    if choice == 3:
        return "(%s)+" % _random_pattern(rng, depth - 1)
    if choice == 4:
        return "(%s)?" % _random_pattern(rng, depth - 1)
    return rng.choice(_ATOMS)


def _sample_patterns():
    """`_PATTERN_COUNT` distinct patterns that compile, drawn from `_SEED`."""
    rng = random.Random(_SEED)
    patterns = []
    seen = set()
    while len(patterns) < _PATTERN_COUNT:
        src = _random_pattern(rng, rng.randrange(1, _MAX_DEPTH + 1))
        if src in seen:
            continue
        try:
            nfa = compile_pattern(src)
        except PatternError:
            # Nullable, or over the state ceiling. Both are refused before
            # `patterns_collide` is ever reached, so neither belongs here.
            continue
        seen.add(src)
        patterns.append((src, nfa))
    return patterns


def _claimed_strings(nfa):
    """Every string in the universe this pattern *claims* as a message.

    A prefix pattern claims `L(pattern).Sigma*`: not the strings the NFA
    accepts, but every string with a prefix the NFA accepts. Built by
    enumeration and whole-string matching only -- `NFA.accepts` and
    `str` slicing -- so it shares nothing with the product construction
    under test beyond the compiled automaton itself.
    """
    accepted = set(w for w in _UNIVERSE if nfa.accepts(w))
    return frozenset(w for w in _UNIVERSE
                     if any(w[:i] in accepted for i in range(len(w) + 1)))


class TestPatternsCollideAgainstABruteForceOracle(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.patterns = _sample_patterns()
        cls.claimed = dict((src, _claimed_strings(nfa))
                           for src, nfa in cls.patterns)

    def test_the_sample_is_the_size_and_shape_this_test_claims(self):
        # The evidence is "1,770 pairs, every combinator exercised". If a
        # future edit quietly shrank the sample, or the generator stopped
        # producing repetition, every other assertion below would still
        # pass while proving much less.
        self.assertEqual(len(self.patterns), _PATTERN_COUNT)
        sources = [src for src, _ in self.patterns]
        self.assertEqual(len(set(sources)), _PATTERN_COUNT)
        for combinator in ("|", "*", "+", "?", "["):
            self.assertTrue(any(combinator in src for src in sources),
                            "no sampled pattern uses %r" % combinator)

    def test_the_oracle_and_the_implementation_agree(self):
        pairs = 0
        for (a, _), (b, _) in itertools.combinations(self.patterns, 2):
            pairs += 1
            shared = self.claimed[a] & self.claimed[b]
            actual = patterns_collide(a, b)
            if shared and not actual:
                # Unambiguous: a concrete string both patterns claim, and
                # `patterns_collide` said they cannot both claim one. The
                # length bound cannot explain this direction.
                self.fail(
                    "patterns_collide(%r, %r) is False, but both claim %r"
                    % (a, b, sorted(shared)[0]))
            if actual and not shared:
                # Ambiguous, and the failure message has to say so: either
                # `patterns_collide` invented a collision, or the two
                # patterns really do collide and every witness is longer
                # than _MAX_LEN characters, which the oracle cannot see.
                # Raise _MAX_LEN to tell the two apart before assuming a
                # bug. With _SEED, this has never fired.
                self.fail(
                    "patterns_collide(%r, %r) is True, but no string of up "
                    "to %d characters over %r is claimed by both. Either "
                    "that is a false collision, or the witness is longer "
                    "than the oracle's bound -- raise _MAX_LEN to tell "
                    "them apart." % (a, b, _MAX_LEN, _ALPHABET))
        self.assertEqual(pairs, _PATTERN_COUNT * (_PATTERN_COUNT - 1) // 2)

    def test_every_pattern_collides_with_itself(self):
        # A sanity check on the oracle rather than on the implementation:
        # a pattern that claims anything at all claims a string in common
        # with itself, so an empty `claimed` set would silently make the
        # main test vacuous for that pattern.
        for src, _ in self.patterns:
            self.assertTrue(self.claimed[src],
                            "%r claims no string within the bound" % src)
            self.assertTrue(patterns_collide(src, src), src)


if __name__ == "__main__":
    unittest.main()
