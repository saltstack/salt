#!/usr/bin/env bash
# For each EXISTS_MATCH_DEST candidate, list 3008.x-only commits whose subject
# looks like a bug fix (fix|Fix|FIX|#NNNNN). Exclude merges and pre-commit.
set -u
cd /home/dan/src/salt/worktree/mf_3008_master

IN=agents/scratch/exists_match_dest.txt
OUT=agents/scratch/fix_commits_per_file.txt
: >"$OUT"

while IFS= read -r f; do
  # --no-merges filters merge commits; grep for fix-like subjects
  fix_log=$(git log --no-merges --oneline origin/master..origin/3008.x -- "$f" \
    | grep -iE 'fix|#[0-9]{4,}|regress|bug|broken|correct|issue' \
    | grep -viE 'pre-commit|pyupgrade|blacken|isort|lint|black |Merge |[Ff]ormat |typo|test|migrate legacy' \
    | head -10)
  if [ -n "$fix_log" ]; then
    echo "== $f ==" >>"$OUT"
    echo "$fix_log" >>"$OUT"
    echo "" >>"$OUT"
  else
    # Even if no fix-labeled commit, note this
    echo "== $f == (no obvious fix commits)" >>"$OUT"
    echo "" >>"$OUT"
  fi
done <"$IN"

wc -l "$OUT"
