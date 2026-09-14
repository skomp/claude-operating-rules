"""The `machines-check` entry point.

Reads one or more paths from the command line, each either a machine
declaration file directly or a directory to look in for a `SKILL.md`, parses
every machine it finds, and reports both each machine's own well-formedness
(`check_machine`, via `check_all`) and whether any two collide on the same
prefix.

Three exit codes, not two:

- `0` -- every machine examined is well-formed and none collide.
- `1` -- the tool ran to completion and found a problem: a machine failed to
  parse, `check_machine` found something wrong with it, or two machines
  collide. This is "I checked, and something is wrong."
- `2` -- the tool could not run at all: no paths were given, a given path
  does not exist or cannot be read, or PyYAML is missing. This is "I could
  not check anything," and must never be confused with `1` -- a broken
  install must not read as a passing or failing check.

The `import yaml` needed to actually parse a declaration is deferred to
inside `main`, after the argument checks, specifically so that importing
this module (as the test suite does) never requires PyYAML to be installed,
and so a missing PyYAML is reported as an exit-2 install instruction rather
than an uncaught ImportError traceback -- even if this module is invoked
directly (`python3 -m machines.cli`) rather than through `bin/machines-check`,
which checks for PyYAML itself before ever reaching this module.
"""

import os
import sys


def _resolve_path(path):
    """Turn one command-line argument into a list of declaration files to
    parse, or a usage error.

    A file is taken as a declaration file directly, whatever it is named --
    the CLI test fixtures are not named SKILL.md, and there is no reason to
    require that of a path the caller named explicitly. A directory is
    searched for a `SKILL.md` directly inside it (not recursively -- "a
    directory searched for one," singular). A directory that exists but
    holds no `SKILL.md` contributes zero files; that is not an error, it is
    zero machines found there, and the caller reports that honestly rather
    than refusing to run.

    Returns (files, error): `error` is a human-readable string when the
    path itself could not be used at all (does not exist, or is neither a
    file nor a directory) -- the caller turns that into exit 2.
    """
    if not os.path.exists(path):
        return None, "path not found: %s" % path
    if os.path.isdir(path):
        candidate = os.path.join(path, "SKILL.md")
        if os.path.isfile(candidate):
            return [candidate], None
        return [], None
    if os.path.isfile(path):
        return [path], None
    return None, "not a file or directory: %s" % path


def main(argv):
    if not argv:
        sys.stderr.write("usage: machines-check <path>...\n")
        sys.stderr.write(
            "  each <path> is a machine declaration file, or a directory "
            "to search for a SKILL.md\n"
        )
        return 2

    try:
        import yaml  # noqa: F401  -- exercised transitively by declaration.py
    except ImportError:
        sys.stderr.write("machines-check: PyYAML is required. Install it with:\n")
        sys.stderr.write("    python3 -m pip install PyYAML\n")
        return 2

    from .declaration import parse
    from .errors import DeclarationError
    from .registry import check_all

    files = []
    for path in argv:
        found, error = _resolve_path(path)
        if error is not None:
            sys.stderr.write("machines-check: %s\n" % error)
            return 2
        files.extend(found)

    machines = []
    load_problems = {}
    for filepath in files:
        try:
            with open(filepath, "r") as f:
                text = f.read()
        except OSError as exc:
            sys.stderr.write("machines-check: cannot read %s: %s\n" % (filepath, exc))
            return 2
        try:
            machines.append(parse(text))
        except DeclarationError as exc:
            load_problems[filepath] = str(exc)

    report = check_all(machines)

    print("Examined %d machine%s" % (
        report.examined, "" if report.examined == 1 else "s"))

    for filepath in sorted(load_problems):
        print("%s: %s" % (filepath, load_problems[filepath]))

    for name in sorted(report.problems):
        for msg in report.problems[name]:
            print("%s: %s" % (name, msg))

    if report.collisions:
        for a, b in report.collisions:
            print("collision: %s and %s claim an overlapping prefix" % (a, b))
    else:
        print("No collisions found")

    found_a_problem = bool(load_problems) or bool(report.problems) or bool(report.collisions)
    return 1 if found_a_problem else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
