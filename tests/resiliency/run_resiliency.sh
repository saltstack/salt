#!/usr/bin/env bash
#
# Resiliency suite entry point.  Thin wrapper around pytest.
#
# The scenarios live in ``tests/resiliency/test_*.py``; this script
# resolves the pytest invocation (topology selection, marker gating,
# plugin conflicts with the parent salt pytest env, workdir layout)
# so the workflow and local invocations stay a single command.
#
# Usage:
#   TOPOLOGY=single ./run_resiliency.sh                           # full battery on single
#   TOPOLOGY=cluster3 SCENARIOS="baseline master_restart" ...     # subset
#   TOPOLOGY=multimaster-failover MARATHON_ENABLED=0 ...          # opt-out of marathon
#
# Env:
#   TOPOLOGY              required: single|cluster3|cluster5|
#                                   multimaster-failover|multimaster-hothot|syndic
#   SCENARIOS             optional: space-separated list of scenario-file
#                                   stems to run.  Default: full battery.
#                                   Each stem maps to test_<stem>.py.
#   MARATHON_ENABLED      1 (default) | 0 to skip master_marathon phases
#   RESILIENCY_WORKDIR    results dir (default: results/<utc-timestamp>)
#   PROMETHEUS_URL        override prometheus endpoint (default per topology)
#   PYTEST_EXTRA_ARGS     appended to the pytest command line verbatim
#
# Exit code: pytest's exit code (0 = all pass, 1 = failures, 2 = setup
# errors / collection problems).

set -u

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/../.." && pwd)"

if [ -z "${TOPOLOGY:-}" ]; then
    printf 'run_resiliency: TOPOLOGY is required (single|cluster3|cluster5|multimaster-failover|multimaster-hothot|syndic)\n' >&2
    exit 2
fi

: "${RESILIENCY_WORKDIR:=${SCRIPT_DIR}/results/$(date -u +%Y%m%dT%H%M%SZ)}"
mkdir -p "$RESILIENCY_WORKDIR"
export RESILIENCY_WORKDIR
export RESULTS_FILE="${RESILIENCY_WORKDIR}/results.jsonl"

: "${MARATHON_ENABLED:=1}"
export MARATHON_ENABLED

printf '[run_resiliency] TOPOLOGY=%s workdir=%s marathon=%s\n' \
    "$TOPOLOGY" "$RESILIENCY_WORKDIR" "$MARATHON_ENABLED"

PYTEST_BIN="${PYTEST_BIN:-}"
if [ -z "$PYTEST_BIN" ]; then
    for candidate in \
        "${REPO_ROOT}/venv314/bin/pytest" \
        "${REPO_ROOT}/venv310/bin/pytest" \
        "$(command -v pytest || true)"; do
        if [ -n "$candidate" ] && [ -x "$candidate" ]; then
            PYTEST_BIN="$candidate"
            break
        fi
    done
fi
if [ -z "$PYTEST_BIN" ]; then
    printf 'run_resiliency: no pytest found (set PYTEST_BIN or install salt venv)\n' >&2
    exit 2
fi

# Plugin exclusions:
#  - pytestsysstats double-registers alongside salt-factories' sysinfo;
#    both ship under different plugin names but hit the same
#    registration key.
#  - salt-factories pulls a fixture set the resiliency suite doesn't
#    need and hooks into collection in ways that interact poorly with
#    our --confcutdir isolation.
PYTEST_ARGS=(
    -c "${SCRIPT_DIR}/pytest.ini"
    --confcutdir="${SCRIPT_DIR}"
    -p no:system-statistics
    -p no:salt-factories
    "--topology=${TOPOLOGY}"
    # ``-v`` emits one flushed line per test (``test_X::test_Y PASSED``)
    # instead of dot-per-test batched per module.  Essential for GHA log
    # progress visibility -- marathon runs would otherwise show nothing
    # for 90+ min between dot batches.
    -v
    -ra
)

if [ "${MARATHON_ENABLED}" = "1" ]; then
    PYTEST_ARGS+=(--marathon)
fi

# Translate SCENARIOS space-list -> pytest -k expression.  Each stem
# selects its matching test_<stem>.py file via test-ID substring match.
if [ -n "${SCENARIOS:-}" ]; then
    kexpr=""
    for s in $SCENARIOS; do
        if [ -z "$kexpr" ]; then
            kexpr="test_${s}"
        else
            kexpr="${kexpr} or test_${s}"
        fi
    done
    PYTEST_ARGS+=(-k "$kexpr")
    printf '[run_resiliency] scenario filter: -k %q\n' "$kexpr"
fi

if [ -n "${PYTEST_EXTRA_ARGS:-}" ]; then
    # shellcheck disable=SC2206  # intentional word-split of caller-supplied args
    PYTEST_ARGS+=(${PYTEST_EXTRA_ARGS})
fi

PYTEST_ARGS+=("${SCRIPT_DIR}")

printf '[run_resiliency] exec: %s %s\n' "$PYTEST_BIN" "${PYTEST_ARGS[*]}"
exec "$PYTEST_BIN" "${PYTEST_ARGS[@]}"
