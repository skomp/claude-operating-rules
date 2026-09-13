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
  local script_dir styles_dir state_dir input session_id state_file
  local tones=() f base existing selected count idx
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
  #     just means session_id extraction below finds nothing. ---
  input="$(cat 2>/dev/null)"

  # --- Extract session_id without jq: a grep+sed pull of the JSON string
  #     field, per Global Constraint 3 and the brief's Step 0 fallback. ---
  session_id="$(printf '%s' "$input" 2>/dev/null | grep -o '"session_id"[[:space:]]*:[[:space:]]*"[^"]*"' | head -n 1 | sed -E 's/^"session_id"[[:space:]]*:[[:space:]]*"(.*)"$/\1/')"

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
  state_dir="${HOME}/.claude/tone-roulette"
  mkdir -p "$state_dir" 2>/dev/null
  state_file=""
  if [ -d "$state_dir" ]; then
    state_file="$state_dir/$session_id"
  fi

  # --- Resume path: state file names a tone that still exists. ---
  selected=""
  if [ -n "$state_file" ] && [ -f "$state_file" ]; then
    existing="$(head -n 1 "$state_file" 2>/dev/null | tr -d '\r\n')"
    if [ -n "$existing" ]; then
      for base in "${tones[@]}"; do
        if [ "$base" = "$existing" ]; then
          selected="$existing"
          break
        fi
      done
    fi
  fi

  # --- Roll path: no usable state, or the recorded tone is stale. ---
  if [ -z "$selected" ]; then
    idx=$((RANDOM % count))
    selected="${tones[$idx]}"
    if [ -n "$state_file" ]; then
      { printf '%s\n' "$selected" > "$state_file"; } 2>/dev/null
    fi
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

  sys_message="🎲 Tone rolled: ${selected}"
  escaped_sys_message="$(printf '%s' "$sys_message" | sed -e 's/\\/\\\\/g' -e 's/"/\\"/g')"

  printf '{"systemMessage":"%s","hookSpecificOutput":{"hookEventName":"SessionStart","additionalContext":"%s"}}' \
    "$escaped_sys_message" "$escaped_body"

  return 0
}

main
exit 0
