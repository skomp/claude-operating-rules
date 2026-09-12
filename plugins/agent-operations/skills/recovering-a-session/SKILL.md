---
name: recovering-a-session
description: "Use when a session will not resume — `--resume` fails, hangs, or errors; a transcript JSONL under ~/.claude/projects/ is very large (past ~4 MB); a session has run for days with no compaction records; or work must be recovered from a session that can no longer be loaded."
---

# Recovering an unresumable session

## The symptom and the cause

One session ran three days and reached **~2.0M tokens on its main chain with zero compaction records** (8.0 MB of message JSON inside a 14 MB transcript). Resume replays the whole chain, so it exceeded even the 1M window and could not be loaded at all.

The transcript was **not corrupt** — every line parsed, no dangling `parentUuid`, no duplicate uuids. It was simply too big to send. Do not go hunting for corruption. Size is the fault.

## How to see it coming

```
wc -c ~/.claude/projects/<slug>/<session-id>.jsonl
```

Past ~4 MB, resume is at risk.

## The recovery procedure

Trim it into a **new** session file; never edit the original.

1. Walk `parentUuid` back from the newest non-sidechain leaf to get the real chain. A record carrying `isSidechain: true` is a subagent thread, not the main chain; a leaf is a record that no other record names as its `parentUuid`. **This walk finds the cut; it is not the output.** Its only job is to prove that the record you cut at genuinely sits on the main chain rather than stranded on a sidechain.
2. Choose a cut at a **plain user text message** — never mid `tool_use`/`tool_result` pair.
3. **Write the file-order slice**: keep that record and every line after it, in the order the original file has them. The chain from step 1 is not what you emit — sidechain records interleaved in that range stay.
4. Set the first kept record's `parentUuid` to `null`.
5. Rewrite `sessionId` (and `session_id` where present) to a fresh uuid, used as the filename. Write that file into the **same** `~/.claude/projects/<slug>/` directory as the original — `--resume` looks nowhere else.
6. Carry the last `mode` / `permission-mode` / `custom-title` / `ai-title` / `agent-name` / `last-prompt` record.
7. Drop `file-history-*`, `queue-operation` and `bridge-session`.
8. Assert zero orphan `tool_result`s and zero unanswered `tool_use`s in the **emitted file** — the file-order slice from step 3, not the step 1 chain — **before** writing.

## Where to aim the cut

At the start of the current arc of work, not at a token count. On a GPU renderer project, cutting at the first prompt of the final day gave 216k tokens and kept the whole relevant thread.

## How to validate it, cheaply

```
claude -p --resume <new-id> --model claude-haiku-4-5-20251001 "Reply with exactly: RESUME OK. Do not use any tools."
```

Run it **from the original session's working directory** — the directory that the `<slug>` encodes. `--resume` resolves which project directory to look in from the current working directory, not from the id, so the command finds the new file only when it runs from that path. The slug is that path with the separators replaced. That lets you read the path back off the directory name, but the mapping is not reversible — an original path containing `-` is ambiguous — so read the path off the slug and then confirm that directory exists.

That proves both that it parses and that it fits. It appends a small exchange to the new transcript; accept that noise, because the auto-mode classifier blocks overwriting a session file afterwards to tidy it up.

## Prevention

A long session's context is not durable storage. Almost nothing was lost on a GPU renderer project only because the design docs, findings and fix reports were already on disk; the single casualty was "where exactly we stopped and what comes next". Write that **as you go**, not at the end, because the session can become unreadable without warning.

The suggested CLAUDE.md block in this plugin's README keeps a one-line version of this rule. This skill is the procedure behind it.
