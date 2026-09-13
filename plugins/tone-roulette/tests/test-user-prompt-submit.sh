#!/usr/bin/env bash
# Tests for the tone-roulette UserPromptSubmit handler
# (hooks-handlers/user-prompt-submit.sh).
#
# Kept in its own file rather than folded into test-handler.sh: that file's
# own header says it tests "the tone-roulette SessionStart handler"
# specifically (hooks-handlers/session-start.sh), the two handlers are
# fired by different hook events with different stdin shapes and different
# jobs (roll/hold a tone vs. measure a gap between prompts), and this
# handler's own "cost nothing unless impatient is active" contract is
# exactly the kind of property worth being able to run, read and reason
# about on its own — folding it into an already-1200-line file would make
# both harder to audit, for no shared fixture this file actually needs.
#
# Every test points HOME at a fresh temp directory so nothing here ever
# touches the real ~/.claude. A snapshot of the real
# ~/.claude/tone-roulette/ directory is taken before the first test and
# compared again after the last one (see the final block) so a HOME leak
# anywhere in between would be caught, not just asserted away by
# construction.
#
# Uses `jq` for assertions (allowed in tests; the handler itself must not
# depend on it — see its own header). No dependency on `shuf`.
#
# Requires bash 4+ (mapfile). The handler itself has no such dependency;
# see test-handler.sh's header for the same bash-3.2-cleanliness note,
# which applies here too since this handler sources the same
# tone-common.sh session-start.sh does.

set -u

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PLUGIN_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
HANDLER="$PLUGIN_ROOT/hooks-handlers/user-prompt-submit.sh"
REAL_HOME="$HOME"
REAL_STATE_DIR="$REAL_HOME/.claude/tone-roulette"

fail_count=0
check_count=0

fail() {
  echo "FAIL: $1"
  fail_count=$((fail_count + 1))
}

pass() {
  echo "PASS: $1"
}

check() {
  check_count=$((check_count + 1))
}

if [ ! -r "$HANDLER" ]; then
  echo "FAIL: handler not found at $HANDLER"
  exit 1
fi

# --- Snapshot the real state directory before touching anything, so the
#     final block can prove nothing here ever wrote to it. `ls -la` plus
#     content hashes would be stronger, but this directory is meant to
#     hold nothing but tiny per-session text files, so a recursive find
#     listing (name + size + mtime) is already sensitive to an add, a
#     remove, or a modified file, without depending on a checksum tool
#     that may not be on PATH. ---
snapshot_real_state_dir() {
  if [ -d "$REAL_STATE_DIR" ]; then
    find "$REAL_STATE_DIR" -mindepth 0 -exec sh -c 'stat -f "%N %z %m" "$1" 2>/dev/null || stat -c "%n %s %Y" "$1" 2>/dev/null' _ {} \; 2>/dev/null | sort
  else
    printf '(absent)\n'
  fi
}
REAL_STATE_BEFORE="$(snapshot_real_state_dir)"

# --- Fixture directories, cleaned up on exit. ---
TMP_ROOTS=()
cleanup() {
  local d
  for d in "${TMP_ROOTS[@]:-}"; do
    [ -n "$d" ] && rm -rf "$d"
  done
}
trap cleanup EXIT

new_tmp_dir() {
  local d
  d="$(mktemp -d)"
  TMP_ROOTS+=("$d")
  printf '%s' "$d"
}

_id_counter=0
next_session_id() {
  _id_counter=$((_id_counter + 1))
  printf 'ups-%s-%s-%s' "$$" "$_id_counter" "$RANDOM"
}

# A project directory with no .claude/settings*.json in it at all — the
# default CLAUDE_PROJECT_DIR for every run_handler call that doesn't pass
# its own, exactly like test-handler.sh's DEFAULT_PROJECT_DIR, and for the
# same reason: without it, an unset CLAUDE_PROJECT_DIR falls back to the
# handler's $PWD, wherever this file happens to be invoked from.
DEFAULT_PROJECT_DIR="$(new_tmp_dir)"

# run_handler HOME STDIN_STRING [PROJECT_DIR] > stdout, returns the
# handler's exit code. PROJECT_DIR defaults to DEFAULT_PROJECT_DIR (no
# settings files, so no outputStyle key) when omitted.
run_handler() {
  local home="$1" stdin_str="$2" project_dir="${3:-$DEFAULT_PROJECT_DIR}"
  printf '%s' "$stdin_str" | HOME="$home" CLAUDE_PROJECT_DIR="$project_dir" bash "$HANDLER"
}

state_dir_for() {
  printf '%s/.claude/tone-roulette' "$1"
}

tone_file_for() {
  printf '%s/.claude/tone-roulette/%s' "$1" "$2"
}

ts_file_for() {
  printf '%s/.claude/tone-roulette/%s.last-prompt' "$1" "$2"
}

write_tone() {
  local home="$1" sid="$2" tone="$3"
  mkdir -p "$(state_dir_for "$home")"
  printf '%s\n' "$tone" > "$(tone_file_for "$home" "$sid")"
}

# write_ts HOME SID SECONDS_AGO: write a last-prompt timestamp file dated
# SECONDS_AGO seconds before "now" as observed in *this* shell, immediately
# before handing control to the handler — the handler takes its own
# independent "now" a moment later, so any margin under a couple of
# seconds is a real race. Callers use generous margins (tens of seconds at
# least) around the GAP_THRESHOLD_SECONDS boundary specifically so that
# unavoidable process-start jitter can never flip a test's expected
# outcome; see the threshold tests below for why each margin was chosen.
write_ts() {
  local home="$1" sid="$2" seconds_ago="$3" now
  mkdir -p "$(state_dir_for "$home")"
  now="$(date +%s)"
  printf '%s\n' "$((now - seconds_ago))" > "$(ts_file_for "$home" "$sid")"
}

project_with_output_style() {
  local dir style
  dir="$(new_tmp_dir)"
  style="$1"
  mkdir -p "$dir/.claude"
  printf '{"outputStyle":"%s"}\n' "$style" > "$dir/.claude/settings.local.json"
  printf '%s' "$dir"
}

# =====================================================================
# Test 1 — a different rolled tone is active: no output, exit 0, and the
# per-session timestamp file is left exactly as it was (cost nothing).
# =====================================================================
{
  home="$(new_tmp_dir)"
  sid="$(next_session_id)"
  write_tone "$home" "$sid" "pirate"
  write_ts "$home" "$sid" 900
  before="$(cat "$(ts_file_for "$home" "$sid")")"

  out="$(run_handler "$home" "{\"session_id\":\"$sid\"}")"
  ec=$?
  after="$(cat "$(ts_file_for "$home" "$sid")" 2>/dev/null)"

  check
  if [ "$ec" -eq 0 ] && [ -z "$out" ]; then
    pass "test1: a different rolled tone (pirate) produces no output, exit 0"
  else
    fail "test1: expected silence and exit 0 with tone=pirate (ec=$ec, out=[$out])"
  fi

  check
  if [ "$after" = "$before" ]; then
    pass "test1: the timestamp file is left untouched when the active tone isn't impatient"
  else
    fail "test1: timestamp file changed even though the active tone wasn't impatient (before=$before after=$after)"
  fi
}

# =====================================================================
# Test 2 — an output style other than impatient is explicitly chosen (via
# settings.local.json), even though a stale state file still says
# "impatient": the chosen style pre-empts the rolled one, so still silent.
# =====================================================================
{
  home="$(new_tmp_dir)"
  sid="$(next_session_id)"
  write_tone "$home" "$sid" "impatient"
  write_ts "$home" "$sid" 900
  proj="$(project_with_output_style "pirate")"

  out="$(run_handler "$home" "{\"session_id\":\"$sid\"}" "$proj")"
  ec=$?

  check
  if [ "$ec" -eq 0 ] && [ -z "$out" ]; then
    pass "test2: outputStyle=pirate stands the hook down even with a stale impatient state file"
  else
    fail "test2: expected silence with a chosen non-impatient style (ec=$ec, out=[$out])"
  fi
}

# =====================================================================
# Test 3 — outputStyle=impatient chosen explicitly (no per-session rolled
# state file at all): the chosen style alone is enough to activate.
# =====================================================================
{
  home="$(new_tmp_dir)"
  sid="$(next_session_id)"
  mkdir -p "$(state_dir_for "$home")"
  write_ts "$home" "$sid" 700
  proj="$(project_with_output_style "impatient")"

  out="$(run_handler "$home" "{\"session_id\":\"$sid\"}" "$proj")"
  ec=$?
  ctx="$(printf '%s' "$out" | jq -r '.hookSpecificOutput.additionalContext // empty' 2>/dev/null)"

  check
  case "$ctx" in
    *"11 minutes"*)
      pass "test3: an explicitly chosen impatient output style activates the hook with no rolled state file"
      ;;
    *)
      fail "test3: expected an injection with outputStyle=impatient and no state file (ec=$ec, out=[$out])"
      ;;
  esac
}

# =====================================================================
# Test 4 — no output on the first prompt of a session: impatient is
# active (rolled) but no previous timestamp exists yet. A timestamp file
# must still be created for the *next* prompt to compare against.
# =====================================================================
{
  home="$(new_tmp_dir)"
  sid="$(next_session_id)"
  write_tone "$home" "$sid" "impatient"

  out="$(run_handler "$home" "{\"session_id\":\"$sid\"}")"
  ec=$?

  check
  if [ "$ec" -eq 0 ] && [ -z "$out" ]; then
    pass "test4: the first prompt of a session produces no output even with impatient active"
  else
    fail "test4: expected silence on a first prompt (ec=$ec, out=[$out])"
  fi

  check
  if [ -f "$(ts_file_for "$home" "$sid")" ]; then
    pass "test4: a timestamp file is written after the first prompt, for the next one to compare against"
  else
    fail "test4: no timestamp file was written after the first prompt"
  fi
}

# =====================================================================
# Test 5 — a gap comfortably below GAP_THRESHOLD_SECONDS: no output.
# 30 seconds is used rather than a value just under the threshold so
# ordinary process-start jitter between this test writing the timestamp
# and the handler reading it can never accidentally push the measured gap
# over the line.
# =====================================================================
{
  home="$(new_tmp_dir)"
  sid="$(next_session_id)"
  write_tone "$home" "$sid" "impatient"
  write_ts "$home" "$sid" 30

  out="$(run_handler "$home" "{\"session_id\":\"$sid\"}")"
  ec=$?

  check
  if [ "$ec" -eq 0 ] && [ -z "$out" ]; then
    pass "test5: a 30-second gap (below GAP_THRESHOLD_SECONDS) produces no output"
  else
    fail "test5: expected silence for a sub-threshold gap (ec=$ec, out=[$out])"
  fi
}

# =====================================================================
# Test 6 — a gap comfortably above GAP_THRESHOLD_SECONDS: valid JSON,
# hookEventName is "UserPromptSubmit", additionalContext names the gap in
# minutes, exit 0.
# =====================================================================
{
  home="$(new_tmp_dir)"
  sid="$(next_session_id)"
  write_tone "$home" "$sid" "impatient"
  write_ts "$home" "$sid" 660   # 11 minutes

  out="$(run_handler "$home" "{\"session_id\":\"$sid\"}")"
  ec=$?

  check
  if [ "$ec" -eq 0 ] && printf '%s' "$out" | jq . >/dev/null 2>&1; then
    pass "test6: an above-threshold gap produces valid JSON on stdout, exit 0"
  else
    fail "test6: expected valid JSON for an above-threshold gap (ec=$ec, out=$out)"
  fi

  event_name="$(printf '%s' "$out" | jq -r '.hookSpecificOutput.hookEventName // empty' 2>/dev/null)"
  check
  if [ "$event_name" = "UserPromptSubmit" ]; then
    pass "test6: hookSpecificOutput.hookEventName is UserPromptSubmit"
  else
    fail "test6: expected hookEventName UserPromptSubmit, got '$event_name'"
  fi

  ctx="$(printf '%s' "$out" | jq -r '.hookSpecificOutput.additionalContext // empty' 2>/dev/null)"
  check
  case "$ctx" in
    *"11 minutes"*)
      pass "test6: additionalContext names the real gap (\"11 minutes\")"
      ;;
    *)
      fail "test6: additionalContext did not name the gap in minutes (got: $ctx)"
      ;;
  esac
}

# =====================================================================
# Test 7 — the boundary is inclusive: a gap of exactly
# GAP_THRESHOLD_SECONDS injects. Written the instant before invoking the
# handler; any jitter can only make the measured gap larger, never
# smaller, so this can never flip from "injects" to "silent".
# =====================================================================
{
  home="$(new_tmp_dir)"
  sid="$(next_session_id)"
  write_tone "$home" "$sid" "impatient"
  write_ts "$home" "$sid" 120

  out="$(run_handler "$home" "{\"session_id\":\"$sid\"}")"
  ec=$?

  check
  if [ "$ec" -eq 0 ] && printf '%s' "$out" | jq -e '.hookSpecificOutput.additionalContext' >/dev/null 2>&1; then
    pass "test7: a gap of exactly the threshold (120s) still injects"
  else
    fail "test7: expected an injection at the exact threshold (ec=$ec, out=[$out])"
  fi
}

# =====================================================================
# Test 8 — an hour-scale gap is phrased in hours, not minutes.
# =====================================================================
{
  home="$(new_tmp_dir)"
  sid="$(next_session_id)"
  write_tone "$home" "$sid" "impatient"
  write_ts "$home" "$sid" 7200   # 2 hours

  out="$(run_handler "$home" "{\"session_id\":\"$sid\"}")"
  ctx="$(printf '%s' "$out" | jq -r '.hookSpecificOutput.additionalContext // empty' 2>/dev/null)"

  check
  case "$ctx" in
    *"2 hours"*)
      pass "test8: a 2-hour gap is phrased in hours"
      ;;
    *)
      fail "test8: expected \"2 hours\" in additionalContext, got: $ctx"
      ;;
  esac
}

# =====================================================================
# Test 9 — malformed stdin: exit 0, nothing on stdout or stderr (still
# impatient-active with a big gap, so the only reason for silence here can
# be the malformed-input handling, not the activation check).
# =====================================================================
{
  home="$(new_tmp_dir)"
  sid="$(next_session_id)"
  write_tone "$home" "$sid" "impatient"
  write_ts "$home" "$sid" 900

  err_file="$(new_tmp_dir)/stderr9"
  out="$(printf '%s' "not json at all {{{ \"session_id\"" | HOME="$home" CLAUDE_PROJECT_DIR="$DEFAULT_PROJECT_DIR" bash "$HANDLER" 2>"$err_file")"
  ec=$?
  err="$(cat "$err_file")"

  check
  if [ "$ec" -eq 0 ] && [ -z "$err" ]; then
    pass "test9: malformed stdin exits 0 with empty stderr"
  else
    fail "test9: malformed stdin should exit 0 with empty stderr (ec=$ec, stderr=[$err])"
  fi
}

# =====================================================================
# Test 10 — empty stdin: exit 0, empty stderr.
# =====================================================================
{
  home="$(new_tmp_dir)"
  err_file="$(new_tmp_dir)/stderr10"
  out="$(printf '' | HOME="$home" CLAUDE_PROJECT_DIR="$DEFAULT_PROJECT_DIR" bash "$HANDLER" 2>"$err_file")"
  ec=$?
  err="$(cat "$err_file")"

  check
  if [ "$ec" -eq 0 ] && [ -z "$err" ]; then
    pass "test10: empty stdin exits 0 with empty stderr"
  else
    fail "test10: empty stdin should exit 0 with empty stderr (ec=$ec, stderr=[$err])"
  fi
}

# =====================================================================
# Test 11 — closed stdin (fd 0 closed, no writer at all): exit 0, empty
# stderr, and it must return promptly rather than hang.
# =====================================================================
{
  home="$(new_tmp_dir)"
  err_file="$(new_tmp_dir)/stderr11"
  out="$(HOME="$home" CLAUDE_PROJECT_DIR="$DEFAULT_PROJECT_DIR" bash "$HANDLER" <&- 2>"$err_file")"
  ec=$?
  err="$(cat "$err_file")"

  check
  if [ "$ec" -eq 0 ] && [ -z "$err" ]; then
    pass "test11: closed stdin exits 0 with empty stderr"
  else
    fail "test11: closed stdin should exit 0 with empty stderr (ec=$ec, stderr=[$err])"
  fi
}

# =====================================================================
# Test 12 — no session_id in stdin at all, and no CLAUDE_PROJECT_DIR
# override in play: falls back to a $PWD-keyed state file (same fallback
# session-start.sh has always used) rather than erroring. Exercised here
# by pre-seeding that same fallback key (a sanitised $PWD) with an
# impatient tone and an old timestamp, then confirming an injection
# happens despite session_id being absent from stdin.
# =====================================================================
{
  home="$(new_tmp_dir)"
  pwd_sid="$(printf '%s' "$PWD" | tr -c 'A-Za-z0-9_.-' '_')"
  write_tone "$home" "$pwd_sid" "impatient"
  write_ts "$home" "$pwd_sid" 900

  out="$(run_handler "$home" '{"prompt":"no session id here"}')"
  ec=$?

  check
  if [ "$ec" -eq 0 ] && printf '%s' "$out" | jq -e '.hookSpecificOutput.additionalContext' >/dev/null 2>&1; then
    pass "test12: a missing session_id falls back to a \$PWD-keyed state file, same as session-start.sh"
  else
    fail "test12: expected the \$PWD fallback to find the impatient state (ec=$ec, out=[$out])"
  fi
}

# =====================================================================
# Test 13 — no output when no tone is active at all (no state file, no
# chosen style): silent, exit 0, no timestamp file written either
# (nothing to be impatient about, and nothing to persist).
# =====================================================================
{
  home="$(new_tmp_dir)"
  sid="$(next_session_id)"

  out="$(run_handler "$home" "{\"session_id\":\"$sid\"}")"
  ec=$?

  check
  if [ "$ec" -eq 0 ] && [ -z "$out" ]; then
    pass "test13: no tone active at all produces no output"
  else
    fail "test13: expected silence with nothing active (ec=$ec, out=[$out])"
  fi

  check
  if [ ! -e "$(ts_file_for "$home" "$sid")" ]; then
    pass "test13: no timestamp file is written when no tone is active"
  else
    fail "test13: a timestamp file was written even though no tone was active"
  fi
}

# =====================================================================
# Test 14 — a missing tone-common.sh must not turn every prompt submitted
# into stderr noise. A copy of the handler in a fixture directory with no
# sibling tone-common.sh (simulating a partial install) must produce
# empty stdout, empty stderr, and exit 0 — see the design spec's Error
# handling table row for "Shared helper file missing or unreadable". A
# tone is set up as "impatient" with a large gap in the *real* HOME first,
# so a version without the guard would actually reach the code that calls
# the now-undefined functions, rather than happening to stay silent for
# an unrelated reason (no tone active).
# =====================================================================
{
  fixture_dir="$(new_tmp_dir)/hooks-handlers"
  mkdir -p "$fixture_dir"
  cp "$HANDLER" "$fixture_dir/user-prompt-submit.sh"
  # deliberately: no tone-common.sh copied alongside it

  home="$(new_tmp_dir)"
  sid="$(next_session_id)"
  write_tone "$home" "$sid" "impatient"
  write_ts "$home" "$sid" 900

  err_file="$(new_tmp_dir)/stderr14"
  out="$(printf '{"session_id":"%s"}' "$sid" \
    | HOME="$home" CLAUDE_PROJECT_DIR="$DEFAULT_PROJECT_DIR" \
      bash "$fixture_dir/user-prompt-submit.sh" 2>"$err_file")"
  ec=$?
  err="$(cat "$err_file" 2>/dev/null)"

  check
  if [ "$ec" -eq 0 ] && [ -z "$out" ] && [ -z "$err" ]; then
    pass "test14: missing tone-common.sh produces empty stdout, empty stderr, exit 0"
  else
    fail "test14: missing tone-common.sh gave exit=$ec, stdout='$out', stderr='$err'"
  fi
}

# =====================================================================
# Test 15 — a tone-common.sh truncated mid-function is syntactically
# broken, so `source` itself fails (a parse error, reported before any of
# the file executes) — the "corrupt" half of the missing-or-unreadable
# row. Same impatient-tone-plus-gap setup as test 14, so an unguarded
# version would actually attempt the now-undefined functions.
# =====================================================================
{
  fixture_dir="$(new_tmp_dir)/hooks-handlers"
  mkdir -p "$fixture_dir"
  cp "$HANDLER" "$fixture_dir/user-prompt-submit.sh"
  head -c 400 "$PLUGIN_ROOT/hooks-handlers/tone-common.sh" > "$fixture_dir/tone-common.sh"

  home="$(new_tmp_dir)"
  sid="$(next_session_id)"
  write_tone "$home" "$sid" "impatient"
  write_ts "$home" "$sid" 900

  err_file="$(new_tmp_dir)/stderr15"
  out="$(printf '{"session_id":"%s"}' "$sid" \
    | HOME="$home" CLAUDE_PROJECT_DIR="$DEFAULT_PROJECT_DIR" \
      bash "$fixture_dir/user-prompt-submit.sh" 2>"$err_file")"
  ec=$?
  err="$(cat "$err_file" 2>/dev/null)"

  check
  if [ "$ec" -eq 0 ] && [ -z "$out" ] && [ -z "$err" ]; then
    pass "test15: a tone-common.sh truncated into a syntax error produces empty stdout, empty stderr, exit 0"
  else
    fail "test15: truncated (syntax-broken) tone-common.sh gave exit=$ec, stdout='$out', stderr='$err'"
  fi
}

# =====================================================================
# Test 16 — a tone-common.sh that sources cleanly (no syntax error) but
# defines none of the functions this handler needs — the case a
# truncation lands on a clean statement boundary, which a bare "did the
# source succeed" check alone would not catch. Only a by-name check
# catches this one. Same impatient-tone-plus-gap setup as test 14/15.
# =====================================================================
{
  fixture_dir="$(new_tmp_dir)/hooks-handlers"
  mkdir -p "$fixture_dir"
  cp "$HANDLER" "$fixture_dir/user-prompt-submit.sh"
  printf '#!/usr/bin/env bash\n# corrupted: no functions defined\n' > "$fixture_dir/tone-common.sh"

  home="$(new_tmp_dir)"
  sid="$(next_session_id)"
  write_tone "$home" "$sid" "impatient"
  write_ts "$home" "$sid" 900

  err_file="$(new_tmp_dir)/stderr16"
  out="$(printf '{"session_id":"%s"}' "$sid" \
    | HOME="$home" CLAUDE_PROJECT_DIR="$DEFAULT_PROJECT_DIR" \
      bash "$fixture_dir/user-prompt-submit.sh" 2>"$err_file")"
  ec=$?
  err="$(cat "$err_file" 2>/dev/null)"

  check
  if [ "$ec" -eq 0 ] && [ -z "$out" ] && [ -z "$err" ]; then
    pass "test16: a functionless (but syntactically valid) tone-common.sh produces empty stdout, empty stderr, exit 0"
  else
    fail "test16: functionless tone-common.sh gave exit=$ec, stdout='$out', stderr='$err'"
  fi
}

# =====================================================================
# Test 17 — normal operation is unaffected: a handler copy with its real,
# intact sibling tone-common.sh alongside it still injects exactly as
# before, for an impatient session past the gap threshold. Confirms the
# guard added around the source is inert when the sourced file is fine —
# tests 1-13 already prove this against HANDLER directly; this proves the
# *copied* handler (same guard, fresh process, fresh fixture dir) behaves
# identically.
# =====================================================================
{
  fixture_dir="$(new_tmp_dir)/hooks-handlers"
  mkdir -p "$fixture_dir"
  cp "$HANDLER" "$fixture_dir/user-prompt-submit.sh"
  cp "$PLUGIN_ROOT/hooks-handlers/tone-common.sh" "$fixture_dir/tone-common.sh"

  home="$(new_tmp_dir)"
  sid="$(next_session_id)"
  write_tone "$home" "$sid" "impatient"
  write_ts "$home" "$sid" 660   # 11 minutes

  out="$(printf '{"session_id":"%s"}' "$sid" \
    | HOME="$home" CLAUDE_PROJECT_DIR="$DEFAULT_PROJECT_DIR" \
      bash "$fixture_dir/user-prompt-submit.sh")"
  ec=$?
  ctx="$(printf '%s' "$out" | jq -r '.hookSpecificOutput.additionalContext // empty' 2>/dev/null)"

  check
  case "$ctx" in
    *"11 minutes"*)
      pass "test17: with an intact sibling tone-common.sh, the source guard does not change normal injection behaviour"
      ;;
    *)
      fail "test17: expected a normal 11-minute injection with an intact tone-common.sh, got exit=$ec out=$out"
      ;;
  esac
}

echo "Checked $check_count assertions in $SCRIPT_DIR/test-user-prompt-submit.sh."

# =====================================================================
# Final check — the real ~/.claude/tone-roulette/ directory gained and
# lost nothing across this entire run. Every test above pointed HOME at a
# fresh temp directory; this is what proves that held, rather than just
# asserting it by construction.
# =====================================================================
REAL_STATE_AFTER="$(snapshot_real_state_dir)"
check
if [ "$REAL_STATE_AFTER" = "$REAL_STATE_BEFORE" ]; then
  pass "final: the real ~/.claude/tone-roulette/ directory is unchanged"
else
  fail "final: the real ~/.claude/tone-roulette/ directory changed during this test run"
fi

echo "Checked $check_count assertions total."

if [ "$fail_count" -gt 0 ]; then
  echo "RESULT: FAILED ($fail_count failing assertion(s))"
  exit 1
else
  echo "RESULT: ALL CHECKS PASSED"
  exit 0
fi
