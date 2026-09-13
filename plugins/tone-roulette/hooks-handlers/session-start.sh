#!/usr/bin/env bash
#
# tone-roulette SessionStart handler.
#
# Reads the SessionStart hook JSON from stdin, rolls (or resumes) a
# conversational tone from the plugin's output-styles catalogue, persists the
# choice per session, and emits a JSON object on stdout carrying a one-line
# announcement (`systemMessage`) and the tone body with its YAML frontmatter
# stripped (`hookSpecificOutput.additionalContext`).
#
# Contract (see task-2-brief.md):
#   - bash + coreutils only. No jq, no python, no `shuf` (absent on the
#     target machine) — randomness comes from $RANDOM.
#   - Every failure path exits 0. On a fatal problem this script prints
#     nothing and exits 0.
#   - No tone text is hardcoded here: the catalogue in output-styles/*.md is
#     the only source of tone names and bodies.
#
# Catalogue location: ${CLAUDE_PLUGIN_ROOT}/output-styles when
# CLAUDE_PLUGIN_ROOT is set (the normal case — Claude Code sets it when it
# runs this hook), falling back to the directory next to this script so the
# handler also works invoked standalone. Tests point CLAUDE_PLUGIN_ROOT at an
# isolated fixture directory so they never touch the shipped catalogue.

set -u

main() {
  local script_dir styles_dir state_dir input session_id source_val state_file
  local tones=() f base existing selected count idx off_token is_off rolled
  local tone_file body escaped_body sys_message escaped_sys_message

  script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

  if [ -n "${CLAUDE_PLUGIN_ROOT:-}" ]; then
    styles_dir="${CLAUDE_PLUGIN_ROOT}/output-styles"
  else
    styles_dir="$(cd "$script_dir/.." 2>/dev/null && pwd)/output-styles"
  fi

  # --- Read the catalogue. Empty/missing catalogue is fatal: nothing to
  #     announce, nothing to inject. Print nothing, exit 0. ---
  tones=()
  if [ -d "$styles_dir" ]; then
    for f in "$styles_dir"/*.md; do
      [ -e "$f" ] || continue
      base="$(basename "$f" .md)"
      tones+=("$base")
    done
  fi
  count=${#tones[@]}
  if [ "$count" -eq 0 ]; then
    return 0
  fi

  # --- Read stdin (the hook JSON). Never fatal: malformed or empty stdin
  #     just means session_id extraction below finds nothing. Guarded
  #     against a closed fd 0: with fd 0 closed and no writer, `cat` would
  #     otherwise block forever — bash reuses the closed fd 0 for the
  #     command substitution's own capture pipe, so `cat` ends up reading a
  #     pipe that never sees EOF (issue #7 item 1). Testing fd 0 via a
  #     throwaway dup to fd 3 costs nothing on the normal piped path and
  #     never touches fd 0 itself, so that path is unchanged. Claude Code
  #     always pipes the payload, so a closed fd 0 is not reachable in
  #     normal use; this guard exists so the handler's own "every path
  #     exits 0" contract holds even when it isn't. ---
  input=""
  if { exec 3<&0; } 2>/dev/null; then
    exec 3<&-
    input="$(cat 2>/dev/null)"
  fi

  # --- Extract session_id without jq: a grep+sed pull of the JSON string
  #     field, per Global Constraint 3 and the brief's Step 0 fallback. ---
  session_id="$(printf '%s' "$input" 2>/dev/null | grep -o '"session_id"[[:space:]]*:[[:space:]]*"[^"]*"' | head -n 1 | sed -E 's/^"session_id"[[:space:]]*:[[:space:]]*"(.*)"$/\1/')"

  # --- Sanitise session_id with the same rule the $PWD fallback below
  #     already uses. session_id is expected to be a UUID from Claude Code,
  #     not attacker input, but nothing about composing it directly into
  #     "$state_dir/$session_id" stopped a value like "../../escaped" from
  #     writing outside the state directory. Applying the identical `tr`
  #     here means both the stdin-supplied id and the $PWD fallback share
  #     one hygiene rule instead of only one of them being safe. A missing
  #     or empty session_id sanitises to itself (empty), so the fallback
  #     checks below are unaffected. ---
  session_id="$(printf '%s' "$session_id" | tr -c 'A-Za-z0-9_.-' '_')"

  # --- Extract source the same way: it names the matcher value
  #     (startup|resume|clear|compact|fork), and decides whether a leftover
  #     "off" state is honored (everything but startup) or ignored
  #     (startup always rolls fresh — see the off-token handling below). ---
  source_val="$(printf '%s' "$input" 2>/dev/null | grep -o '"source"[[:space:]]*:[[:space:]]*"[^"]*"' | head -n 1 | sed -E 's/^"source"[[:space:]]*:[[:space:]]*"(.*)"$/\1/')"

  if [ -z "$session_id" ]; then
    # Fallback: key the state file on a sanitised $PWD instead.
    session_id="$(printf '%s' "$PWD" | tr -c 'A-Za-z0-9_.-' '_')"
  fi
  if [ -z "$session_id" ]; then
    # $PWD was somehow empty too. Nothing safe to key state on; still roll,
    # just don't persist.
    session_id="_"
  fi

  # --- State directory. Create if absent; if we can't, we simply can't
  #     persist a resume — still roll and announce below. ---
  state_dir="${HOME:-}/.claude/tone-roulette"
  mkdir -p "$state_dir" 2>/dev/null
  state_file=""
  if [ -d "$state_dir" ]; then
    state_file="$state_dir/$session_id"
  fi

  # --- Off token: the /tone skill's "off" switches the tone off by writing
  #     this literal value to the state file rather than deleting it, so
  #     absence keeps meaning "roll" and "off" gets its own representation
  #     (a genuinely missing/unreadable/stale state file still rolls fresh,
  #     unchanged from before). It can never collide with a real tone name:
  #     tone names are catalogue basenames, and the catalogue is asserted to
  #     hold exactly eight of those, none named this. ---
  off_token="__off__"
  is_off=0

  # --- Resume path: only for a non-startup source (resume/clear/compact,
  #     or anything unrecognized). A fresh session (source=startup) always
  #     rolls below, regardless of what a previous session left in the
  #     state file — including a leftover off_token, which must never leak
  #     into a new session. ---
  selected=""
  if [ "$source_val" != "startup" ] && [ -n "$state_file" ] && [ -f "$state_file" ]; then
    existing="$(head -n 1 "$state_file" 2>/dev/null | tr -d '\r\n')"
    if [ "$existing" = "$off_token" ]; then
      is_off=1
    elif [ -n "$existing" ]; then
      for base in "${tones[@]}"; do
        if [ "$base" = "$existing" ]; then
          selected="$existing"
          break
        fi
      done
    fi
  fi

  # --- Off path: the session was explicitly switched off and this isn't a
  #     fresh startup. Print nothing, exit 0 — the session stays untoned. ---
  if [ "$is_off" -eq 1 ]; then
    return 0
  fi

  # --- Roll path: source=startup, or no usable state, or the recorded tone
  #     is stale. `rolled` records whether this run actually rolled a new
  #     tone (true here) or is re-announcing one already in force (false,
  #     set when `selected` came from the resume path above) — the
  #     announcement below says "rolled" only when it's true. ---
  rolled=0
  if [ -z "$selected" ]; then
    idx=$((RANDOM % count))
    selected="${tones[$idx]}"
    rolled=1
    if [ -n "$state_file" ]; then
      { printf '%s\n' "$selected" > "$state_file"; } 2>/dev/null
    fi
  fi

  # --- Prune stale per-session state files (issue #6). Every session that
  #     loads this plugin leaves one ~20-byte file behind forever, because
  #     session ids are UUIDs the handler can never see again to know a
  #     session ended. Age is the only available signal, so this removes
  #     files whose mtime is older than 30 days — chosen generously because
  #     resume/clear/compact (below, and see the resume branch above) only
  #     READ the state file without rewriting it, so a long-running
  #     session's file keeps its original mtime the whole time and must not
  #     look stale just because the session has been open for a while.
  #
  #     Runs only on `startup`, and only after this run's own state_file has
  #     just been persisted above, so it always has a name to protect.
  #     `resume`/`clear`/`compact` never reach here: they are reading state
  #     for a possibly-still-live session, and a prune racing that read is
  #     how a live session loses its tone. Every safety property is
  #     enforced by the find invocation itself, not by trusting its inputs:
  #       - refuses to run at all unless state_dir is a real directory
  #         (empty/unset/non-directory all skip the block below);
  #       - "-maxdepth 1 -type f" never descends and never follows a
  #         symlink (a symlink's find type is its own, not its target's, so
  #         a symlink inside state_dir pointing outside it is never a match
  #         and is never touched);
  #       - "! -name" excludes this session's own file by exact name,
  #         regardless of age;
  #       - "-exec rm -f {} +" (not the non-POSIX "-delete") only ever fires
  #         on paths find itself produced, which are already confined to
  #         state_dir by -maxdepth 1.
  #     Any failure here (permission denied, race with another process,
  #     etc.) is swallowed by the redirect below: this must never be the
  #     reason a session-start hook prints to stderr or exits non-zero.
  if [ "$source_val" = "startup" ] && [ -n "${state_dir:-}" ] && [ -d "$state_dir" ] && [ -n "$state_file" ]; then
    {
      find "$state_dir" -maxdepth 1 -type f -mtime +30 ! -name "$(basename "$state_file")" -exec rm -f {} +
    } 2>/dev/null
  fi

  tone_file="$styles_dir/$selected.md"
  [ -r "$tone_file" ] || return 0

  # --- Strip YAML frontmatter (the two `---` lines and everything between
  #     them), keeping the exact remaining bytes. A trailing sentinel byte
  #     defeats command substitution's trailing-newline stripping so the
  #     body's real trailing newline survives. ---
  body="$(
    {
      awk '
        NR == 1 && $0 == "---" { infm = 1; next }
        infm && $0 == "---"    { infm = 0; next }
        infm                   { next }
        { print }
      ' "$tone_file"
      printf 'X'
    }
  )"
  body="${body%X}"

  # --- JSON-escape the body, in an order where each pass only ever
  #     introduces backslashes that later passes must NOT re-escape:
  #       1. existing backslashes: \ -> \\
  #       2. existing double quotes: " -> \"
  #       3. C0 control characters other than \n (which pass 4 handles):
  #          \t and \r get their short forms, everything else in
  #          U+0000-U+001F becomes \u00XX. (U+0000 itself cannot occur here
  #          in practice: bash command substitution truncates a captured
  #          string at the first NUL byte, so there is nothing left by this
  #          point for the loop below to ever match against 0 — the case is
  #          included anyway so the escaping is complete on its own terms.)
  #       4. real newlines -> literal \n
  #     Shell text processing only, per Global Constraint 3. ---
  escaped_body="$(
    {
      printf '%s' "$body" | sed -e 's/\\/\\\\/g' -e 's/"/\\"/g'
      printf 'X'
    }
  )"
  escaped_body="${escaped_body%X}"

  escaped_body="$(
    {
      printf '%s' "$escaped_body" | awk '
        BEGIN {
          for (c = 0; c <= 31; c++) {
            if (c == 10) continue  # real newline: pass 4 handles it
            ch = sprintf("%c", c)
            if (c == 9)       esc = "\\t"
            else if (c == 13) esc = "\\r"
            else              esc = sprintf("\\u%04x", c)
            ctrl_map[ch] = esc
          }
        }
        {
          line = $0
          out = ""
          n = length(line)
          for (i = 1; i <= n; i++) {
            ch = substr(line, i, 1)
            out = out ((ch in ctrl_map) ? ctrl_map[ch] : ch)
          }
          print out
        }
      '
      printf 'X'
    }
  )"
  escaped_body="${escaped_body%X}"

  escaped_body="$(
    {
      printf '%s' "$escaped_body" | awk '{printf "%s\\n", $0}'
      printf 'X'
    }
  )"
  escaped_body="${escaped_body%X}"

  # --- Announcement: only claim "rolled" when a roll actually happened
  #     this run. A resumed tone (clear/compact/resume with valid state)
  #     did not just get rolled, and saying so was a lie the user had no
  #     way to catch — say "held" instead. The message is never dropped:
  #     after a /clear the user may genuinely not remember which tone is
  #     active, and silence would be worse than a plain restatement. ---
  if [ "$rolled" -eq 1 ]; then
    sys_message="🎲 Tone rolled: ${selected}"
  else
    sys_message="🎲 Tone held: ${selected}"
  fi
  escaped_sys_message="$(printf '%s' "$sys_message" | sed -e 's/\\/\\\\/g' -e 's/"/\\"/g')"

  printf '{"systemMessage":"%s","hookSpecificOutput":{"hookEventName":"SessionStart","additionalContext":"%s"}}' \
    "$escaped_sys_message" "$escaped_body"

  return 0
}

main
exit 0
