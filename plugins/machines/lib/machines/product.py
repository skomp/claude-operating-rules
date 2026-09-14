"""Whether two message-prefix patterns can both claim the same message.

A machine's `prefix` pattern does not have to match a whole message -- it
only has to match a *prefix* of one (see pattern.py's module docstring and
`compile_pattern`'s nullability check). So a compiled pattern `a` actually
claims the language `L(a).Sigma*`: everything `a` accepts, followed by
anything at all. Two installed machines collide exactly when

    L(a).Sigma*   inter  L(b).Sigma*  !=  {}

which is true iff some string one of them accepts is a prefix of some
string the other accepts. `session-relay:` and `session-relay:v1 ` collide
under this definition -- the first is a proper prefix of the second -- even
though they are not equal as strings. That is deliberately not the same
question as "are these two patterns equal", and testing for equality would
miss exactly the case (a versioned prefix shadowing its own root) most
likely to happen by accident.

This module knows nothing about protocols or machines; it only intersects
two `NFA` objects (Task 5's `pattern.py`) and answers a boolean. Task 7
decides what to do with that boolean at install time.

Method: build, for each NFA, the automaton for `L(pattern).Sigma*` by
adding a self-loop over the full codepoint range to every accepting state
(that is what lets the automaton keep consuming *any* further input once it
has already matched something in `L(pattern)`), then search the product of
the two augmented automata -- as pairs of epsilon-closed state sets -- for
a reachable pair that is accepting in both. If one exists, some string is
accepted by both `L(a).Sigma*` and `L(b).Sigma*`, so the two original
languages collide; if the search exhausts every reachable pair without
finding one, they don't.
"""

from .pattern import compile_pattern

# The full Unicode codepoint span, matching pattern.py's _FULL_SPAN. This is
# the range a `.` or negated class already uses, so an accepting state's
# Sigma* self-loop is exactly one more move of the same shape the compiler
# already produces elsewhere.
_FULL_SPAN = (0, 0x10FFFF)
_SIGMA = frozenset([_FULL_SPAN])


def ranges_intersect(x, y):
    """Whether charsets `x` and `y` (each a frozenset of inclusive
    (low, high) codepoint ranges) share at least one codepoint.

    Two moves out of a product state can be taken together only on the
    codepoints both charsets contain, so this is the primitive the product
    search steps on. Adjacency is not intersection: (1, 5) and (6, 9) share
    no codepoint even though they are contiguous, and must compare False --
    an off-by-one here (e.g. comparing `lo1 <= hi2 + 1`) would silently
    invent a collision between two patterns that don't actually overlap.
    Touching at a single codepoint, (1, 5) and (5, 9), must compare True.
    """
    for lo1, hi1 in x:
        for lo2, hi2 in y:
            if lo1 <= hi2 and lo2 <= hi1:
                return True
    return False


def _with_sigma_star_loops(nfa):
    """A copy of `nfa.moves` with an extra move on the full codepoint range
    from every accepting state back to itself, giving the automaton for
    `L(nfa).Sigma*` instead of `L(nfa)`.

    Deliberately does not touch `nfa` or its `moves`/`epsilon` dicts: those
    belong to the caller (and, via `compile_pattern`, may in principle be
    reused or cached), so mutating them in place here would corrupt the
    original NFA for anyone who compiled it -- silently, since Python dicts
    and lists mutate in place with no signal at the call site. Only the
    lists for accepting states are actually replaced (with a new list built
    via `+`, which never mutates the original); every other state's move
    list is shared unchanged with the source NFA, which is safe because
    this module never writes back into it.
    """
    augmented = dict(nfa.moves)
    for state in nfa.accept:
        augmented[state] = augmented[state] + [(_SIGMA, state)]
    return augmented


def patterns_collide(a, b):
    """Whether prefix patterns `a` and `b` can both claim the same message,
    i.e. whether `L(a).Sigma*` and `L(b).Sigma*` intersect.

    Raises PatternError (from pattern.py) if either pattern fails to parse
    or compile -- in particular if either is nullable, since a nullable
    pattern already claims every message and `compile_pattern` refuses to
    produce an NFA for it. That refusal happens before this function is
    reached, so `patterns_collide` never has to special-case an accepting
    start state; the emptiness check below (a product pair is accepting
    when *both* halves' closures meet their own accept set) already gives
    the right answer for that case too; it just cannot arise here.
    """
    nfa_a = compile_pattern(a)
    nfa_b = compile_pattern(b)
    moves_a = _with_sigma_star_loops(nfa_a)
    moves_b = _with_sigma_star_loops(nfa_b)

    start_a = frozenset(nfa_a.epsilon_closure({nfa_a.start}))
    start_b = frozenset(nfa_b.epsilon_closure({nfa_b.start}))

    visited = set()
    stack = [(start_a, start_b)]
    while stack:
        closure_a, closure_b = stack.pop()
        pair = (closure_a, closure_b)
        if pair in visited:
            continue
        visited.add(pair)

        if (closure_a & nfa_a.accept) and (closure_b & nfa_b.accept):
            return True

        moves_out_a = [
            (charset, target)
            for state in closure_a
            for charset, target in moves_a[state]
        ]
        moves_out_b = [
            (charset, target)
            for state in closure_b
            for charset, target in moves_b[state]
        ]

        for charset_a, target_a in moves_out_a:
            for charset_b, target_b in moves_out_b:
                if not ranges_intersect(charset_a, charset_b):
                    continue
                next_a = frozenset(nfa_a.epsilon_closure({target_a}))
                next_b = frozenset(nfa_b.epsilon_closure({target_b}))
                next_pair = (next_a, next_b)
                if next_pair not in visited:
                    stack.append(next_pair)

    # Finitely many pairs of epsilon-closed state sets exist over two
    # finite automata, and `visited` guarantees each is expanded at most
    # once, so this loop is guaranteed to terminate rather than merely
    # expected to.
    return False
