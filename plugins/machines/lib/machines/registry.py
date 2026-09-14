"""Check a set of installed machines: each one's own well-formedness, and
whether any two of them can claim the same message.

This is what a person actually reads at install time -- Task 6's
`patterns_collide` answers "do these two patterns collide" for a single
pair; this module turns that into a report over every machine that was
handed to it, using Task 3's `check_machine` for each machine's own
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

    Never raises: a machine whose prefix pattern does not compile
    (`PatternError`, from an unparseable or nullable pattern -- see
    pattern.py) is reported under its own name in `.problems` and left out
    of collision checking, rather than propagating out of this function.
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
            own_problems.append(str(exc))
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
