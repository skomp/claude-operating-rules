# Mechanical verification: session-relay (2026-09-13)

> **Redaction note, 2026-09-13.** The checks recorded below were executed against the
> real repository and session names. Those names were redacted afterwards, here and in
> the files this record describes, before publication. The commands, their outputs and
> the planted near-misses are otherwise exactly as run; only identifiers changed.

Task 5 of the session-relay plan. Re-runs `check` (Task 1), `check2` (Task 2),
`check3` (Task 3) and `check4` (Task 4) together, adds three repository-wide
checks (`sweep`), and records, for every check, a planted near-miss the check
was watched to catch — not just a pass.

Environment: branch `session-relay`, tree clean at `ef6df54` before this run.
All five checks were re-run at the end and the tree confirmed clean again
(only the untracked `.claude/` worktree present, deliberately left alone).

## Baseline: all five together

```
{ check; check2; check3; check4; sweep; }
```

Result (first attempt): `PASS PASS PASS PASS` then
`FAIL: unresolvable skill reference: not-enabled` — see **Defect found in
`sweep` itself**, below, for why and how it was fixed.

Result (after the fix, and again at the very end of the session): `PASS PASS
PASS PASS SWEEP PASS`. Tree clean both times.

## check (Task 1 — plugin manifest and marketplace entry)

**Command:** the `check` function from `task-1-brief.md` Step 1, verbatim.

**Result:** PASS.

**Near-miss:** set `marketplace.json`'s `session-relay` entry `source` to
`./plugins/does-not-exist` (`python3` rewrite of the JSON). `check` failed
with `AssertionError` on the `os.path.isdir(p['source'])` assertion.
Restored with `git checkout -- .claude-plugin/marketplace.json`; `check`
passed again.

Proven able to fail: **yes**.

## check2 (Task 2 — `coordinating-across-repos`)

**Command:** the `check2` function from `task-2-brief.md` Step 1, verbatim.

**Result:** PASS.

**Near-miss (as specified in `task-2-brief.md`, and the defect it reveals):**
`sed -i '' 's/session-relay:stalled/session-relay:stalledd/'` on the skill
file. Expected (per the Task 2 brief) to fail with
`MISSING LITERAL: session-relay:stalled`. **It did not fail — `check2` still
reported PASS.** `grep -qF` matches substrings, and
`session-relay:stalledd` contains `session-relay:stalled` as a prefix, so
the literal check is satisfied by the corrupted text. This is defect #1
named in the Task 5 brief, reproduced concretely rather than assumed. File
restored with `git checkout --`.

**Corrected near-miss:** shortening instead of extending —
`sed -i '' 's/session-relay:stalled/session-relay:stalle/'` — removes the
literal `session-relay:stalled` from the file entirely. `check2` correctly
failed with `MISSING LITERAL: session-relay:stalled`. Restored with
`git checkout --`; `check2` passed again.

**Second near-miss:** appended `x relay:v1 planted` to the file. `check2`
correctly failed with `unnamespaced relay: prefix`. Restored with
`git checkout --`; `check2` passed again.

Proven able to fail: **yes** (via the corrected, shortening-based plant —
the literal-extension plant specified in Task 2's own brief does not work,
and is recorded as broken, not as a pass).

## check3 (Task 3 — `handling-an-inbound-ping`)

**Command:** the `check3` function from `task-3-brief.md` Step 1, verbatim.

**Result:** PASS.

**Near-miss 1:** appended a second copy of the wire-format header
(`<!-- session-relay:v1 from=... -->`) to the file. `check3` correctly
failed with `DUPLICATED wire format; it belongs only in
coordinating-across-repos`. Restored with `git checkout --`; `check3`
passed again.

**Near-miss 2 (the greedy-sed description plant):** before trusting this
plant, counted occurrences of the literal `session-relay:` on the
frontmatter `description:` line specifically — exactly **1** (the whole
file has 18 occurrences of the string, but only one is on the description
line). Because the sed pattern's leading `.*` is greedy, if the description
line carried the literal twice, only the *last* occurrence would be
rewritten and the check would wrongly still pass (this is defect #2 named
in the Task 5 brief). With the count confirmed at 1, the plant is safe to
trust here. Ran
`sed -i '' 's/^description: "\(.*\)session-relay:\(.*\)"$/description: "\1peer sessions\2"/'`.
`check3` correctly failed with `description must contain the literal
session-relay:`. Restored with `git checkout --`; `check3` passed again.

**Known limitation, not fixed (defect #3 named in the Task 5 brief):**
`check3`'s literal loop includes `grep -qF -- 'session-relay:v1 mine'`.
Confirmed directly:
`grep -qF 'session-relay:v1 mine' <<<'session-relay:v1 mineral'` succeeds.
So a file that accidentally contained only `session-relay:v1 mineral` and
never the real phrase would still pass this line of `check3`. **Recorded as
a limitation, not tightened**, because `check3` is Task 3's already-reviewed
and committed artifact and Task 5's job is to re-run it, not amend it; the
real file at hand contains the exact required phrase (`session-relay:v1
mine <owner>/<repo>`, confirmed by direct grep) and no `mineral`-shaped
near-miss, so the weakness is latent here, not live. If this check is ever
revisited, tightening it to `grep -qE -- 'session-relay:v1 mine([^a-z]|$)'`
(or similar) would close the gap.

Proven able to fail: **yes** (both near-misses above; the `mine`/`mineral`
weakness is recorded separately as a limitation, not counted against this).

## check4 (Task 4 — README row and the honest caveat)

**Command:** the `check4` function from `task-4-brief.md` Step 1, verbatim.

**Result:** PASS.

**Near-miss:** `sed -i '' '/session-relay/d' README.md` (deletes every line
mentioning session-relay, including the new table row). `check4` correctly
failed with `expected 5 (header + 4 rows...), got 4`. Restored with
`git checkout -- README.md`; `check4` passed again.

Proven able to fail: **yes**.

**Amended 2026-09-13, after the merge that brought `tone-roulette` onto this
branch.** That merge added a fifth plugin row to the README table, so
`grep -c '^| '` returns **6**, not 5, and `check4` went red on a branch where
nothing about `session-relay` had changed: `expected 5 (header + 4 rows...),
got 6`. The count was asserting the size of the whole table, which any other
plugin can change. The expected value in `check4` is now **6 (header + 5
rows)**, updated in `docs/superpowers/plans/2026-09-13-session-relay.md`, and
re-run here: **PASS**. The near-miss above is unaffected — deleting every
`session-relay` line still drops the count below the expectation and still
fails the check.

## sweep (Task 5 — three new repository-wide checks)

**Command:** the `sweep` function written for this task (Step 1 of
`task-5-brief.md`, with one correction — see below):

```bash
sweep() {
  grep -rnE '(^|[^-])relay:' plugins/ README.md .claude-plugin/ docs/superpowers/specs/ \
    && { echo "FAIL: unnamespaced prefix"; return 1; }
  for f in plugins/*/skills/*/SKILL.md; do
    d=$(basename "$(dirname "$f")")
    grep -qx "name: $d" "$f" || { echo "FAIL: $f name != $d"; return 1; }
  done
  known=$(ls -d plugins/*/skills/*/ | xargs -n1 basename | sort -u)
  for s in $(grep -rhoE '`[a-z][a-z-]+-[a-z-]+`' plugins/session-relay/ | tr -d '`' | sort -u); do
    case "$s" in *-*) ;; *) continue ;; esac
    if grep -qx -- "$s" <<<"$known"; then continue; fi
    grep -qxF -- "$s" <<'ALLOWED'
session-relay
created-by-claude
router-repo
not-enabled
not-mine
courseware-authoring-db
courseware-bundles
coursewear-run
ALLOWED
    test $? -eq 0 || { echo "FAIL: unresolvable skill reference: $s"; return 1; }
  done
  echo "SWEEP PASS"
}
```

**Result:** SWEEP PASS (after the fix below).

**Defect found in `sweep` itself, and the fix.** As given verbatim in
`task-5-brief.md`, the cross-reference sub-check's `ALLOWED` list was
`session-relay`, `created-by-claude`, `router-repo`. Run against
the real, correct, already-committed content of `plugins/session-relay/`
with no fault planted, `sweep` **failed** on its very first run:
`FAIL: unresolvable skill reference: not-enabled`. The regex
`` `[a-z][a-z-]+-[a-z-]+` `` matches any lowercase hyphenated backtick
token, not just skill-name-shaped ones, and the real files legitimately
backtick several such tokens that are not skill directories: the control
replies `not-enabled` and `not-mine`, and the worked-example session/repo
names `courseware-authoring-db`, `courseware-bundles` and `coursewear-run` (from
the addressing measurement in `coordinating-across-repos` §6). None of
these five were in the brief's `ALLOWED` list; `router-repo`, which
*was* in the list, does not appear anywhere in the actual files (it was an
anticipated name that the plan didn't end up using). Fixed by adding the
five real tokens to `ALLOWED`; kept `router-repo` since it is
harmless. This is a correction to the check's exception list, not a
widening of its scope — it still scans the same files and still requires
every unrecognized skill-shaped token to resolve to a real directory.

**Near-miss 1 (repo-wide check 1 — no unnamespaced prefix):** appended
`A note about the relay: mechanism appears here.` to
`plugins/session-relay/skills/coordinating-across-repos/SKILL.md`. `sweep`
correctly failed: `FAIL: unnamespaced prefix` (and printed the offending
`grep -rn` match). Restored with `git checkout --`; `sweep` passed again.

**Near-miss 2 (repo-wide check 2 — skill directory ⇔ frontmatter name):**
changed `name: handling-an-inbound-ping` to
`name: handling-an-inbound-pong` in that skill's `SKILL.md`. `sweep`
correctly failed:
`FAIL: plugins/session-relay/skills/handling-an-inbound-ping/SKILL.md name != handling-an-inbound-ping`.
Restored with `git checkout --`; `sweep` passed again.

**Near-miss 3 (repo-wide check 3 — cross-references resolve):** appended
`` See the `not-a-real-skill` skill. `` to
`plugins/session-relay/skills/handling-an-inbound-ping/SKILL.md`. `sweep`
correctly failed:
`FAIL: unresolvable skill reference: not-a-real-skill`. Restored with
`git checkout --`; `sweep` passed again.

Proven able to fail: **yes**, for all three repository-wide checks bundled
into `sweep`.

## Scope, as constrained

The prefix sweep covers `plugins/`, `README.md`, `.claude-plugin/` and
`docs/superpowers/specs/` only. The plan file
(`.superpowers/sdd/2026-09-13-session-relay/*.md`) is deliberately excluded,
since it quotes the bare prefix to describe planting it. `.superpowers/` and
`.claude/` were not touched or scanned at all; `.claude/` is another
session's git worktree.

## Summary

| Check | Passed at baseline | Near-miss demonstrated | Notes |
|---|---|---|---|
| `check` (Task 1) | yes | yes | — |
| `check2` (Task 2) | yes | yes | Task 2's own specified literal-extension plant is broken (defect #1); a shortening plant was substituted and works |
| `check3` (Task 3) | yes | yes | `session-relay:v1 mine` / `mineral` substring weakness recorded as a limitation, not fixed |
| `check4` (Task 4) | yes | yes | Expected row count raised from 5 to 6 on 2026-09-13, after a merge added a fifth plugin row to the README table |
| `sweep` (Task 5, 3 checks) | yes, after a fix | yes, all 3 sub-checks | `ALLOWED` list in the brief's sample was incomplete for real content; extended, not widened |

No check is recorded as unproven. Every one of the five was watched to fail
on a specific, reproducible near-miss and then to pass again after restore.
