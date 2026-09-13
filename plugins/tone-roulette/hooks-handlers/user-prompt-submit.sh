#!/usr/bin/env bash
#
# tone-roulette UserPromptSubmit handler.
#
# Measures the real gap since the previous user prompt in this session and,
# only when the impatient tone is currently the one in force, injects a
# short factual line via hookSpecificOutput.additionalContext — e.g. "the
# user's previous message in this session was 11 minutes ago" — so the
# impatient tone has something true to be impatient about, rather than
# generic grumbling.
#
# Contract (same as session-start.sh; see
# docs/superpowers/specs/2026-09-13-tone-roulette-design.md):
#   - bash + coreutils only. No jq, no python, no `shuf`.
#   - Every path exits 0. Nothing on stderr, ever.
#   - Costs nothing when the impatient tone is not the one in force: this
#     hook fires on every prompt in every session where the plugin is
#     enabled, so for the other 19 tones and for anyone who has chosen a
#     different output style it must produce no output and do no work
#     beyond the one cheap check that says so. See tone_is_active() in
#     tone-common.sh, which this file shares with session-start.sh rather
#     than keeping a second copy of the "is a style chosen, what tone is
#     this session's state file holding" detection.
#   - Never injects on the first prompt of a session (no previous
#     timestamp to compare against) or when the gap is below
#     GAP_THRESHOLD_SECONDS.
#
# Where the timestamp lives: ${HOME}/.claude/tone-roulette/<session_id>.last-prompt
# — a single line holding the unix time of the prompt before this one. This
# is the same state directory session-start.sh already owns
# (${HOME}/.claude/tone-roulette/); the ".last-prompt" suffix keeps this
# file distinct from session-start.sh's own "$state_dir/$session_id" file,
# whose content (the rolled tone name, or the literal "__off__") several of
# test-handler.sh's assertions compare byte-for-byte against the *whole*
# file — appending a second line to that file for a timestamp would have
# broken every one of those. A sibling file in the same directory avoids
# that without inventing a new state location. session-start.sh's own
# stale-file prune (find ... -mtime +30) also sweeps up an old session's
# leftover ".last-prompt" file the same way it already sweeps up that
# session's tone file, since neither is excluded by name except the
# current run's own tone file.

set -u

_TONE_COMMON_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
_TONE_COMMON_FILE="$_TONE_COMMON_DIR/tone-common.sh"

# --- Guard the source: same reasoning as session-start.sh's identical
#     guard (see its comment for the full rationale) — a missing,
#     unreadable, truncated or otherwise corrupt tone-common.sh must never
#     put a line on stderr or a nonzero exit onto every prompt submitted in
#     every session. Checks the three functions this handler actually
#     calls below (resolve_session_id, tone_state_dir, tone_is_active). ---
if [ ! -r "$_TONE_COMMON_FILE" ]; then
  exit 0
fi
# shellcheck source=./tone-common.sh
. "$_TONE_COMMON_FILE" 2>/dev/null || exit 0
if ! command -v resolve_session_id >/dev/null 2>&1 \
  || ! command -v tone_state_dir >/dev/null 2>&1 \
  || ! command -v tone_is_active >/dev/null 2>&1; then
  exit 0
fi

# --- A gap shorter than this is unremarkable — ordinary time to read a
#     reply and type the next message — and is not worth an impatient
#     remark. Two minutes. Named so the floor is a decision on record, not
#     a bare number buried in an arithmetic comparison. ---
GAP_THRESHOLD_SECONDS=120

# --- format_gap SECONDS: render a whole number of elapsed seconds (already
#     known to be >= GAP_THRESHOLD_SECONDS) as a short phrase in the
#     coarsest unit that stays readable — minutes below an hour, hours
#     below a day, days beyond that — rounded down, correctly pluralised. ---
format_gap() {
  local secs="$1" minutes hours days
  minutes=$(( secs / 60 ))
  if [ "$minutes" -lt 60 ]; then
    if [ "$minutes" -eq 1 ]; then
      printf '1 minute'
    else
      printf '%d minutes' "$minutes"
    fi
    return 0
  fi
  hours=$(( secs / 3600 ))
  if [ "$hours" -lt 24 ]; then
    if [ "$hours" -eq 1 ]; then
      printf '1 hour'
    else
      printf '%d hours' "$hours"
    fi
    return 0
  fi
  days=$(( secs / 86400 ))
  if [ "$days" -eq 1 ]; then
    printf '1 day'
  else
    printf '%d days' "$days"
  fi
}

main() {
  local input session_id state_dir ts_file now prev gap phrase
  local ctx escaped_ctx

  # --- Read stdin (the hook JSON) first — session_id (needed even to know
  #     which state file to check) only ever comes from here. Same
  #     closed-fd guard as session-start.sh: bash reuses a closed fd 0 for
  #     the command substitution's own capture pipe, so testing fd 0 via a
  #     throwaway dup to fd 3 first avoids `cat` blocking forever on a pipe
  #     that never sees EOF. Malformed or empty stdin is never fatal here
  #     either: it just means session_id falls back to $PWD, same as
  #     session-start.sh. ---
  input=""
  if { exec 3<&0; } 2>/dev/null; then
    exec 3<&-
    input="$(cat 2>/dev/null)"
  fi

  session_id="$(resolve_session_id "$input")"
  state_dir="$(tone_state_dir)"

  # --- Stand down entirely unless "impatient" is the tone currently in
  #     force for this session. This must happen before any state file is
  #     touched: every other tone, and every user on a different output
  #     style, costs nothing beyond this one check. ---
  if ! tone_is_active "impatient" "$session_id" "$state_dir"; then
    return 0
  fi

  ts_file="$state_dir/$session_id.last-prompt"
  now="$(date +%s 2>/dev/null)"
  [ -n "$now" ] || return 0

  prev=""
  if [ -f "$ts_file" ]; then
    prev="$(head -n 1 "$ts_file" 2>/dev/null | tr -d '\r\n')"
  fi

  # --- Persist "now" as the reference point for the next prompt,
  #     regardless of whether this run ends up injecting anything below.
  #     mkdir -p is idempotent and cheap; session-start.sh already created
  #     this directory in the normal case, but a hook that only ever fires
  #     on UserPromptSubmit (never SessionStart, e.g. in a test) must not
  #     depend on that. ---
  mkdir -p "$state_dir" 2>/dev/null
  { printf '%s\n' "$now" > "$ts_file"; } 2>/dev/null

  # --- No previous timestamp (first prompt of the session), or a
  #     corrupted one (anything not a plain non-negative integer) — either
  #     way there is nothing valid to compare against. Inject nothing. ---
  case "$prev" in
    ''|*[!0-9]*) return 0 ;;
  esac

  gap=$(( now - prev ))
  [ "$gap" -ge "$GAP_THRESHOLD_SECONDS" ] || return 0

  phrase="$(format_gap "$gap")"
  ctx="Factual note for tone purposes: the user's previous message in this session was ${phrase} ago."
  escaped_ctx="$(printf '%s' "$ctx" | sed -e 's/\\/\\\\/g' -e 's/"/\\"/g')"

  printf '{"hookSpecificOutput":{"hookEventName":"UserPromptSubmit","additionalContext":"%s"}}' "$escaped_ctx"

  return 0
}

main
exit 0
