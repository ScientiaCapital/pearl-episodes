#!/usr/bin/env bash
# PreToolUse hook for Write, Edit, MultiEdit and NotebookEdit: deny a file write whose new content holds a secret.
# Claude Code sends the event as JSON on stdin. Every string inside tool_input is checked. Input this hook can't
# read is denied, never let through. Tested in tests/hook-test.sh. gitleaks (pre-commit and CI) is the backstop
# for anything written outside Claude Code.
set -u -o pipefail

deny() {
  jq -cn --arg r "$1" '{hookSpecificOutput: {hookEventName: "PreToolUse", permissionDecision: "deny",
    permissionDecisionReason: $r}}' 2>/dev/null \
    || printf '{"hookSpecificOutput":{"hookEventName":"PreToolUse","permissionDecision":"deny","permissionDecisionReason":"%s"}}\n' "$1"
  exit 0
}

command -v jq >/dev/null 2>&1 || deny "check-secrets: jq is not installed, so this write can't be checked."
input=$(cat)
[ -n "$input" ] || deny "check-secrets: empty tool call."
content=$(printf '%s' "$input" | jq -er 'if (.tool_input | type) == "object" then [.tool_input | .. | strings] | join("\n")
  else error("no tool_input") end' 2>/dev/null) \
  || deny "check-secrets: couldn't read this tool call."

# Name and pattern. Patterns are POSIX ERE; each is passed with -e so a leading dash is never read as an option.
patterns=(
  "private key|-----BEGIN [A-Z ]*PRIVATE KEY-----"
  "Anthropic API key|sk-ant-[A-Za-z0-9_-]{20,}"
  "AWS access key|AKIA[0-9A-Z]{16}"
  "GitHub token|gh[pousr]_[A-Za-z0-9]{36}"
  "GitHub fine-grained token|github_pat_[A-Za-z0-9_]{50,}"
  "Slack token|xox[abprs]-[A-Za-z0-9-]{10,}"
  "Google API key|AIza[0-9A-Za-z_-]{35}"
  "Pearl password in an env file|^[[:space:]]*PEARL_PASSWORD=[^[:space:]#]+"
)
for entry in "${patterns[@]}"; do
  name=${entry%%|*}
  pattern=${entry#*|}
  printf '%s' "$content" | grep -qE -e "$pattern"
  case $? in
    0) deny "check-secrets: the new content looks like it holds a ${name}. Put secrets in .env (gitignored) and read them through Settings." ;;
    1) ;;
    *) deny "check-secrets: the ${name} check failed to run, so this write was blocked." ;;
  esac
done
exit 0
