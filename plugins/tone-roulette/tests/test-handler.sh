#!/usr/bin/env bash
# Tests for the tone-roulette SessionStart handler
# (hooks-handlers/session-start.sh).
#
# Every test points HOME at a fresh temp directory so nothing here ever
# touches the real ~/.claude. Most tests point CLAUDE_PLUGIN_ROOT at the
# real shipped plugin (so STYLES_DIR resolves to the real output-styles/
# catalogue); tests 8 and 10 point it at an isolated fixture root instead,
# so the empty-catalogue and joke-tone-body cases never touch the shipped
# catalogue.
#
# Uses `jq` for assertions (allowed in tests; the handler itself must not
# depend on it). No dependency on `shuf`.

set -u

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PLUGIN_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
HANDLER="$PLUGIN_ROOT/hooks-handlers/session-start.sh"
STYLES_DIR="$PLUGIN_ROOT/output-styles"

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

if [ ! -x "$HANDLER" ] && [ ! -r "$HANDLER" ]; then
  echo "FAIL: handler not found at $HANDLER"
  exit 1
fi

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
  printf 'sid-%s-%s-%s' "$$" "$_id_counter" "$RANDOM"
}

# List the catalogue's tone basenames, one per line.
catalog_tones() {
  local dir="$1" f base
  for f in "$dir"/*.md; do
    [ -e "$f" ] || continue
    base="$(basename "$f" .md)"
    printf '%s\n' "$base"
  done
}

mapfile -t TONES < <(catalog_tones "$STYLES_DIR")
if [ "${#TONES[@]}" -eq 0 ]; then
  echo "FAIL: no tone files found in $STYLES_DIR — cannot run handler tests"
  exit 1
fi

# run_handler HOME ROOT STDIN_STRING > stdout, returns handler's exit code.
run_handler() {
  local home="$1" root="$2" stdin_str="$3"
  printf '%s' "$stdin_str" | HOME="$home" CLAUDE_PLUGIN_ROOT="$root" bash "$HANDLER"
}

state_file_for() {
  local home="$1" sid="$2"
  printf '%s/.claude/tone-roulette/%s' "$home" "$sid"
}

# =====================================================================
# Test 1 — output is valid JSON for a roll.
# =====================================================================
{
  home="$(new_tmp_dir)"
  sid="$(next_session_id)"
  out="$(run_handler "$home" "$PLUGIN_ROOT" "{\"session_id\":\"$sid\",\"source\":\"startup\"}")"
  ec=$?

  check
  if [ "$ec" -eq 0 ] && printf '%s' "$out" | jq . >/dev/null 2>&1; then
    pass "test1: roll produces valid JSON on stdout (exit 0)"
  else
    fail "test1: roll did not produce valid JSON (exit=$ec, out=$out)"
  fi

  TEST1_OUT="$out"
}

# =====================================================================
# Test 2 — .systemMessage is non-empty and names a real tone.
# =====================================================================
{
  sysmsg="$(printf '%s' "$TEST1_OUT" | jq -r '.systemMessage // empty')"

  check
  if [ -z "$sysmsg" ]; then
    fail "test2: .systemMessage is empty"
  else
    matched=""
    for t in "${TONES[@]}"; do
      case "$sysmsg" in
        *"$t"*) matched="$t" ;;
      esac
    done
    if [ -n "$matched" ]; then
      pass "test2: .systemMessage ('$sysmsg') names a real catalog tone ($matched)"
    else
      fail "test2: .systemMessage ('$sysmsg') does not name any catalog tone"
    fi
  fi
}

# =====================================================================
# Test 3 — hookEventName is SessionStart, additionalContext non-empty.
# =====================================================================
{
  event_name="$(printf '%s' "$TEST1_OUT" | jq -r '.hookSpecificOutput.hookEventName // empty')"
  ctx="$(printf '%s' "$TEST1_OUT" | jq -r '.hookSpecificOutput.additionalContext // empty')"

  check
  if [ "$event_name" = "SessionStart" ]; then
    pass "test3: hookSpecificOutput.hookEventName == SessionStart"
  else
    fail "test3: hookSpecificOutput.hookEventName == '$event_name', expected SessionStart"
  fi

  check
  if [ -n "$ctx" ]; then
    pass "test3: .additionalContext is non-empty"
  else
    fail "test3: .additionalContext is empty"
  fi
}

# =====================================================================
# Test 4 — frontmatter is stripped.
#
# Ruling in the dispatch overrides the brief's literal test 4 (which would
# fail a correct handler if a tone body happened to contain the substring
# "name:"). Implemented as: the body must not begin with the `---`
# delimiter, and must not contain the specific line `name: <basename>` for
# the selected tone.
# =====================================================================
{
  home="$(new_tmp_dir)"
  sid="$(next_session_id)"
  out="$(run_handler "$home" "$PLUGIN_ROOT" "{\"session_id\":\"$sid\",\"source\":\"startup\"}")"
  selected="$(cat "$(state_file_for "$home" "$sid")" 2>/dev/null)"
  ctx="$(printf '%s' "$out" | jq -r '.hookSpecificOutput.additionalContext // empty')"
  first3="$(printf '%s' "$ctx" | cut -c1-3)"

  check
  if [ "$first3" != "---" ]; then
    pass "test4: additionalContext does not begin with '---'"
  else
    fail "test4: additionalContext begins with '---' — frontmatter not stripped"
  fi

  check
  if [ -n "$selected" ] && printf '%s\n' "$ctx" | grep -qxF "name: $selected"; then
    fail "test4: additionalContext still contains the frontmatter line 'name: $selected'"
  else
    pass "test4: additionalContext does not contain 'name: $selected'"
  fi
}

# =====================================================================
# Test 5 — randomness is real: 60 fresh rolls, at least 3 distinct tones.
#
# Chosen so a correct implementation (uniform pick among 8 tones) fails
# this bar with probability far below any flakiness budget, while a
# fixed-pick implementation always returns exactly 1 distinct tone and
# always fails it. See task-2-report.md for how this was confirmed
# against a deliberately fixed-pick copy of the handler.
# =====================================================================
{
  declare -A seen=()
  for _i in $(seq 1 60); do
    home="$(new_tmp_dir)"
    sid="$(next_session_id)"
    run_handler "$home" "$PLUGIN_ROOT" "{\"session_id\":\"$sid\",\"source\":\"startup\"}" >/dev/null
    sel="$(cat "$(state_file_for "$home" "$sid")" 2>/dev/null)"
    [ -n "$sel" ] && seen["$sel"]=1
  done
  distinct=${#seen[@]}

  check
  if [ "$distinct" -ge 3 ]; then
    pass "test5: 60 fresh rolls produced $distinct distinct tones (>= 3)"
  else
    fail "test5: 60 fresh rolls produced only $distinct distinct tone(s), expected >= 3"
  fi
}

# =====================================================================
# Test 6 — resume does not re-roll: 20 runs, same known tone each time.
# =====================================================================
{
  home="$(new_tmp_dir)"
  sid="$(next_session_id)"
  known="${TONES[0]}"
  mkdir -p "$(dirname "$(state_file_for "$home" "$sid")")"
  printf '%s\n' "$known" > "$(state_file_for "$home" "$sid")"

  all_same=1
  for _i in $(seq 1 20); do
    out="$(run_handler "$home" "$PLUGIN_ROOT" "{\"session_id\":\"$sid\",\"source\":\"resume\"}")"
    sysmsg="$(printf '%s' "$out" | jq -r '.systemMessage // empty')"
    case "$sysmsg" in
      *"$known"*) ;;
      *) all_same=0 ;;
    esac
  done
  final_state="$(cat "$(state_file_for "$home" "$sid")" 2>/dev/null)"

  check
  if [ "$all_same" -eq 1 ]; then
    pass "test6: 20 resume runs all returned the known tone ($known)"
  else
    fail "test6: at least one of 20 resume runs did not return the known tone ($known)"
  fi

  check
  if [ "$final_state" = "$known" ]; then
    pass "test6: state file still names the known tone after 20 resumes"
  else
    fail "test6: state file was rewritten to '$final_state', expected unchanged '$known'"
  fi
}

# =====================================================================
# Test 7 — stale state recovers: unknown tone in state file triggers a
# fresh roll instead of an error or empty output, and rewrites state.
# =====================================================================
{
  home="$(new_tmp_dir)"
  sid="$(next_session_id)"
  stale="no-such-tone-xyz"
  mkdir -p "$(dirname "$(state_file_for "$home" "$sid")")"
  printf '%s\n' "$stale" > "$(state_file_for "$home" "$sid")"

  out="$(run_handler "$home" "$PLUGIN_ROOT" "{\"session_id\":\"$sid\",\"source\":\"startup\"}")"
  ec=$?
  ctx="$(printf '%s' "$out" | jq -r '.hookSpecificOutput.additionalContext // empty')"
  newval="$(cat "$(state_file_for "$home" "$sid")" 2>/dev/null)"

  check
  if [ "$ec" -eq 0 ] && printf '%s' "$out" | jq . >/dev/null 2>&1 && [ -n "$ctx" ]; then
    pass "test7: stale state produces a valid, non-empty roll rather than an error"
  else
    fail "test7: stale state did not recover cleanly (exit=$ec, out=$out)"
  fi

  check
  is_real=0
  for t in "${TONES[@]}"; do
    [ "$t" = "$newval" ] && is_real=1
  done
  if [ "$newval" != "$stale" ] && [ "$is_real" -eq 1 ]; then
    pass "test7: state file was rewritten to a real tone ($newval)"
  else
    fail "test7: state file after recovery is '$newval', expected a real tone != '$stale'"
  fi
}

# =====================================================================
# Test 8 — empty output-styles/ directory: no stdout, exit code 0.
# =====================================================================
{
  empty_root="$(new_tmp_dir)"
  mkdir -p "$empty_root/output-styles"
  home="$(new_tmp_dir)"
  sid="$(next_session_id)"

  out="$(run_handler "$home" "$empty_root" "{\"session_id\":\"$sid\",\"source\":\"startup\"}")"
  ec=$?

  check
  if [ -z "$out" ] && [ "$ec" -eq 0 ]; then
    pass "test8: empty catalogue produces no stdout and exit 0"
  else
    fail "test8: empty catalogue gave exit=$ec, out='$out' (expected empty output, exit 0)"
  fi
}

# =====================================================================
# Test 9 — malformed / empty stdin: exit code 0 either way.
# =====================================================================
{
  home="$(new_tmp_dir)"
  out="$(printf 'not { valid ] json at all' | HOME="$home" CLAUDE_PLUGIN_ROOT="$PLUGIN_ROOT" bash "$HANDLER" 2>/dev/null)"
  ec=$?

  check
  if [ "$ec" -eq 0 ]; then
    pass "test9: malformed (non-JSON) stdin still exits 0"
  else
    fail "test9: malformed stdin exited $ec, expected 0"
  fi

  home2="$(new_tmp_dir)"
  out2="$(printf '' | HOME="$home2" CLAUDE_PLUGIN_ROOT="$PLUGIN_ROOT" bash "$HANDLER" 2>/dev/null)"
  ec2=$?

  check
  if [ "$ec2" -eq 0 ]; then
    pass "test9: empty stdin still exits 0"
  else
    fail "test9: empty stdin exited $ec2, expected 0"
  fi
}

# =====================================================================
# Test 10 — a tone file with `"`, `\`, a literal newline, a literal TAB
# and another C0 control character round-trips: emitted JSON parses and
# .additionalContext reproduces the body exactly.
#
# The fixture is built here, in the test's own temp directory — no joke
# tone file is added to the shipped catalogue. Built with printf (not a
# quoted heredoc) so the tab (\t) and unit-separator (\x1f) control bytes
# actually land in the file as real bytes, not as their two-character
# spellings.
# =====================================================================
{
  fixture_root="$(new_tmp_dir)"
  mkdir -p "$fixture_root/output-styles"
  fixture_file="$fixture_root/output-styles/fixture-tone.md"

  {
    printf -- '---\n'
    printf -- 'name: fixture-tone\n'
    printf -- 'description: Round-trip escaping fixture for test-handler.sh.\n'
    printf -- '---\n'
    printf -- '\n'
    printf -- 'He said "hello" and meant it, then typed C:\\path\\to\\file without flinching.\n'
    printf -- 'A lone backslash \\ and a "quoted phrase" share this second line on purpose.\n'
    printf -- 'Column1\tColumn2\tColumn3 has a literal TAB between fields.\n'
    printf -- 'A unit-separator control character sits right here: \x1f — and then text.\n'
  } > "$fixture_file"

  # Expected body: same frontmatter-stripping rule the handler documents
  # (strip the two `---` lines and everything between them), applied here
  # with a plain awk one-liner — not the handler's own escaping logic —
  # so this is an independent check, not a restatement of it.
  expected_body_file="$(new_tmp_dir)/expected-body"
  awk '
    NR == 1 && $0 == "---" { infm = 1; next }
    infm && $0 == "---"    { infm = 0; next }
    infm                   { next }
    { print }
  ' "$fixture_file" > "$expected_body_file"

  home="$(new_tmp_dir)"
  sid="$(next_session_id)"
  out_file="$(new_tmp_dir)/handler-out.json"
  printf '{"session_id":"%s","source":"startup"}' "$sid" \
    | HOME="$home" CLAUDE_PLUGIN_ROOT="$fixture_root" bash "$HANDLER" > "$out_file"
  ec=$?

  check
  if [ "$ec" -eq 0 ] && jq . "$out_file" >/dev/null 2>&1; then
    pass "test10: fixture tone produces valid, parseable JSON"
  else
    fail "test10: fixture tone handler run failed (exit=$ec)"
  fi

  actual_body_file="$(new_tmp_dir)/actual-body"
  # -j: raw output, no implicit trailing newline added by jq, so this is
  # exactly the bytes of the JSON string value — a fair byte-for-byte
  # comparison against the plain-file expected_body_file above.
  jq -j '.hookSpecificOutput.additionalContext' "$out_file" > "$actual_body_file" 2>/dev/null

  check
  if diff -q "$expected_body_file" "$actual_body_file" >/dev/null 2>&1; then
    pass "test10: .additionalContext reproduces the fixture body exactly (quotes, backslash, newline)"
  else
    fail "test10: .additionalContext does not match the fixture body exactly"
    echo "  --- expected ---"
    cat "$expected_body_file"
    echo "  --- actual ---"
    cat "$actual_body_file"
  fi
}

echo ""
echo "Ran $check_count assertions."
if [ "$fail_count" -gt 0 ]; then
  echo "RESULT: FAILED ($fail_count failing assertion(s))"
  exit 1
fi

echo "RESULT: ALL CHECKS PASSED"
exit 0
