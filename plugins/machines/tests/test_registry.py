import contextlib
import io
import os
import tempfile
import unittest

from machines.cli import main
from machines.declaration import parse
from machines.registry import check_all
from tests.test_declaration import VALID


def named(name, prefix, version="v1"):
    text = VALID.replace("machine: session-relay", "machine: " + name)
    text = text.replace('prefix: "session-relay:v1 "', 'prefix: "%s"' % prefix)
    return parse(text.replace("version: v1", "version: " + version))


class TestCheckAll(unittest.TestCase):
    def test_no_machines_reports_zero_examined_and_no_collisions(self):
        report = check_all([])
        self.assertEqual(report.collisions, [])
        self.assertEqual(report.examined, 0)

    def test_two_disjoint_machines_do_not_collide(self):
        report = check_all([named("alpha", "alpha:v1 "), named("beta", "beta:v1 ")])
        self.assertEqual(report.collisions, [])
        self.assertEqual(report.examined, 2)

    def test_two_machines_claiming_one_prefix_collide(self):
        report = check_all([named("alpha", "shared:v1 "), named("beta", "shared:v1 ")])
        self.assertEqual(report.collisions, [("alpha", "beta")])

    def test_a_proper_prefix_collides(self):
        report = check_all([named("alpha", "shared:"), named("beta", "shared:v1 ")])
        self.assertEqual(report.collisions, [("alpha", "beta")])

    def test_two_versions_of_one_machine_are_not_a_collision(self):
        report = check_all([named("alpha", "alpha:v1 ", "v1"),
                            named("alpha", "alpha:v1 ", "v2")])
        self.assertEqual(report.collisions, [])

    def test_a_malformed_machine_is_reported_under_its_own_name(self):
        bad = named("alpha", "alpha:v1 ")
        bad.initial = "nowhere"
        report = check_all([bad, named("beta", "beta:v1 ")])
        self.assertIn("alpha", report.problems)
        self.assertNotIn("beta", report.problems)

    # --- gap found while preparing this task: a prefix that won't compile
    # (unparseable, or nullable -- see pattern.py's compile_pattern) must
    # not crash check_all. It is reported like any other problem, and the
    # machine that carries it is excluded from collision checking, since a
    # pattern that will not compile cannot be intersected with anything.

    def test_a_pattern_that_will_not_compile_is_reported_not_raised(self):
        # "x*" is nullable (matches the empty string), so compile_pattern
        # raises PatternError for it -- see pattern.py's module docstring
        # and compile_pattern's nullability check.
        bad = named("badpattern", "x*")
        report = check_all([bad, named("beta", "beta:v1 ")])
        self.assertIn("badpattern", report.problems)
        self.assertNotIn("beta", report.problems)
        self.assertEqual(report.collisions, [])

    def test_a_good_pair_either_side_of_a_bad_machine_still_collides(self):
        bad = named("badpattern", "x*")
        alpha = named("alpha", "shared:v1 ")
        beta = named("beta", "shared:v1 ")
        report = check_all([alpha, bad, beta])
        self.assertIn("badpattern", report.problems)
        self.assertEqual(report.collisions, [("alpha", "beta")])
        self.assertEqual(report.examined, 3)


class TestCli(unittest.TestCase):
    def test_no_paths_exits_2_and_says_so(self):
        out = io.StringIO()
        with contextlib.redirect_stderr(out):
            code = main([])
        self.assertEqual(code, 2)

    def test_a_missing_path_exits_2(self):
        out = io.StringIO()
        with contextlib.redirect_stderr(out):
            code = main(["/nonexistent/SKILL.md"])
        self.assertEqual(code, 2)

    def test_a_valid_fixture_exits_0_and_reports_the_count(self):
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            code = main(["tests/fixtures/valid-session-relay.md"])
        self.assertEqual(code, 0)
        self.assertIn("Examined 1 machine", out.getvalue())

    def test_zero_machines_examined_prints_the_count_not_a_bare_pass(self):
        # A directory that exists but holds no SKILL.md is zero machines
        # found, not a broken tool -- exit 0, and the count must still be
        # stated. "No collisions found" with no count would be exactly the
        # evidence-discipline failure this requirement exists to prevent:
        # a pass that looked at nothing, worded like a pass that checked
        # something.
        out = io.StringIO()
        with tempfile.TemporaryDirectory() as empty_dir:
            with contextlib.redirect_stdout(out):
                code = main([empty_dir])
        self.assertEqual(code, 0)
        self.assertIn("Examined 0 machines", out.getvalue())
        self.assertIn("No collisions found", out.getvalue())

    def test_a_malformed_declaration_exits_1_not_2(self):
        # A file that fails to parse is a problem the checker found, not a
        # reason the tool itself could not run -- it must not share exit 2
        # with a missing path or missing PyYAML.
        out = io.StringIO()
        with tempfile.TemporaryDirectory() as d:
            bad_path = os.path.join(d, "SKILL.md")
            with open(bad_path, "w") as f:
                f.write("no machine block here\n")
            with contextlib.redirect_stdout(out):
                code = main([bad_path])
        self.assertEqual(code, 1)


if __name__ == "__main__":
    unittest.main()
