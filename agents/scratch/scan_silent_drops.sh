#!/usr/bin/env bash
# Silent-drop scanner for in-progress 3008.x -> master merge.
# Reads candidate_files.txt and uu_files.txt from same dir.
set -u
cd /home/dan/src/salt/worktree/mf_3008_master

UU=agents/scratch/uu_files.txt
IN=agents/scratch/candidate_files.txt
OUT=agents/scratch/candidates_raw.txt
: >"$OUT"

# Build a hash of UU files for O(1) skip lookup.
declare -A UU_SET
while IFS= read -r f; do UU_SET["$f"]=1; done <"$UU"

while IFS= read -r f; do
  [ -n "${UU_SET[$f]:-}" ] && continue

  # dst hash from master
  dst=$(git rev-parse "origin/master:$f" 2>/dev/null) || dst=""
  # src hash from 3008.x
  src=$(git rev-parse "origin/3008.x:$f" 2>/dev/null) || src=""
  # ours = working tree hash. If file doesn't exist, ours is "".
  if [ -e "$f" ]; then
    ours=$(git hash-object -- "$f" 2>/dev/null) || ours=""
  else
    ours=""
  fi

  # Case A: file exists in tree, matches DEST, differs from SRC
  if [ -n "$ours" ] && [ -n "$dst" ] && [ -n "$src" ] \
     && [ "$ours" = "$dst" ] && [ "$ours" != "$src" ]; then
    # check that 3008.x has commits touching this file that master lacks
    n=$(git log --oneline origin/master..origin/3008.x -- "$f" | wc -l)
    if [ "$n" -gt 0 ]; then
      printf '%s\tEXISTS_MATCH_DEST\t%s\n' "$f" "$n" >>"$OUT"
    fi
    continue
  fi

  # Case B: file missing in tree but present on SRC — potential drop of a
  # SRC-added file. Only flag if file is *not* in DEST (i.e., only SRC added it).
  if [ -z "$ours" ] && [ -n "$src" ] && [ -z "$dst" ]; then
    # 3008.x has this file, master doesn't, working tree doesn't. Merge should
    # have added it. If it's absent post-merge, that's a drop candidate.
    printf '%s\tMISSING_SRC_ONLY\t0\n' "$f" >>"$OUT"
    continue
  fi
done <"$IN"

wc -l "$OUT"
