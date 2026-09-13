#!/usr/bin/env bash
# Tests for the tone-roulette output-style catalogue.
#
# Verifies:
#   1. Exactly seventeen .md files exist in output-styles/.
#   2. Every file's frontmatter `name` equals its basename without `.md`.
#   3. Every file contains the ground-rules block byte-for-byte (a single
#      constant below, never retyped per file).
#   4. No file contains the string `force-for-plugin`.
#   5. Every file has a non-empty `## Voice` section.
#   6. (bonus) Frontmatter carries exactly the two keys `name` and
#      `description` — nothing else.
#
# No dependency on `shuf`. May use `jq`, but does not need to for this file
# format (YAML frontmatter, not JSON).
#
# Unlike its sibling test-handler.sh, this file has no bash 4 dependency
# (no `mapfile`, no `declare -A`) and has been verified to run cleanly
# under bash 3.2, the version macOS ships at /bin/bash (issue #7 item 2).
# The handler is likewise clean under 3.2 — see test-handler.sh's header.

set -u

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
STYLES_DIR="$SCRIPT_DIR/../output-styles"

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

# The ground-rules block, byte-for-byte, as specified in
# docs/superpowers/specs/2026-09-13-tone-roulette-design.md.
# This is the ONE place this text is retyped; every file is compared
# against this constant rather than against each other.
EXPECTED_GROUND_RULES=$(cat <<'BLOCK'
This tone governs conversational prose only — what you say to the user in chat.

It never touches code, identifiers, comments, commit messages, pull request descriptions,
issue titles and bodies, file contents, shell commands, or tool arguments. Those stay in
normal professional English.

The tone never costs accuracy. If staying in character would require vagueness, hedging or
invention, drop the voice for that sentence and be plain. Being right outranks the bit.
BLOCK
)

if [ ! -d "$STYLES_DIR" ]; then
  fail "output-styles directory not found at $STYLES_DIR"
  exit 1
fi

# --- Check 1: exactly seventeen .md files ---
check
md_files=("$STYLES_DIR"/*.md)
md_count=${#md_files[@]}
if [ "$md_count" -eq 17 ]; then
  pass "exactly seventeen .md files exist in output-styles/ ($md_count found)"
else
  fail "expected exactly 17 .md files in output-styles/, found $md_count"
fi

# --- Per-file checks 2, 3, 4, 5, 6 ---
for f in "${md_files[@]}"; do
  [ -e "$f" ] || continue
  base="$(basename "$f" .md)"

  # --- Check 2: frontmatter name == basename ---
  check
  fm_name=$(awk -F': ' '/^name:/{print $2; exit}' "$f")
  if [ "$fm_name" = "$base" ]; then
    pass "$base: frontmatter name matches filename"
  else
    fail "$base: frontmatter name '$fm_name' does not match filename '$base'"
  fi

  # --- Check 3: ground-rules block byte-for-byte ---
  check
  actual_ground_rules=$(awk '
    /^## Ground rules$/ {flag=1; next}
    /^## Voice$/ {flag=0}
    flag
  ' "$f" | tail -n +2)
  if [ "$actual_ground_rules" = "$EXPECTED_GROUND_RULES" ]; then
    pass "$base: ground-rules block is byte-for-byte identical"
  else
    fail "$base: ground-rules block does not match the expected constant"
  fi

  # --- Check 4: no 'force-for-plugin' string anywhere in the file ---
  check
  if grep -q "force-for-plugin" "$f"; then
    fail "$base: contains forbidden string 'force-for-plugin'"
  else
    pass "$base: does not contain 'force-for-plugin'"
  fi

  # --- Check 5: non-empty ## Voice section ---
  check
  voice_body=$(awk '/^## Voice$/{flag=1; next} flag' "$f" | tr -d '[:space:]')
  if [ -n "$voice_body" ]; then
    pass "$base: ## Voice section is non-empty"
  else
    fail "$base: ## Voice section is missing or empty"
  fi

  # --- Check 6 (bonus): frontmatter has exactly the keys name, description ---
  check
  fm_keys=$(awk '
    NR==1 { if ($0 != "---") { print "BADSTART"; exit } ; next }
    /^---$/ { exit }
    /^[A-Za-z_-]+:/ { split($0, parts, ":"); print parts[1] }
  ' "$f")
  expected_keys="$(printf 'name\ndescription')"
  if [ "$fm_keys" = "$expected_keys" ]; then
    pass "$base: frontmatter has exactly the keys name, description"
  else
    fail "$base: frontmatter keys are [$fm_keys], expected exactly [name, description]"
  fi
done

echo ""
echo "Checked $check_count assertions across ${md_count} tone file(s) in $STYLES_DIR."

if [ "$fail_count" -gt 0 ]; then
  echo "RESULT: FAILED ($fail_count failing assertion(s))"
  exit 1
fi

echo "RESULT: ALL CHECKS PASSED"
exit 0
