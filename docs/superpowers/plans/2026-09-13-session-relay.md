# session-relay Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ship a fourth plugin, `session-relay`, holding the two skills that let one session raise work in another repository and discuss it to a conclusion in GitHub issue comments.

**Architecture:** Two `SKILL.md` files and a manifest. No executable parts: no hooks, no polling, no registry, no slash command. A session signals a peer only immediately after it writes to an issue and only when that write needs an answer. Every message carries the envelope `session-relay:v1`, and the inbound skill is completely inert for anything that does not.

**Tech Stack:** Markdown with YAML frontmatter, JSON manifests, `gh` CLI in documented commands. No build, no test framework, no dependencies.

**Spec:** `docs/superpowers/specs/2026-09-13-session-relay-design.md`

## How this plan handles the absence of a test framework

This repository ships prose, so there is no `pytest` to go red then green. The TDD cycle
is preserved by making each task's deliverable satisfy a **mechanical check written
before the file exists**:

1. Write the check. Run it. It must FAIL, because the file is not there.
2. Write the file to the contract.
3. Run the check. It must PASS.
4. **Plant a near-miss violation, re-run, confirm the check catches it, revert.** A check
   only ever seen to pass is not evidence. This step is not optional.

   **A planted fault must be checked for reachability, not just written.** Two in
   this plan were not: one extended a literal where `grep -F` matches substrings, and
   Task 3's description fault uses a greedy `sed` that rewrites only the LAST
   `session-relay:` on the line — so a description carrying the literal twice would
   survive the plant silently. Count occurrences before trusting a plant.

   **Shorten a literal to break it; never extend it.** `grep -F` matches substrings, so
   turning `session-relay:stalled` into `session-relay:stalledd` still matches and the
   plant silently does nothing. Task 2's implementer proved this:
   `printf 'session-relay:stalledd' | grep -cF 'session-relay:stalled'` prints `1`.
   Use `session-relay:stalld`.

Checks are inline `bash`. Do not add tooling to this repository; the spec's file list is
closed.

## What this plan gives you, and what it does not

Per `writing-plans-and-dispatches` in this repository: plan prose handed over as
requirements is untested content that looks authoritative. So each task carries a
**contract** (required sections, exact literal strings, cross-references that must
resolve, duplication that must not appear) and a **measurement table**. Where a draft
sentence appears it is labelled a **PROPOSAL**.

**Every dispatch executing a task from this plan must carry this clause:** *"Wording
marked PROPOSAL is a proposal, not a requirement. Be sceptical. Report defects rather
than fixing them silently. If you conclude something in this plan is wrong, say so with
evidence rather than implementing something you believe is incorrect."*

## Global Constraints

Copied verbatim from the spec. Every task's requirements implicitly include these.

- The envelope is `session-relay:v1`. The guard prefix is `session-relay:`.
- The five comment `kind` values: `triage`, `question`, `answer`, `conclusion`, `stalemate`. The five signal-only control replies: `whois`, `mine`, `not-mine`, `not-enabled`, `unsupported`.
- **The protocol is opt-in per repository.** It runs only where that repository's `CLAUDE.md` carries a `## Session relay` declaration naming its peers. A session never *infers* enablement — least of all from being asked to file an issue against another repository — but it does **offer** it once when the section is absent, and enables on any clear yes. `Not enabled.` in that section means never offer again.
- The two labels: `session-relay:open`, `session-relay:stalled`. Issues Claude files also carry `created-by-claude`.
- The cap is ten comments carrying your own `from=`, counted **per issue**.
- Guard order is fixed: (1) prefix, (2) version, (3) repository ownership, (4) `kind`. Guard 1 sends no reply; guards 2, 3 and 4 do.
- Prose references an issue as `repo#123` and a pull request as `PR: repo#123`. **A closing keyword takes the full `owner/repo#123`** — GitHub's parser does not act on the short form.
- Tickets this protocol writes use ASD-STE100 Simplified Technical English, per `tracking-work`.
- No hooks, no polling, no watcher, no registry file, no slash command.
- This protocol never requires a separate private repository.

## Already measured — do not re-derive

| Fact | Value |
|---|---|
| Skill frontmatter keys | `name` (bare) and `description` (double-quoted, single line). Nothing else. |
| `plugin.json` keys | `name`, `version`, `description`, `author`, `homepage`, `repository`, `license`, `keywords`. There is **no** `skills` key; skills are discovered from `skills/`. |
| `author` value | `{ "name": "skomp", "url": "https://github.com/skomp" }` |
| `homepage` and `repository` | `https://github.com/skomp/claude-operating-rules` |
| `license` | `MIT` |
| Starting `version` | `0.1.0` |
| `marketplace.json` plugin entry keys | `name`, `source`, `version`, `category`, `description`, `author` |
| `category` used by the other three | `development` (×2), `productivity` (×1) |
| README plugin table | Header at `README.md:13`, separator at `:14`, three rows at `:15-17`. Columns: `Plugin | Skills | Install it if`. |
| README "Known limitation" section | Claims all skills are untested for retrieval. It must be amended, not left to cover a seventh skill it never measured. |

---

### Task 1: Plugin scaffold and marketplace registration

**Files:**
- Create: `plugins/session-relay/.claude-plugin/plugin.json`
- Modify: `.claude-plugin/marketplace.json`

**Interfaces:**
- Consumes: nothing.
- Produces: the directory `plugins/session-relay/skills/` exists for Tasks 2 and 3. The plugin name `session-relay` is referenced by Task 4's README row.

**Contract for `plugin.json`:** exactly the eight keys in the measurement table, same order as `plugins/ticket-craft/.claude-plugin/plugin.json`. `name` is `session-relay`. `version` is `0.1.0`. `keywords` describes the protocol, not the plugin's internals — propose from: `sessions`, `coordination`, `github-issues`, `cross-repo`, `signals`.

**Contract for the `marketplace.json` entry:** appended as the fourth element of `plugins`, six keys per the measurement table, `source` is `./plugins/session-relay`, `category` is `development`.

- [ ] **Step 1: Write the check and watch it fail**

```bash
check() {
  python3 -c "import json,sys; json.load(open('plugins/session-relay/.claude-plugin/plugin.json'))" || return 1
  python3 - <<'PY' || return 1
import json,sys,os
m=json.load(open('.claude-plugin/marketplace.json'))
names=[p['name'] for p in m['plugins']]
assert names==['evidence-discipline','agent-operations','ticket-craft','session-relay'], names
e=[p for p in m['plugins'] if p['name']=='session-relay'][0]
assert set(e)=={'name','source','version','category','description','author'}, set(e)
assert e['source']=='./plugins/session-relay'
for p in m['plugins']:
    assert os.path.isdir(p['source']), p['source']
p=json.load(open('plugins/session-relay/.claude-plugin/plugin.json'))
assert set(p)=={'name','version','description','author','homepage','repository','license','keywords'}, set(p)
assert p['name']=='session-relay' and p['version']==e['version']
assert p['version']=='0.1.0', p['version']
assert p['author']=={'name':'skomp','url':'https://github.com/skomp'}, p['author']
assert p['license']=='MIT'
assert p['homepage']==p['repository']=='https://github.com/skomp/claude-operating-rules'
assert e['source']=='./plugins/session-relay' and e['category']=='development'
assert p['description']!=e['description'], "the two descriptions serve different readers"
print("PASS")
PY
}
check
```

Expected: FAIL — `plugins/session-relay/.claude-plugin/plugin.json` does not exist.

- [ ] **Step 2: Create the manifest and the entry**

Write `plugins/session-relay/.claude-plugin/plugin.json` and append the `marketplace.json` entry to the contract above. Also create the empty directory `plugins/session-relay/skills/`.

The two `description` fields differ in audience and must not be copies of each other: the `plugin.json` one is read after install, the `marketplace.json` one is read while choosing. **PROPOSAL** for `marketplace.json`: *"One session owns one repository. Work that belongs to another repository becomes an issue filed against it and a signal to the session that owns it; the discussion then happens only in GitHub issue comments, each one naming the session that wrote it."*

- [ ] **Step 3: Run the check**

Run the `check` function from Step 1. Expected: `PASS`.

- [ ] **Step 4: Prove the check can fail**

```bash
python3 -c "
import json; p='.claude-plugin/marketplace.json'; m=json.load(open(p))
m['plugins'][-1]['source']='./plugins/does-not-exist'
json.dump(m,open(p,'w'),indent=2)"
check   # MUST fail on the isdir assertion
```

**Do not restore with `git checkout .claude-plugin/marketplace.json`.** At this point
the entry is not committed yet, so `checkout` reverts to `HEAD` and discards the whole
Step 2 edit rather than the planted fault. Copy the file aside before planting, and
restore from that copy:

```bash
cp .claude-plugin/marketplace.json "${TMPDIR:-/tmp}/mk.json"   # BEFORE planting
# ... plant, run check, confirm it fails ...
cp "${TMPDIR:-/tmp}/mk.json" .claude-plugin/marketplace.json; rm "${TMPDIR:-/tmp}/mk.json"
check   # MUST pass again
```

If the first `check` passes, the check is broken. Stop and report.

- [ ] **Step 5: Commit**

```bash
git add plugins/session-relay/.claude-plugin/plugin.json .claude-plugin/marketplace.json
git status --short   # confirm nothing unexpected is staged
git commit -m "Add the session-relay plugin manifest"
```

---

### Task 2: The `coordinating-across-repos` skill

**Files:**
- Create: `plugins/session-relay/skills/coordinating-across-repos/SKILL.md`

**Interfaces:**
- Consumes: the directory from Task 1.
- Produces: **the single definition of the wire format.** Task 3 references this file by name and must not restate the header format. Task 5 greps this file for every literal in Global Constraints.

**Contract — frontmatter.** `name: coordinating-across-repos`. The `description` is one double-quoted line and must name the moments that make retrieval fire: finding a cause that lives in another repository, being about to edit a repository this session is not bound to, filing an issue against another repository, and opening or concluding a cross-repo thread.

**PROPOSAL** for the description — attack it, retrieval is the untested property in this repository:

> "Read when this repository has opted in to the session-relay protocol — a `## Session relay` declaration in its `CLAUDE.md` — and you are about to raise work with a peer repository's session, answer one, or conclude a cross-repository thread. Also read it before editing, committing or opening a pull request in a repository this session is not bound to. Being asked to file an issue against another repository is NOT a trigger on its own."

**The last sentence is load-bearing and was added deliberately.** An earlier draft
triggered on "file an issue against another project's repository", which is an
ordinary English request and would start the protocol unasked. If you rewrite this
description, that exclusion survives the rewrite.

**Contract — required sections, in this order:**

1. **The three hard preconditions**, and the statement that the protocol refuses to operate and says so rather than degrading silently. Precondition 1 binds the session to one repository via `git remote get-url origin`; precondition 2 requires GitHub issues; **precondition 3 requires a human's written opt-in** — a `## Session relay` declaration in that repository's `CLAUDE.md` naming the peer repositories. Show the declaration's exact shape. State plainly that a session never enables the protocol and never infers enablement, and that a target repository absent from the declared list is not a peer. Then **Offering the protocol**: do the work you were asked to do first, then offer once, carrying the spec's proposed wording and both of its honest costs — the discussion is autonomous, and it is written into a public record. Any clear yes enables it and writes the declaration; a no writes `Not enabled.` so the offer never returns, with a note that deleting the section restores it. Offer only when the section is absent. Then **When a peer signals a repository that has not opted in**: reply `session-relay:v1 not-enabled <subject>` without reading anything — the signal alone carries the repository and the issue reference — and make the same offer to your own human partner, naming the calling session and the issue.
2. **The teeth.** May read any peer repository. May never edit, commit, branch, tag or open a pull request in one. Work belonging elsewhere becomes an issue plus a signal. State *why*: without it the protocol is optional and a session that can fix the other repository will.
3. **The signalling rule**, with the alternation table from the spec: a signal is emitted only immediately after this session writes to an issue, and only when that write needs something back.
4. **The signal format** and the meaning of `blocking`, including that a sender marking everything blocking removes the receiver's ability to protect its own task.
5. **The envelope**, with the reasoning for naming the protocol rather than the skill or the message type — a renamed skill would retroactively invalidate headers already permanent in GitHub comments.
6. **Addressing**, and **Two vocabularies**. Nothing reliably connects a repository
   to a session name, so resolution is a question asked over the wire. `ListAgents`
   lists live sessions; only interactive peers are reachable. The repository name
   **orders** candidates and never excludes one — carry the spec's measurement
   verbatim, because it is the evidence for the rule: of four real sessions, one
   (`coursewear-run` against `courseWare-supplies`) matched under no string rule at all.
   Then send `session-relay:v1 whois <owner>/<repo>`; the bound session replies
   `mine`, others reply `not-mine`; on `not-mine`, ask every remaining live peer.
   Only when nobody replies `mine` does the sender give up, and **giving up is a
   report with fixing instructions**: what was filed and where, who was asked and what
   each answered, who could not be asked (offline and Remote Control peers), and the
   three alternative remedies — open a session in that repository and tell it to
   triage the issue; check `git remote get-url origin` in a session that should have
   answered, because an unbound session never answers `mine` however often it is
   asked; or, when a session answered `not-enabled`, add the `## Session relay`
   declaration to that repository's `CLAUDE.md`. Carry the spec's rule verbatim: **never report only that no session was
   found.** State why there is no registry: the sessions **are** the registry, asked
   rather than recorded, so the answer cannot go stale. Then give the two `kind` vocabularies —
   the five comment kinds and the five control replies (`whois`, `mine`, `not-mine`,
   `not-enabled`, `unsupported`) — and say that a control signal carries no issue
   number.
7. **The thread.** One venue, the downstream issue. The upstream issue gets exactly two protocol comments.
8. **The comment format** — header and visible attribution line. This section is the single definition.
9. **Labels**, the two plus `created-by-claude`, with `gh label create` shown.
10. **Termination** — the three exits, the cap counted per issue, the loop test stated as a check on the draft rather than a judgement, and the four steps a stuck exit performs.
11. **Reference style**, including the closing-keyword exception and the `gh issue list --repo <owner>/<repo> --state open` verification after a push.

**Contract — required literal strings** (Task 5 greps for these): `ListAgents`, `session-relay:v1`, `triage`, `question`, `answer`, `conclusion`, `stalemate`, `session-relay:open`, `session-relay:stalled`, `created-by-claude`, `git remote get-url origin`, `gh label create`.

**Contract — cross-references that must resolve:** `tracking-work` (STE and the `repo#123` rule), `parallel-sessions` (§4, whose chat a decision belongs in), `handling-an-inbound-ping` (the inbound half).

**Style contract:** match the six existing skills — second person, imperative, a reason attached to each rule, and a closing red-flags table with the columns `About to… | Do this instead`. Sections 1–11 are requirements; the sentences that fill them are yours.

- [ ] **Step 1: Write the check and watch it fail**

```bash
check2() {
  f=plugins/session-relay/skills/coordinating-across-repos/SKILL.md
  test -f "$f" || { echo "MISSING $f"; return 1; }
  head -1 "$f" | grep -qx -- '---' || { echo "no frontmatter"; return 1; }
  grep -qx 'name: coordinating-across-repos' "$f" || { echo "bad name"; return 1; }
  grep -q '^description: "' "$f" || { echo "description must be one quoted line"; return 1; }
  for lit in 'ListAgents' 'whois' 'not-enabled' 'Session relay' 'session-relay:v1' 'triage' 'question' 'answer' 'conclusion' 'stalemate' \
             'session-relay:open' 'session-relay:stalled' 'created-by-claude' \
             'git remote get-url origin' 'gh label create' \
             'tracking-work' 'parallel-sessions' 'handling-an-inbound-ping'; do
    grep -qF -- "$lit" "$f" || { echo "MISSING LITERAL: $lit"; return 1; }
  done
  grep -qE '(^|[^-])relay:' "$f" && { echo "unnamespaced relay: prefix"; return 1; }
  echo "PASS"
}
check2
```

Expected: FAIL with `MISSING plugins/session-relay/skills/coordinating-across-repos/SKILL.md`.

- [ ] **Step 2: Write the skill to the contract**

Read the spec sections *Hard preconditions*, *The signalling rule*, *Addressing*, *The thread*, *Labels* and *Termination*. Write the ten sections. Do not invent rules the spec does not contain; where the spec is silent, say so in your report rather than filling the gap.

- [ ] **Step 3: Run the check**

Run `check2`. Expected: `PASS`.

- [ ] **Step 4: Prove the check can fail**

```bash
f=plugins/session-relay/skills/coordinating-across-repos/SKILL.md
cp "$f" "${TMPDIR:-/tmp}/sr-backup.md"
sed -i '' 's/session-relay:stalled/session-relay:stalld/g' "$f"
check2   # MUST fail with MISSING LITERAL: session-relay:stalled
printf '\nx relay:v1 planted\n' >> "$f"
check2   # MUST fail on the unnamespaced prefix
cp "${TMPDIR:-/tmp}/sr-backup.md" "$f"; rm "${TMPDIR:-/tmp}/sr-backup.md"
check2   # MUST pass again
```

Both planted faults must be caught. If either slips through, the check is broken. Stop and report.

- [ ] **Step 5: Commit**

```bash
git add plugins/session-relay/skills/coordinating-across-repos/SKILL.md
git status --short
git commit -m "Add the coordinating-across-repos skill"
```

---

### Task 3: The `handling-an-inbound-ping` skill

**Files:**
- Create: `plugins/session-relay/skills/handling-an-inbound-ping/SKILL.md`

**Interfaces:**
- Consumes: Task 2's file, which owns the wire format. This skill **references** it and must not restate the comment header.
- Produces: the subagent dispatch boilerplate, quoted verbatim by anyone dispatching triage work.

**Contract — frontmatter.** `name: handling-an-inbound-ping`. The `description` **must contain the literal string `session-relay:`** and must say the skill is inert for any other message. This is the routing mechanism, not decoration: a description reading "handles messages from peer sessions" would route every future protocol into this one skill.

**PROPOSAL** for the description — this one is load-bearing and is verification item 1:

> "Read when a message arrives that begins with `session-relay:` — the envelope of the cross-repo issue protocol — or when your human partner asks whether there are new issues to discuss. Ignore this skill for any other message; it owns one envelope and has no opinion on the rest."

**Contract — required sections, in this order:**

1. **Envelope discipline**, before anything else, with the four guards in the fixed order and the reasoning that **a reply is a form of consumption**: guard 4 accepts BOTH `kind` vocabularies — the five comment kinds and the five control replies — because a guard that rejected `whois` would make addressing impossible, since the message that finds the right session would be refused by every session. Answering a `whois` for a repository this session is not bound to is `not-mine` under guard 3; answering one for the repository it IS bound to is `session-relay:v1 mine <owner>/<repo>`. It is: answering `not-mine` to a message that was never a relay message claims it. Guard 1 sends no reply of any kind. Guards 2 and 4 reply because the message *was* addressed to this protocol and silence would strand the sender.
2. **The decision rule** — the blocking/overlap tree. State the reason a subagent is wrong for an overlapping task: it would read a tree moving under it, the same reason `parallel-sessions` makes a reviewer pin a commit.
3. **The subagent dispatch boilerplate**, as a blockquote to be pasted verbatim, carrying: owns no files; reads and runs `gh` only; never edits, stages or commits; signs with the session's name and ref, not its own; returns to the session rather than asking the human; emits an outbound signal only if it wrote a comment needing an answer.
4. **Manual recovery** — the `gh issue list --state open --label session-relay:open` command, and the instruction to read only the newest protocol comment of each result. State the reason: a recovery check that costs a large fraction of the context window is worse than the missed signal it repairs.
5. **Red flags table**, columns `About to… | Do this instead`.

**Contract — required literal strings:** `session-relay:` (in the description), `session-relay:v1 not-mine`, `session-relay:v1 unsupported`, `session-relay:open`, `parallel-sessions`, `coordinating-across-repos`.

**Contract — what must NOT appear.** This file must not contain the string `<!-- session-relay:v1 from=`. The header format is defined once, in Task 2's file. Two copies of one format is the failure `completing-a-correction` describes.

- [ ] **Step 1: Write the check and watch it fail**

```bash
check3() {
  f=plugins/session-relay/skills/handling-an-inbound-ping/SKILL.md
  test -f "$f" || { echo "MISSING $f"; return 1; }
  grep -qx 'name: handling-an-inbound-ping' "$f" || { echo "bad name"; return 1; }
  grep -q '^description: ".*session-relay:.*"$' "$f" || { echo "description must contain the literal session-relay:"; return 1; }
  for lit in 'session-relay:v1 not-mine' 'session-relay:v1 unsupported' 'session-relay:open' \
             'whois' 'session-relay:v1 mine' 'session-relay:v1 not-enabled' \
             'parallel-sessions' 'coordinating-across-repos'; do
    grep -qF -- "$lit" "$f" || { echo "MISSING LITERAL: $lit"; return 1; }
  done
  grep -qF -- '<!-- session-relay:v1 from=' "$f" && { echo "DUPLICATED wire format; it belongs only in coordinating-across-repos"; return 1; }
  grep -qE '(^|[^-])relay:' "$f" && { echo "unnamespaced relay: prefix"; return 1; }
  echo "PASS"
}
check3
```

Expected: FAIL with `MISSING plugins/session-relay/skills/handling-an-inbound-ping/SKILL.md`.

- [ ] **Step 2: Write the skill to the contract**

Read the spec sections *Envelope discipline*, *Handling an inbound signal*, *Addressing* step 3 and *Manual recovery*.

- [ ] **Step 3: Run the check**

Run `check3`. Expected: `PASS`.

- [ ] **Step 4: Prove the check can fail**

```bash
f=plugins/session-relay/skills/handling-an-inbound-ping/SKILL.md
cp "$f" "${TMPDIR:-/tmp}/sr-backup3.md"
printf '\n<!-- session-relay:v1 from=x repo=y ref=z kind=question seq=1 blocking=no -->\n' >> "$f"
check3   # MUST fail on DUPLICATED wire format
cp "${TMPDIR:-/tmp}/sr-backup3.md" "$f"
sed -i '' 's/^description: "\(.*\)session-relay:\(.*\)"$/description: "\1peer sessions\2"/' "$f"
check3   # MUST fail on the description check
cp "${TMPDIR:-/tmp}/sr-backup3.md" "$f"; rm "${TMPDIR:-/tmp}/sr-backup3.md"
check3   # MUST pass again
```

The second planted fault is the important one: it is exactly the greedy description the spec forbids. If the check does not catch it, the routing guarantee is unenforced. Stop and report.

- [ ] **Step 5: Commit**

```bash
git add plugins/session-relay/skills/handling-an-inbound-ping/SKILL.md
git status --short
git commit -m "Add the handling-an-inbound-ping skill"
```

---

### Task 4: Documentation, and an honest caveat

**Files:**
- Modify: `README.md` (table at `:13-17`, and the `## Known limitation` section)
- Delete: `handoff.md`

**Interfaces:**
- Consumes: the plugin name and both skill names from Tasks 1–3.
- Produces: nothing later tasks depend on.

**Contract — the table row.** A fifth row matching the existing four: bold plugin name, both skill names in backticks, and an "install it if" clause that says who should NOT install it as well as who should. The other three rows each do this.

**Contract — the "Known limitation" section.** It currently claims *these skills* are untested and are faithful records of failures that already happened. Both halves are now wrong for the seventh and eighth skills, in different ways, and the section must say so rather than quietly widening:

- The first three plugins are records of failures that already happened. `session-relay` is a **design**, with no incident behind it. The README's opening paragraph ("Nothing here is advice in the abstract") must be qualified, not deleted.
- Retrieval remains unproven for all of them. For `session-relay` it is scheduled — Task 6 — and the caveat must **narrow when that evidence exists, not before**. Do not write "tested" in this task.

**Contract — `handoff.md`.** Its content is fully captured by the spec. Delete it in the same commit that adds the README row, so the repository never carries both.

- [ ] **Step 1: Write the check and watch it fail**

```bash
check4() {
  test -f handoff.md && { echo "handoff.md still present"; return 1; }
  n=$(grep -c '^| ' README.md)
  test "$n" -eq 6 || { echo "expected 6 (header + 5 rows; the |---| separator does not match '^| '), got $n"; return 1; }
  grep -q 'session-relay' README.md || { echo "no README row"; return 1; }
  grep -qF 'coordinating-across-repos' README.md || { echo "skill not named"; return 1; }
  grep -qF 'handling-an-inbound-ping' README.md || { echo "skill not named"; return 1; }
  grep -qiE 'have not been tested|unproven|untested|not yet been proven' README.md \
    || { echo "the untested caveat must still be present and explicit"; return 1; }
  grep -qiE 'session-relay[^.]{0,80}(is|are) (now )?(tested|proven|verified)' README.md \
    && { echo "do not claim session-relay is tested; Task 6 has not run"; return 1; }
  echo "PASS"
}
check4
```

Expected: FAIL with `handoff.md still present`.

- [ ] **Step 2: Update the README and remove the handoff**

Add the row, qualify the opening paragraph, amend `## Known limitation`, then `git rm handoff.md`.

- [ ] **Step 3: Run the check**

Run `check4`. Expected: `PASS`.

- [ ] **Step 4: Prove the check can fail**

```bash
cp README.md "${TMPDIR:-/tmp}/sr-readme.md"
sed -i '' '/session-relay/d' README.md
check4   # MUST fail
cp "${TMPDIR:-/tmp}/sr-readme.md" README.md; rm "${TMPDIR:-/tmp}/sr-readme.md"
check4   # MUST pass again
```

- [ ] **Step 5: Commit**

`handoff.md` is untracked, so there is nothing for git to remove — delete the file
and stage only `README.md`.

```bash
rm -f handoff.md
git add README.md
git status --short   # handoff.md must not appear at all, not even as untracked
git commit -m "Document session-relay and keep the untested caveat honest"
```

---

### Task 5: Mechanical verification sweep

**Files:**
- Create: `docs/superpowers/verification/2026-09-13-session-relay-mechanical.md`

**Interfaces:**
- Consumes: everything from Tasks 1–4.
- Produces: the evidence file Task 6 appends its live results to.

**Contract.** Re-run `check`, `check2`, `check3` and `check4` together, add three repository-wide checks, and record the output — the commands **and their results** — in the evidence file. A result nobody can re-run is not evidence.

The three repository-wide checks:

1. **No unnamespaced prefix in anything that ships.** Scope it to `plugins/`,
   `README.md`, `.claude-plugin/` and `docs/superpowers/specs/`. **This plan is
   deliberately excluded**, because it quotes the old prefix in order to describe
   planting it as a near-miss; a sweep including the plan can never pass, which is
   as useless as one that can never fail.
2. **Every skill directory is discoverable**: each `plugins/*/skills/*/SKILL.md` has frontmatter whose `name` equals its directory name.
3. **Cross-references resolve**: every skill name mentioned in backticks inside `plugins/session-relay/` matches a real directory under `plugins/*/skills/`.

- [ ] **Step 1: Write the sweep and watch check 2 fail on a plant**

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
ALLOWED
    test $? -eq 0 || { echo "FAIL: unresolvable skill reference: $s"; return 1; }
  done
  echo "SWEEP PASS"
}
cp plugins/session-relay/skills/handling-an-inbound-ping/SKILL.md "${TMPDIR:-/tmp}/sr5.md"
sed -i '' 's/^name: handling-an-inbound-ping$/name: handling-an-inbound-pong/' plugins/session-relay/skills/handling-an-inbound-ping/SKILL.md
sweep   # MUST fail on the name mismatch
cp "${TMPDIR:-/tmp}/sr5.md" plugins/session-relay/skills/handling-an-inbound-ping/SKILL.md
rm "${TMPDIR:-/tmp}/sr5.md"
```

Then plant an unresolvable cross-reference and confirm the third check catches it:

```bash
f=plugins/session-relay/skills/handling-an-inbound-ping/SKILL.md
cp "$f" "${TMPDIR:-/tmp}/sr5b.md"
printf '\nSee the `not-a-real-skill` skill.\n' >> "$f"
sweep   # MUST fail with: unresolvable skill reference: not-a-real-skill
cp "${TMPDIR:-/tmp}/sr5b.md" "$f"; rm "${TMPDIR:-/tmp}/sr5b.md"
sweep   # MUST pass again
```

- [ ] **Step 2: Run everything and capture the output**

`check`, `check2`, `check3` and `check4` are shell functions defined in Step 1 of
Tasks 1, 2, 3 and 4. A fresh session has none of them. **Paste all four definitions
into this shell first**, verbatim from those tasks, then:

```bash
{ check; check2; check3; check4; sweep; } 2>&1 | tee "${TMPDIR:-/tmp}/sr-evidence.txt"
```

All five must report PASS.

- [ ] **Step 3: Write the evidence file**

Record, for each of the five checks: the command, the date, the result, and — for each check — the planted fault that was shown to make it fail. A check with no recorded near-miss must be listed as **unproven**, not as passing.

- [ ] **Step 4: Commit**

```bash
git add docs/superpowers/verification/2026-09-13-session-relay-mechanical.md
git status --short
git commit -m "Record the mechanical verification of session-relay"
```

---

### Task 6: Live verification, and only then narrow the caveat

**Files:**
- Modify: `docs/superpowers/verification/2026-09-13-session-relay-mechanical.md` (append the live results)
- Modify: `README.md` (narrow the caveat — **only if the evidence supports it**)

**Interfaces:**
- Consumes: Task 5's evidence file.
- Produces: the answer that the router repository's first issue is waiting on.

**This task is gated on the human.** It needs the live courseware fleet and a real repository to file into. Do not simulate it, do not mark items passed by reasoning about them, and do not narrow the README caveat without recorded output. If the fleet is unavailable, stop and report which items remain unrun.

The seven items are in the spec's **Verification** section. Run them in order; item 1 is the one another repository depends on.

- [ ] **Step 1: Item 1 — prove the description fires on the prefix alone**

Send a session a bare `session-relay:v1 triage <owner>/<repo>#1 blocking=no` and nothing else — no surrounding explanation, no mention of issues or peers. Record whether the skill loaded.

- [ ] **Step 2: Item 2 — prove the skill ignores what is not its own**

Send an ordinary message with no `session-relay:` prefix while the skill is loaded. It must do nothing: no reply, no `not-mine`, no mention that it saw a protocol message.

- [ ] **Step 3: Items 3–7**

Ownership guard rejects; one round trip; silence when a comment needs no answer; a stuck exit at the cap; and the recovery check reading only `session-relay:open` issues.

- [ ] **Step 4: Append the results, pass or fail**

Record each item's actual output. A failed item is a finding, not a blocker to hide: file it as an issue in this repository with the `created-by-claude` label, written in STE per `tracking-work`.

- [ ] **Step 5: Report item 1's result to the router repository**

Comment on the router repository's first issue with the outcome. That issue states both branches already: the skill loads, so each protocol routes itself and a router is needed only for an unclaimed envelope; or it does not, and a central router becomes necessary.

- [ ] **Step 6: Narrow the README caveat to what was measured**

Only now. Name which items passed, on which date, against which repositories. The six older skills stay uncaveated-down: nothing in this task measured them.

**This step deliberately breaks `check4`.** `check4` refuses any sentence claiming
`session-relay` is tested, which is correct for Tasks 1–5 and wrong once the evidence
exists. Amend that one assertion in the same commit, so the guard becomes "the claim
must name the date and the items it rests on" rather than "the claim is forbidden".
Do not simply delete it: a caveat with nothing guarding it drifts back to a bare
"tested" within two edits.

- [ ] **Step 7: Commit**

```bash
git add docs/superpowers/verification/2026-09-13-session-relay-mechanical.md README.md
git status --short
git commit -m "Record the live verification of session-relay"
```

---

## Notes for the executor

- **Stage explicit paths.** Never `git add -A` or `git commit -a`, and run `git status --short` between `git add` and `git commit`. `git commit` commits the whole index, not the paths you just added.
- **`sed -i ''` is the BSD form** used above, correct on this macOS host. On GNU `sed` it is `sed -i`.
- **The spec is the authority.** Where this plan and the spec disagree, the spec wins and the disagreement is a defect in this plan — report it.
- **Two copies exist.** A private copy of these skills lives in `~/.claude/skills/`. This repository is the source of truth. A correction here must be checked against it.
