"""The restricted prefix pattern language.

A machine's `prefix` (see SCHEMA.md) is not a literal string but a pattern in
a deliberately small language: literals, `.`, character classes, grouping,
alternation, and `*`/`+`/`?` repetition. Nothing else. In particular: no
backreferences, no lookaround, no anchors, no `{n,m}` counted repetition, no
named groups, no shorthand classes.

The restriction exists because the installer's central guarantee -- that no
two installed machines can claim the same message -- is decided by
intersecting two compiled automata (Task 6). That only works if every prefix
pattern is a *regular* language. A backreference (`(a)\\1`) or lookaround
is not regular; a pattern containing one could be accepted here, sail through
every other check, and the guarantee would silently stop holding for that
one machine. Parse time is the only place this can be caught, so it is
caught here, loudly, by name, rather than surfacing later as a wrong
collision verdict.

This module knows nothing about protocols, machines, or messages -- it is a
standalone grammar-to-AST parser, tested as one. It is Task 5's job to
compile the AST this module produces into an NFA, and Task 6's job to
intersect two of those NFAs.

Grammar::

    pattern := alt
    alt     := cat ('|' cat)*
    cat     := rep*
    rep     := atom ('*' | '+' | '?')?
    atom    := literal | '.' | class | '(' alt ')'
    class   := '[' '^'? item+ ']'
    item    := char '-' char | char
    literal := any char except | * + ? ( ) [ ] . \\  -- or '\\' followed by
               one of those

One deliberate departure from that grammar as written: the brief's prose
says plainly "no {n,m}" and requires `a{2,3}` to be rejected, but the
literal-exclusion list above does not name `{`. Taken fully literally, the
grammar would accept `{` as an ordinary character and parse `a{2,3}` as six
concatenated literals, which contradicts the required rejection test.

CORRECTION (fix round 1): the first version of this fix reserved `{`
wholesale -- rejecting every bare `{` and every `\{` escape, with no way to
match a literal brace at all. That went wider than the defect: "no counted
repetition" is not "no brace character", and a JSON-shaped prefix like
`{"type":"force"}` is a plausible thing for a publisher to want to match.
`{` is rejected *only* when it opens something shaped like a genuine
counted repetition -- `\d+(,\d*)?\}` immediately following it, i.e. `{2}`,
`{2,}`, `{2,3}` -- via a lookahead in `_Parser._parse_atom`, not by
reserving the character outright. A bare `{` that isn't followed by that
shape (`{oops}`, a lone `{`) is an ordinary literal, and `\{`/`\}` are
valid escapes to a literal brace (both are in `_METACHARACTERS`).

AST node types: `Lit`, `Cat`, `Alt`, `Star`, `Empty` -- five, not seven,
because the parser desugars `+` to `Cat(x, Star(x))` and `?` to
`Alt(x, Empty())` rather than inventing Plus/Opt node types. Task 5's NFA
builder therefore only ever has to handle Cat, Alt, and Star.
"""

import re

from .errors import DeclarationError

# The full Unicode codepoint span. '.' and a negated class are both defined
# relative to this.
_FULL_SPAN = (0, 0x10FFFF)

# Characters that are metacharacters in this grammar and therefore *not*
# available as a bare literal. '\' escapes any of these back to a literal.
# '{' and '}' are here so `\{`/`\}` always escape to a literal brace, even
# though a *bare* '{' is only rejected when it opens something shaped like
# a counted repetition -- see _COUNTED_REPETITION_RE and _parse_atom.
_METACHARACTERS = set("|*+?(){}[].\\")

# What a counted repetition looks like, immediately after '{': one or more
# digits, then an optional ',' and zero or more digits, then '}' -- {2},
# {2,}, {2,3}. Matched with .match(src, pos) so it's anchored at the '{'
# without needing to re-slice the string. A bare '{' that isn't followed by
# this shape is an ordinary literal character, not a syntax error -- see
# the CORRECTION note in the module docstring.
_COUNTED_REPETITION_RE = re.compile(r"\{\d+(,\d*)?\}")


class PatternError(DeclarationError):
    """A prefix pattern violates the restricted grammar.

    Subclasses DeclarationError (see errors.py, which stays the one base
    module for declaration-time failures) rather than introducing a second
    exception hierarchy for what is, from a publisher's point of view, the
    same kind of problem: something they wrote in a bundle is rejected
    before install.
    """


# --- AST ---------------------------------------------------------------
#
# Plain classes (matching the style already used for Machine/State/
# Transition in machine.py), with value equality so tests -- and later,
# Task 5's compiler -- can compare ASTs structurally instead of by identity.


class Node(object):
    def __eq__(self, other):
        return type(self) is type(other) and self._fields() == other._fields()

    # No explicit __ne__: Python 3's default already inverts __eq__.

    def __hash__(self):
        return hash((type(self), self._fields()))

    def _fields(self):
        raise NotImplementedError


class Lit(Node):
    """A single character drawn from a set of inclusive codepoint ranges."""

    def __init__(self, chars):
        """`chars` is a frozenset of (low, high) inclusive codepoint ranges."""
        self.chars = frozenset(chars)

    def _fields(self):
        return (self.chars,)

    def __repr__(self):
        return "Lit(%r)" % (sorted(self.chars),)


class Cat(Node):
    """`left` followed by `right`."""

    def __init__(self, left, right):
        self.left = left
        self.right = right

    def _fields(self):
        return (self.left, self.right)

    def __repr__(self):
        return "Cat(%r, %r)" % (self.left, self.right)


class Alt(Node):
    """`left` or `right`."""

    def __init__(self, left, right):
        self.left = left
        self.right = right

    def _fields(self):
        return (self.left, self.right)

    def __repr__(self):
        return "Alt(%r, %r)" % (self.left, self.right)


class Star(Node):
    """Zero or more repetitions of `node`."""

    def __init__(self, node):
        self.node = node

    def _fields(self):
        return (self.node,)

    def __repr__(self):
        return "Star(%r)" % (self.node,)


class Empty(Node):
    """Matches the empty string. Only ever produced by the parser's own
    `?` desugaring (Alt(x, Empty())) -- never by parsing zero atoms
    directly; see the module docstring and _Parser.parse_cat below for why
    that distinction matters.
    """

    def _fields(self):
        return ()

    def __repr__(self):
        return "Empty()"


# --- range helpers -------------------------------------------------------
#
# Kept separate from the parser and tested directly (TestComplementHelper /
# TestMergeRangesHelper in test_pattern.py): an off-by-one here is the
# defect most likely to survive into Task 6, where it would silently
# produce a wrong collision verdict instead of a visible crash.


def _merge_ranges(ranges):
    """Sort `ranges` and coalesce overlapping or adjacent (low, high)
    inclusive codepoint ranges into the minimal equivalent list.

    Adjacency matters, not just overlap: (0, 5) and (6, 10) share no
    codepoint but cover a contiguous span, so they must still merge --
    otherwise a class built from adjacent items would carry a spurious
    internal gap.
    """
    if not ranges:
        return []
    ordered = sorted(ranges)
    merged = [ordered[0]]
    for lo, hi in ordered[1:]:
        mlo, mhi = merged[-1]
        if lo <= mhi + 1:
            merged[-1] = (mlo, max(mhi, hi))
        else:
            merged.append((lo, hi))
    return merged


def _complement(ranges, full=_FULL_SPAN):
    """The complement of `ranges` within `full`, as a frozenset of
    (low, high) inclusive ranges: everything in `full` not covered by
    `ranges`, computed by merging then walking the gaps between merged
    ranges (and before the first / after the last).
    """
    merged = _merge_ranges(list(ranges))
    lo_bound, hi_bound = full
    result = []
    cursor = lo_bound
    for lo, hi in merged:
        if lo > cursor:
            result.append((cursor, lo - 1))
        cursor = max(cursor, hi + 1)
    if cursor <= hi_bound:
        result.append((cursor, hi_bound))
    return frozenset(result)


# --- parser ----------------------------------------------------------------


def parse_pattern(src):
    """Parse `src` as a prefix pattern and return its AST (a Node).

    Raises PatternError if `src` does not conform to the grammar in this
    module's docstring.
    """
    return _Parser(src).parse()


class _Parser(object):
    """A recursive-descent parser over the grammar in the module docstring.
    One method per production; `pos` is the cursor into `src`.
    """

    def __init__(self, src):
        self.src = src
        self.pos = 0

    def parse(self):
        node = self._parse_alt()
        if self.pos != len(self.src):
            raise PatternError(
                "unexpected %r at position %d" % (self.src[self.pos], self.pos)
            )
        return node

    # -- helpers --

    def _peek(self):
        return self.src[self.pos] if self.pos < len(self.src) else None

    def _advance(self):
        ch = self.src[self.pos]
        self.pos += 1
        return ch

    # -- grammar productions --

    def _parse_alt(self):
        # alt := cat ('|' cat)*
        node = self._parse_cat()
        while self._peek() == "|":
            self._advance()
            node = Alt(node, self._parse_cat())
        return node

    def _parse_cat(self):
        # cat := rep*
        #
        # Decision 2: cat() may syntactically consume zero reps -- that is
        # what makes "a|" and "" parse at all under this grammar's raw
        # production rules. But a cat that matches the empty string means
        # the branch it belongs to (or, if it's the only branch, the whole
        # pattern) matches every message, colliding with every other
        # installed machine while every other check still passes. That is
        # the framework's central guarantee failing silently, so it is
        # rejected here, at the one point in the grammar where an empty
        # match can be produced *syntactically* -- with no NFA involved.
        #
        # This is deliberately narrower than full nullability: `a*` and
        # `a?` at top level are also nullable, but detecting that needs the
        # compiled automaton and is Task 5's job. Do not extend this check
        # to cover them.
        start = self.pos
        parts = []
        while True:
            ch = self._peek()
            if ch is None or ch in "|)":
                break
            parts.append(self._parse_rep())
        if not parts:
            raise PatternError(
                "empty alternation branch at position %d: a pattern (or "
                "branch) that matches the empty string would collide with "
                "every message" % start
            )
        node = parts[0]
        for part in parts[1:]:
            node = Cat(node, part)
        return node

    def _parse_rep(self):
        # rep := atom ('*' | '+' | '?')?
        node = self._parse_atom()
        ch = self._peek()
        if ch == "*":
            self._advance()
            return Star(node)
        if ch == "+":
            # Desugared here, not as its own node type -- see point 4 in
            # the module docstring.
            self._advance()
            return Cat(node, Star(node))
        if ch == "?":
            self._advance()
            return Alt(node, Empty())
        return node

    def _parse_atom(self):
        # atom := literal | '.' | class | '(' alt ')'
        ch = self._peek()
        if ch is None:
            raise PatternError("unexpected end of pattern at position %d" % self.pos)

        if ch == "(":
            return self._parse_group()
        if ch == ".":
            self._advance()
            return Lit(frozenset([_FULL_SPAN]))
        if ch == "[":
            return self._parse_class()
        if ch == "\\":
            return self._parse_escape()
        if ch == "{" and _COUNTED_REPETITION_RE.match(self.src, self.pos):
            # Only reject '{' when it actually opens {n}/{n,}/{n,m} -- see
            # the CORRECTION note in the module docstring. A '{' that
            # doesn't match this shape falls through to the plain-literal
            # case below.
            raise PatternError(
                "counted repetition '{n,m}' is not supported (at position "
                "%d)" % self.pos
            )
        if ch in "|*+?)]":
            raise PatternError(
                "unexpected metacharacter %r at position %d" % (ch, self.pos)
            )
        self._advance()
        return Lit(frozenset([(ord(ch), ord(ch))]))

    def _parse_group(self):
        start = self.pos
        self._advance()  # consume '('
        if self._peek() == "?":
            # CORRECTION (fix round 1): covers lookaround ((?=...),
            # (?!...), (?<=...), (?<!...)) and named/non-capturing groups
            # ((?P<name>...), (?<name>...), (?:...)) alike -- every one of
            # those starts with '(?'. The brief's decision 2 said to name
            # this "lookaround", but that's only true of some of them; the
            # message instead names what's true of the whole family: this
            # language has only plain groups.
            raise PatternError(
                "extended group syntax '(?...)' is not supported; this "
                "language has only plain groups (at position %d)" % start
            )
        node = self._parse_alt()
        if self._peek() != ")":
            raise PatternError("unclosed group starting at position %d" % start)
        self._advance()  # consume ')'
        return node

    def _parse_escape(self):
        start = self.pos
        self._advance()  # consume '\'
        ch = self._peek()
        if ch is None:
            raise PatternError(
                "dangling backslash at end of pattern (position %d)" % start
            )
        if ch.isdigit():
            raise PatternError(
                "backreferences are not supported (\\%s at position %d)"
                % (ch, start)
            )
        if ch in _METACHARACTERS:
            self._advance()
            return Lit(frozenset([(ord(ch), ord(ch))]))
        raise PatternError(
            "unsupported escape \\%s at position %d" % (ch, start)
        )

    def _parse_class(self):
        # class := '[' '^'? item+ ']'
        # item  := char '-' char | char
        start = self.pos
        self._advance()  # consume '['
        negate = False
        if self._peek() == "^":
            negate = True
            self._advance()

        ranges = []
        while True:
            ch = self._peek()
            if ch is None:
                raise PatternError(
                    "unclosed character class starting at position %d" % start
                )
            if ch == "]":
                break
            ranges.append(self._parse_class_item())

        if not ranges:
            raise PatternError("empty character class at position %d" % start)

        self._advance()  # consume ']'
        chars = frozenset(_merge_ranges(ranges))
        if negate:
            chars = _complement(chars)
        return Lit(chars)

    def _parse_class_item(self):
        # item := char '-' char | char
        lo = self._advance()
        has_range = (
            self._peek() == "-"
            and self.pos + 1 < len(self.src)
            and self.src[self.pos + 1] != "]"
        )
        if not has_range:
            return (ord(lo), ord(lo))
        self._advance()  # consume '-'
        hi = self._advance()
        if ord(hi) < ord(lo):
            raise PatternError(
                "invalid range %r-%r at position %d" % (lo, hi, self.pos)
            )
        return (ord(lo), ord(hi))
