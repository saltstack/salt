#!/usr/bin/env bash
# Re-run every failed workflow job listed in ci_logs/github_actions_run_*_failures.txt
# (one numeric job id per line after the header block).
#
# Requires a GitHub token with permission to re-run Actions jobs on the repo
# (classic PAT: ``repo`` + ``workflow`` scope, or fine-grained: Actions write).
#
# Usage:
#   export GH_TOKEN=...   # optional if gh is already logged in with sufficient scope
#   bash cicd/gh-rerun-failed-jobs-from-snapshot.sh ci_logs/github_actions_run_24876542573_failures.txt
#
# Notes:
# - ``gh run rerun <run-id> --failed`` often fails for cancelled/legacy runs
#   ("workflow file may be broken"); per-job POST can still be rejected.
# - This cannot execute macOS / Windows / arm64-only matrix rows on a Linux dev box;
#   it only triggers GitHub-hosted reruns.

set -euo pipefail
FILE=${1:?path to github_actions_run_*_failures.txt}
REPO=${GITHUB_REPOSITORY:-saltstack/salt}
LOG=${RERUN_LOG:-ci_logs/gh_rerun_jobs_attempt.log}
mkdir -p "$(dirname "$LOG")"
: >"$LOG"
ok=0
fail=0
while IFS= read -r line; do
  id=${line%%$'\t'*}
  if [[ ! "$id" =~ ^[0-9]+$ ]]; then
    continue
  fi
  name=${line#*$'\t'}
  name=${name%%$'\t'*}
  echo "POST jobs/$id ($name)" | tee -a "$LOG"
  if gh api --method POST "repos/$REPO/actions/jobs/$id/rerun" >>"$LOG" 2>&1; then
    ok=$((ok + 1))
  else
    fail=$((fail + 1))
  fi
  sleep "${RERUN_SLEEP:-0.35}"
done < <(
  # Only the "## Failed jobs" table — not "## Jobs not finished" / in_progress rows.
  awk -F'\t' '
    /^## Failed jobs/ {p=1; next}
    /^## / {if (p) exit}
    p && /^[0-9]+\t/ {print $1 "\t" $2}
  ' "$FILE"
)

echo "Done. ok=$ok fail=$fail log=$LOG"
