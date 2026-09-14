"""Check a set of installed machines: each one's own well-formedness, and
whether any two of them can claim the same message.

This is what a person actually reads at install time -- `product.py`'s
`patterns_collide` answers "do these two patterns collide" for a single
pair; this module turns that into a report over every machine that was
handed to it, using `machine.py`'s `check_machine` for each machine's own
well-formedness first.

Two things this module has to do that `patterns_collide` itself does not:

- A prefix that will not compile (unparseable, or nullable -- see
  pattern.py's `compile_pattern`) makes `patterns_collide` raise
  `PatternError`. `check_machine` never looks at the prefix at all, so
  nothing upstream of this module catches that. A single bad prefix must
  not crash a check whose whole point is to report every problem at once;
  it is recorded as that machine's own problem instead, and the machine is
  excluded from collision checking -- a pattern that will not compile
  cannot be intersected with anything. Every other machine is still
  checked against every other, bad machine included on neither side.

- Two machines with the same `name` and a different `version` are one
  protocol's history (an installer keeps old versions on purpose), not a
  collision, so that pair is skipped. Two machines with *different* names
  are still compared even when their prefixes are written identically --
  that is the collision this module exists to find.
"""

import itertools

from .machine import check_machine
from .pattern import PatternError, compile_pattern
from .product import patterns_collide


class Report(object):
    """The result of `check_all`.

    - `examined`: how many machines were looked at, including zero. A
      report that found no collisions because it was handed no machines
      must not read the same as a report that checked ten machines and
      found them all clean -- see the module-level docstring and
      `check_all` below.
    - `problems`: machine name -> its own list of problems (from
      `check_machine`, plus a prefix that would not compile). A machine
      with no problems of its own is absent from this dict, not present
      with an empty list.
    - `collisions`: pairs of machine names that can claim the same
      message, each pair as a sorted 2-tuple, each pair listed once, the
      whole list sorted -- so the output is stable across runs.
    """

    def __init__(self, examined, problems, collisions):
        self.examined = examined
        self.problems = problems
        self.collisions = collisions


def check_all(machines):
    """Check every machine in `machines` for its own well-formedness, then
    check every pair of distinctly-named machines against each other for a
    collision. Returns a `Report`.

    A machine whose prefix pattern does not compile (`PatternError`, from
    an unparseable or nullable pattern -- see pattern.py) is reported under
    its own name in `.problems` and left out of collision checking, rather
    than propagating out of this function.

    A prefix nested deep enough in `(...)` groups is named by
    `PatternError` too -- pattern.py's parser tracks nesting depth and
    rejects past 100 levels, well short of where it would recurse into a
    raw `RecursionError`. That guard is the ordinary case; `RecursionError`
    itself is also caught here, alongside `PatternError`, as a backstop --
    converted to the same kind of named problem -- for whatever AST shape
    (if any) reaches a deep stack some other way, in either the parser or
    the compiler. See pattern.py's `_MAX_GROUP_DEPTH` for the measurement
    and reasoning; the handler below stays trivial on purpose (no
    formatting that calls back into pattern code, no further recursion),
    since `RecursionError` fires with the stack nearly exhausted.

    Those are the only exceptions this function catches, and they are the
    only ones a `Machine` built by `declaration.parse` can produce here. It
    is deliberately not described as "never raises": a `Machine`
    constructed by hand, bypassing the parser's shape guards, can still
    carry a non-string `prefix` or a non-iterable `transitions`, and this
    function would let that `TypeError` through. `parse` is what makes that
    unreachable in practice (see declaration.py's shape guards), not a
    blanket catch here -- swallowing arbitrary exceptions would turn a bug
    in this library into a finding about the publisher's machine.
    """
    problems = {}
    collidable = []  # machines fit to compare (prefix compiles); the compiled
                     # pattern is not kept here -- patterns_collide recompiles
                     # both prefixes itself on every call

    for m in machines:
        own_problems = list(check_machine(m))
        try:
            compile_pattern(m.prefix)
        except PatternError as exc:
            # Name the field. Every `check_machine` message says which
            # field it is about; without the prefix here, a publisher
            # reads `alpha: unclosed group starting at position 0` and has
            # to guess which of nine fields is a pattern at all.
            own_problems.append("prefix pattern %r: %s" % (m.prefix, exc))
        except RecursionError:
            # Backstop, not the primary guard -- see the docstring above
            # and pattern.py's `_MAX_GROUP_DEPTH`. Deliberately trivial:
            # RecursionError is raised with the stack nearly exhausted, and
            # while Python unwinds before this handler runs, the handler
            # itself must not recurse or call back into pattern code (a
            # %r of a string does not). Just name the field and stop.
            own_problems.append(
                "prefix pattern %r: too deeply nested to analyse" % (m.prefix,)
            )
        else:
            collidable.append(m)
        if own_problems:
            problems[m.name] = own_problems

    collisions = []
    for a, b in itertools.combinations(collidable, 2):
        if a.name == b.name:
            # Same protocol, different (or, degenerately, the same)
            # version -- kept on purpose, not a collision. See the
            # module docstring.
            continue
        if patterns_collide(a.prefix, b.prefix):
            collisions.append(tuple(sorted((a.name, b.name))))

    collisions.sort()

    return Report(len(machines), problems, collisions)
