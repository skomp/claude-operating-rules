---
name: verifying-claims
description: "STOP before you report that something is absent, closed, safe, healthy, clean, or not-reproducible. Load this when you are about to say a security property holds, that a check passed, that a probe found nothing, that an API returned 404, or that a low-level tool (dig, curl, psql, the aws CLI) works while your program fails. Load it when you are about to write 'no X found', 'cannot reproduce', 'the bypass is closed', 'main is unprotected', 'the hardware is fine', or 'the tests pass'."
---

# Verifying Claims

## The One Rule

**A check that cannot fail proves nothing, and a negative from one instrument is evidence about that instrument, not about the property you care about.**

"Absent / closed / safe / healthy / cannot reproduce" is the answer you were hoping for, which is why it hides. A passing false oracle is worse than no check: the code and the report both now look like the case was handled.

## The Mandatory Procedure

Whenever a check reports the absence of something:

1. **Run the same probe against a known-POSITIVE input and confirm it fires.** A leak check must find a leak you planted. A bypass probe must succeed against the configuration you know is bypassable. If you cannot make it fire, you have not tested anything.
2. **Guard the needle.** Refuse to run a substring search whose needle is empty, and print the needle's length alongside the verdict.
3. **Distinguish "refused" from "failed earlier".** Read the actual error, not the exit status. `unauthorized_client` and `invalid_scope` mean completely different things about the property under test.
4. **The probe must take the same code path, and cost the same, as the real work.** A health check cheaper than the thing being timed cannot tell healthy from broken.
5. **Prefer a design that needs no detection at all** over "detect then adapt". If you must detect, see 4.

This extends past probes to tests and acceptance scripts. **A fix to a false oracle that you cannot show failing is just another false oracle.**

## Known Blind Spots

### A cheap workload cannot prove the hardware is healthy

A GPU renderer project, 2026-08-20. A renderer was ~10x slow. A trivial shader on the same context measured 0.4 ms, so the GPU, driver and context were pronounced healthy — "the slowness was not real, the shader is just expensive" — and it was written up as resolved. A reboot restored the machine to 61.5 fps from 6.

**A trivial workload never asks the part to raise its clocks**, so it runs at full speed on hardware stuck in a low power state. Proportional scaling ("halving SPP halves the time") separates nothing either — it is equally consistent with every unit of work running 10x slow. Before believing any "not real / cannot reproduce" verdict, ask what a reboot or a fresh process would change.

The wrong conclusion was then used to **discard a correct measurement**: a real 77.9 fps reading, written off as corrupted for contradicting the new theory.

### `dig` is not an oracle for whether your program can resolve a name

A Python API client, 2026-09-04. `curl` said `Could not resolve host: api.example.invalid`; `dig +short` returned an address instantly, against both the router and 8.8.8.8. Reading that as "DNS is fine, so it is the sandbox / the firewall / the API" was wrong on every count.

**`dig` queries a nameserver directly. It never touches the resolver your program uses.** On macOS that is mDNSResponder, which holds a **negative cache**: once a lookup fails, the name keeps failing locally while `dig` keeps succeeding. Two tells:

- **Time the failure.** `getaddrinfo` failed in **0.01s** with `nodename nor servname provided`. Nothing crosses a network in 10ms — that is a cached answer replayed, not a lookup. A real DNS failure costs a timeout. `curl -w '%{time_namelookup}'` shows the same thing.
- **Test a sibling name through the same path.** `app.example.invalid` and `example.invalid` resolved fine through `getaddrinfo`, ruling out "DNS is broken" and pointing at one poisoned entry.

Fix is `sudo dscacheutil -flushcache && sudo killall -HUP mDNSResponder`. It needs sudo, so it is your human partner's to run — say so rather than flailing. Meanwhile pin the address yourself: `curl --resolve host:443:<ip>` answered the actual question in one call.

### curl works but Python hangs — Python has no Happy Eyeballs

A Python API client, 2026-08-31. A token refresh appeared to hang for over two minutes. It was not hanging: `securetoken.googleapis.com` resolves to **8 IPv6 addresses ahead of 8 IPv4 ones**, the host's IPv6 black-holed, and `socket.create_connection`/`urlopen` walk addresses **serially with the timeout applied per attempt, not to the sequence**. So `timeout=30` meant 8 x 30s = 240s before the first IPv4 try. At `timeout=8` the total measured 64.06s — exactly 8 x 8s, which is how the cause was confirmed.

`curl` never showed it, because curl implements Happy Eyeballs (RFC 6555) and races the families. **Python's standard library does not. Go's `net.Dialer` does.** "curl works but my Python script hangs" against a dual-stack host is this, essentially every time. Fix by reordering resolver results IPv4-first, keeping IPv6 as fallback — **never by filtering**, which breaks IPv6-only hosts.

The first fix you reach for is usually worse: detect "does this host have an IPv6 route?" with a UDP `connect()`, which consults the routing table without sending packets. **It returned True on the very host whose IPv6 was dead** — a route existed, it just black-holed. The fix silently did nothing and the 64s stall remained. Reordering needs no oracle, loses nothing, and is correct everywhere.

**Generalise it: when a low-level tool and your program disagree, ask whether they share a code path.** `dig` vs `getaddrinfo`, `curl` vs `urllib`, `psql` vs the driver, `aws` CLI vs the SDK. The tool that works is not evidence that your program's path works — usually it is evidence that the two paths differ, which is the actual finding.

### When `grep -E` is ugrep, it fails silently on digit classes

*Recorded from a concurrent session, 2026-09-12, and confirmed by reproduction. Not yet reviewed by the session that lived it.*

A tutorial-authoring project, 2026-09-12. A sweep for a stale section count returned "no hits". That was a
**false negative from a broken instrument**, not a clean repository. `grep` here is
**ugrep 7.8.4**, and under `-E` a digit class mixed with `\b` makes the whole alternation
match nothing — with a clean exit 1, which is indistinguishable from an honest zero:

```
matches=2   \b(one|...|ten)\b[^.]{0,40}\bsections?\b
matches=0   \b(five|six|[0-9]+)\b[^.]{0,40}\bsections?\b     <- silently broken
matches=0   \b[0-9]+\b[^.]{0,40}\bsections?\b                <- silently broken
```

`-P` handles all three correctly. Two habits follow, and the first is what caught it:

- **Run a second, cruder grep beside the clever one.** A plain search for the bare word
  returned the line the clever pattern had missed. Two instruments disagreeing is the tell;
  one instrument reporting zero is not evidence of anything.
- **Prefer `-P` whenever a pattern mixes `\b` with a character class**, and plant a positive
  control before trusting any zero.

This is a special case of the rule at the top of this file, and the most expensive kind:
a verification tool that fails by returning *the answer you were hoping for*, with nothing
about the output looking wrong.

### A probe that passes for the wrong reason

An OAuth service, 2026-09-09. Three times in one session you reported a security property as holding when the check could not have detected its absence:

- **An empty needle.** `grep -qF -- "$TOK" log` with `$TOK` unset matches every line, so a token-leak check reported a leak where there was none — and would equally have reported *no* leak had you inverted it. The variable was empty because you had assumed the wrong port.
- **The wrong credential.** Fifteen bypass attempts against an OAuth client using a secret belonging to a *different* client. Every request failed `unauthorized_client` before scope resolution was reached, which looked exactly like "the bypass is closed".
- **A duplicate keyword argument.** `f(required_scope="x", **{"required_scope": ""})` raises `TypeError` before any validation runs. You read that as the code refusing a hostile value.

The same session had three tests that could not fail, and a demo script `CLAUDE.md` called "an acceptance step" whose only assertion was that its audit-record count matched its request count — so it exited 0 on a chain where **every** request was rejected. Its fix had to break the chain deliberately and show the script fail before showing it pass.

### A check reports only on what it examined

**A check is a statement about what it examined at the moment it ran.** Everything
below is one rule wearing nine costumes, all of them from a single repository on
2026-09-13, where the same session made the error nine times in a day while writing
this skill.

Each line names what was examined, against what was claimed:

1. **File content, not commit metadata.** Two audits searched the working tree for
   identifying names and passed. The names were in commit messages and author emails.
2. **One branch, not a ref that had diverged.** A rewrite cleaned one branch; local
   `main` had diverged hours earlier and kept the original text.
3. **Commit messages, not the files those commits add.** A `--msg-filter` cleaned every
   message. The same commits added files that still carried the names.
4. **Before a merge, not after.** An audit passed; a later merge reintroduced what it
   had cleared; nobody re-ran it.
5. **The working tree, not the ref being published.** A grep of the checkout was
   reported as "the repository is clean". A different branch was then pushed.
6. **Clean, but the wrong object.** A branch was verified clean and *was the wrong
   lineage* — pushing it would have deleted a plugin from the remote. Clean and correct
   are independent properties.
7. **A name, not the content.** Six refs shared a `bak-`/`backup-` prefix; three
   carried names and three did not. The prefix predicted nothing.
8. **A session's state, not its progress.** `idle` means "not currently working". It
   does not mean finished — the two are indistinguishable from outside.
9. **What a terminal displayed, not what happened.** `tmux capture-pane -p` prints
   characters and discards their styling, so text *drawn* into an empty input box is
   indistinguishable from text *typed* into it. A session reported an intruder on that
   basis. `capture-pane -p -e | cat -v` showed `^[[2m` — dim — and a genuinely empty
   pane had no such run at all.

10. **A rendering, not the thing rendered.** The same session then read a terminal's
   collapsed one-line display of an incoming message — `Message from @…: ` with the
   sender truncated and the line ending `(ctrl+o to expand)` — and reported it as the
   message's wire format. It was not. The real message carries a different envelope
   entirely. Nothing truncates a real message; only a renderer does.

**A rendering is not the thing rendered, and a terminal is a renderer.** Instances 9
and 10 are one missing sentence, and the second happened after the first had been
written into this file.

The mechanism, which is what makes that actionable rather than merely wise: the Claude
Code TUI runs on the **alternate screen**. `tmux capture-pane -S -` returns about 24
lines regardless of `history-limit`, and tool calls are never in the buffer at all. **A
pane cannot tell you what a session read.** Only its transcript can:

```sh
ls ~/.claude/projects/<escaped-cwd>/*.jsonl     # what the session actually did
tmux capture-pane -p -e -t <pane> | cat -v      # and if you must read a pane, keep the styling
```

The styled capture matters because `capture-pane` without `-e` discards exactly the
distinction you need: `^[[2m` marks dim placeholder text the terminal drew, which is
indistinguishable from typed input once the escape codes are stripped.

**Say what the probe read, not what you concluded.** "The repository is clean" was
never supported. "No file content under these paths matches these 43 names" was. The
first silently annexes commit messages, authorship, tags, ref names, reflogs and the
forge; the second invites the obvious question.

**Say what the check can separate.** A check that cannot tell two causes apart cannot
report which one occurred. Instance 9 is the pure case: the command could not
distinguish drawn text from entered text, so its output could not mean what it was
read to mean.

**A theory that explains every property of the evidence is a theory to test.** In
instance 9 the text was contextual, correctly shaped, in the project's own register,
and never submitted. Those were read as proof that something knew what the work was
about. They are the defining properties of generated text.

**A reader inherits the defect, and adds confidence to it.** A second session verified
its own side rigorously — 33 transcripts, zero hits — then accepted the first
session's framing without asking whether "text appeared in a pane" had been
established as "text was entered into a pane". It then supplied reasoning the original
report never contained and handed it to a person as analysis. Before acting on
someone's conclusion, ask what their check could separate.

**For a publication check specifically**, the surfaces are at least: file content,
commit messages, author and committer identity, ref and tag names, and what the forge
serves — which is not what your local refs say.

```sh
git merge-base --is-ancestor <the-correction> <the-ref-you-publish>  # instances 2 and 5
git log --all --format='%ae%n%ce' | sort -u                          # identities
git log --all --format='%B' | grep -iE '<names>'                     # messages
git grep -lIiE '<names>' <ref> -- .                                  # content, per ref
git for-each-ref --format='%(refname)'                               # names leak too
```


### A 404 from one endpoint is not proof of absence

An agent-seat plugin repo, 2026-09-02. You checked `GET /repos/{owner}/{repo}/branches/main/protection`, got a 404, and reported main as unprotected. It was protected — by a **ruleset**, which that endpoint does not report. Two commits went straight to main and the push said so plainly: `remote: Bypassed rule violations for refs/heads/main`.

- **Read what the write actually printed.** That warning sat in the output of your own push several tool calls before you noticed it. A "success" that prints a warning is not a success.
- **When an API says "not found", ask whether you queried the only mechanism.** GitHub has classic branch protection AND rulesets; Cloud IAM has several layers that each answer "no policy" independently.
- **A summary you built yourself is not a check.** Before a production `cdk deploy` you summarised the diff by grepping its *resource* lines, saw only Lambdas and image URIs, and told your human partner "no IAM, no security groups, no data resources". CloudFormation prints IAM statement changes in a **separate table** your grep never touched — there were fourteen of them. They were benign (an S3 prefix moving `3.7.0` -> `3.8.0`), and the deploy's own approval gate caught what you had waved through. Never turn "I did not see X in my filtered view" into "there is no X": look at the unfiltered output, or say which slice you examined.

## Debugging Habits That Generalise

- **Instrument every boundary before theorising.** curl vs Python, OS vs interpreter, DNS vs TCP vs TLS. That localised the stall to "TCP connect", and `create_connection` reporting 64s while the TLS handshake took 0.02s was the whole answer.
- **Time every attempt, failures included**, so a hang and a fast error are distinguishable.
- **Never filter diagnostic output through a grep you wrote for a different problem.** Python's stderr piped through `grep -v ... ValueError ...` to suppress unrelated `blake2b` noise ate the actual exception, and "it hangs" was concluded from an empty result. Re-run unfiltered.
- **When a measurement fights a conclusion, suspect the conclusion.**

## Red Flags — Stop and Prove the Probe Fires

- About to write "no X found", "cannot reproduce", "the bypass is closed", "main is unprotected", "the hardware is fine".
- The check passed first time and you never saw it fail.
- The verdict came from a summary, a filtered view, or a grep — not the unfiltered output.
- A tool succeeds where your program fails, and you concluded the subsystem is healthy.
- A failure came back in under ~10ms, or the health check was cheaper than the real work.

**All of these mean: run the probe against a known-positive input first. If you cannot make it fire, report that you could not verify — not that the property holds.**
