#!/usr/bin/env bash
# Run mmap-related regression smoke tests (see mmapcache-smoke-tests.txt).
set -euo pipefail

_repo_root="$(cd "$(dirname "$0")/../.." && pwd)"
cd "${_repo_root}"

_py="${PYTHON:-python3}"
for _cand in "${_repo_root}/venv311/bin/python" "${_repo_root}/.venv/bin/python"; do
  if [[ -x "${_cand}" ]]; then
    _py="${_cand}"
    break
  fi
done

_tests_file="$(dirname "$0")/mmapcache-smoke-tests.txt"
mapfile -t _lines < <(grep -v '^#' "${_tests_file}" | grep -v '^$' || true)
if [[ ${#_lines[@]} -eq 0 ]]; then
  echo "No tests listed in ${_tests_file}" >&2
  exit 1
fi

exec "${_py}" -m pytest "${_lines[@]}" --benchmark-disable --tb=short "$@"
