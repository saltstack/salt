#!/usr/bin/env bash
# For each EXISTS_MATCH_DEST candidate file, list the top 3008.x-only commits
# and dump the raw diff for reviewer inspection.
set -u
cd /home/dan/src/salt/worktree/mf_3008_master

IN=agents/scratch/exists_match_dest.txt
OUT=agents/scratch/per_file_review.txt
: >"$OUT"

while IFS= read -r f; do
  echo "========================================" >>"$OUT"
  echo "FILE: $f" >>"$OUT"
  echo "----------------------------------------" >>"$OUT"
  echo "-- 3008.x-only commits (subject only):" >>"$OUT"
  git log --oneline origin/master..origin/3008.x -- "$f" >>"$OUT"
  echo "" >>"$OUT"
done <"$IN"

echo "wrote $OUT ($(wc -l <"$OUT") lines)"
