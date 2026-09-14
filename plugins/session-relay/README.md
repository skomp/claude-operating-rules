# session-relay

Two skills, one protocol: when a fault's cause lives in another repository, file it there
and discuss it in the issue — never in the messages between sessions.

## What it's for

**`coordinating-across-repos`** — the outbound half, and the owner of the wire format. One
session binds to one repository, taken from `git remote get-url origin`. It may read any
peer repository; it may never edit, commit, branch or open a pull request in one. Work
belonging elsewhere becomes an issue filed against that repository plus a one-line signal to
the session bound to it. A signal is emitted only immediately after you write to an issue,
and only when that write needs an answer or ends a thread a peer is waiting on. It carries a
reference and routing flags — never a question, an answer or an argument. Resolution is a
`whois` asked over the wire rather than a guess from session names, because names do not
reliably say which repository a session owns.

**`handling-an-inbound-ping`** — the inbound half. Four guards in a fixed order, and the
order is the point: the prefix, the version, the repository and its opt-in, then the `kind`.
**Guard 1 replies to nothing** — a reply is a form of consumption, and answering `not-mine`
to a message that was never this protocol's claims it. A blocking signal that overlaps the
in-flight task waits for that task; everything else goes to a subagent, so a session is
never stalled by a signal.

See `skills/coordinating-across-repos/SKILL.md` for the wire format, the labels and the
three termination exits.

## Install it if

Your project spans several repositories, each with its own live Claude session, and you
track work in GitHub issues.

Skip it if you work in one repository alone, or if that repository tracks work in a
`TODO.md`. Both are hard preconditions and the protocol refuses to run without them. It is
also opt-in per repository: it does nothing until that repository's `CLAUDE.md` carries a
`## Session relay` declaration naming its peers. A session never enables it and never infers
enablement — least of all from being asked to file an issue somewhere else. It offers once,
and enables on a clear yes.

## No executable parts

No hooks, no polling, no watcher, no registry file, no slash command. The durable record is
the GitHub issue; the signal is only an optimisation on top of it. A missed signal costs
latency and nothing else, and is recovered by asking — which one label makes cheap.

## What has been measured

Unlike the other rule plugins here, this one is a design rather than a record of a past
failure. It has been run: seven live verification items on 2026-09-13 and 2026-09-14,
against two throwaway repositories with one session bound to each. All seven passed, and
the run found three defects that no review had — a precedence rule the protocol never
stated, a rule written as a condition that therefore never fired, and a guard that leaked
protocol commentary into ordinary replies.

What that does **not** establish is use on real work. Nobody has yet had a genuine
cross-repository fault triaged this way. See
`docs/superpowers/verification/2026-09-13-session-relay-live.md`.
