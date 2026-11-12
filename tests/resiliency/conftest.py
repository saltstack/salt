"""Pytest configuration and fixtures for the Salt resiliency suite.

This conftest ports the lifecycle that ``run_resiliency.sh`` and
``lib/common.sh`` implement in bash:

  * compose up (per topology) + exporter launch + ``wait_initial_auth``;
  * per-scenario workload backgrounding under its own process group;
  * ``results.jsonl`` capture in a schema the existing
    ``analyze_resiliency.py`` can consume;
  * teardown: ``docker compose logs``, prometheus_data tarball, compose
    down (unless ``--no-cleanup``).

Fixtures provided (see ``CONTRACT.md``):

  * session-scoped ``topology`` -- a running ``Topology`` handle;
  * function-scoped ``workload`` -- a backgrounded ``workload.sh``.

Markers registered:

  * ``@pytest.mark.topology("single", "cluster3", ...)`` -- skip the
    test unless the session topology is in the list;
  * ``@pytest.mark.marathon`` -- skip unless ``--marathon`` is passed;
  * ``@pytest.mark.setup_error_on_fail`` -- a failure on such a test is
    recorded as ``setup_error`` in results.jsonl instead of ``failed``.

Scenarios stash per-test result data on their pytest ``item`` via
``stash_result``; ``pytest_runtest_makereport`` reads it back and
writes a single JSONL row per test to ``$RESILIENCY_WORKDIR/results.jsonl``.
"""

# pylint: disable=broad-exception-caught  # Resiliency: test cleanup catches Exception deliberately to avoid masking the real verdict

from __future__ import annotations

import datetime as _dt
import json
import os
import signal
import subprocess
import time
from pathlib import Path
from typing import Any

import pytest

# Lazy import: ``lib.topology`` is produced by a parallel agent; we need
# the names ``load_topology`` and ``Topology`` only at fixture-time.
# Defer the import so that ``pytest --collect-only`` on the resiliency
# tests works even before that module lands.


# ---------------------------------------------------------------------------
# Paths / env
# ---------------------------------------------------------------------------

HERE = Path(__file__).resolve().parent
REPO_ROOT = HERE.parent.parent

VALID_TOPOLOGIES = (
    "single",
    "cluster3",
    "cluster5",
    "multimaster-failover",
    "multimaster-hothot",
    "syndic",
)

# Per-topology default prometheus URLs.  Mirrors run_resiliency.sh.
DEFAULT_PROM_URLS = {
    "single": "http://127.0.0.1:19090",
    "cluster3": "http://127.0.0.1:19090",
    "cluster5": "http://127.0.0.1:19093",
    "multimaster-failover": "http://127.0.0.1:19091",
    "multimaster-hothot": "http://127.0.0.1:19091",
    "syndic": "http://127.0.0.1:19092",
}

# Per-topology prometheus_data bind-mount source.  Mirrors run_resiliency.sh.
PROM_DATA_DIRS = {
    "single": REPO_ROOT
    / "tests"
    / "resiliency"
    / "compose"
    / "single"
    / "prometheus_data",
    "cluster3": REPO_ROOT
    / "tests"
    / "monitoring"
    / "cluster-3node"
    / "prometheus_data",
    "cluster5": REPO_ROOT
    / "tests"
    / "monitoring"
    / "cluster-5node"
    / "prometheus_data",
    "multimaster-failover": REPO_ROOT
    / "tests"
    / "resiliency"
    / "compose"
    / "multimaster"
    / "prometheus_data",
    "multimaster-hothot": REPO_ROOT
    / "tests"
    / "resiliency"
    / "compose"
    / "multimaster"
    / "prometheus_data",
    "syndic": REPO_ROOT
    / "tests"
    / "resiliency"
    / "compose"
    / "syndic"
    / "prometheus_data",
}


def _utc_timestamp() -> str:
    return _dt.datetime.utcnow().strftime("%Y%m%dT%H%M%SZ")


def _resolve_workdir() -> Path:
    """Return ``$RESILIENCY_WORKDIR`` or the default results path."""
    env = os.environ.get("RESILIENCY_WORKDIR")
    if env:
        workdir = Path(env)
    else:
        workdir = HERE / "results" / _utc_timestamp()
    workdir.mkdir(parents=True, exist_ok=True)
    return workdir


# ---------------------------------------------------------------------------
# CLI flags + marker registration
# ---------------------------------------------------------------------------


def pytest_addoption(parser):
    group = parser.getgroup("resiliency")
    group.addoption(
        "--topology",
        action="store",
        default="single",
        choices=VALID_TOPOLOGIES,
        help="Which resiliency topology to bring up (default: single).",
    )
    group.addoption(
        "--marathon",
        action="store_true",
        default=False,
        help="Enable tests marked @pytest.mark.marathon (multi-hour runs).",
    )
    group.addoption(
        "--no-cleanup",
        action="store_true",
        default=False,
        help="Leave the compose stack running after the session for debugging.",
    )
    group.addoption(
        "--prometheus-url",
        action="store",
        default=None,
        help="Override the per-topology prometheus endpoint.",
    )


def pytest_configure(config):
    config.addinivalue_line(
        "markers",
        "topology(*names): skip unless the session topology is in `names`",
    )
    config.addinivalue_line(
        "markers",
        "marathon: skip unless --marathon is passed (multi-hour tests)",
    )
    config.addinivalue_line(
        "markers",
        "setup_error_on_fail: a failure of this test is recorded as "
        "setup_error in results.jsonl (used for fixture-level errors)",
    )

    # Resolve + publish the workdir / results file / prometheus URL now so
    # every downstream hook, fixture, and worker sees the same values.
    topo_name = config.getoption("--topology")
    workdir = _resolve_workdir()
    results_file = workdir / "results.jsonl"
    prom_url = config.getoption("--prometheus-url") or DEFAULT_PROM_URLS[topo_name]

    os.environ.setdefault("RESILIENCY_WORKDIR", str(workdir))
    os.environ["RESULTS_FILE"] = str(results_file)
    os.environ["PROMETHEUS_URL"] = prom_url
    # Exported for scenarios / lib.topology to consume without re-parsing argv.
    os.environ["TOPOLOGY"] = topo_name

    config._resiliency_workdir = workdir  # type: ignore[attr-defined]
    config._resiliency_results_file = results_file  # type: ignore[attr-defined]
    config._resiliency_prom_url = prom_url  # type: ignore[attr-defined]
    config._resiliency_topology_name = topo_name  # type: ignore[attr-defined]


# ---------------------------------------------------------------------------
# Collection-time filtering
# ---------------------------------------------------------------------------


def pytest_collection_modifyitems(config, items):
    topo_name = config.getoption("--topology")
    marathon_enabled = config.getoption("--marathon")

    skip_topology = pytest.mark.skip(
        reason=f"topology {topo_name!r} not in test's topology list"
    )
    skip_marathon = pytest.mark.skip(
        reason="marathon tests disabled; pass --marathon to enable"
    )

    for item in items:
        topo_marker = item.get_closest_marker("topology")
        if topo_marker is not None and topo_marker.args:
            if topo_name not in topo_marker.args:
                item.add_marker(skip_topology)
                # Flag this skip so pytest_runtest_makereport can record
                # it with the dedicated "skipped_for_topology" outcome.
                item.user_properties.append(("resiliency_skipped_for_topology", True))

        if item.get_closest_marker("marathon") is not None and not marathon_enabled:
            item.add_marker(skip_marathon)


# ---------------------------------------------------------------------------
# Session-scoped topology fixture
# ---------------------------------------------------------------------------


def _compose_cmd(spec, *args: str) -> list[str]:
    """Build ``docker compose -f ... -p <project> <args...>``."""
    cmd = ["docker", "compose"]
    for cf in spec.compose_files:
        cmd.extend(["-f", str(cf)])
    cmd.extend(["-p", spec.compose_project])
    cmd.extend(args)
    return cmd


def _launch_exporters(topo_name: str, spec, workdir: Path) -> None:
    """Topology-specific fd_exporter startup -- mirrors run_resiliency.sh."""
    log = (workdir / "exporters.log").open("a")
    try:
        if topo_name in ("single", "cluster3", "cluster5", "syndic"):
            script = HERE / "compose" / topo_name / "start_exporters.sh"
            if script.exists() and os.access(script, os.X_OK):
                subprocess.run(
                    [str(script)],
                    stdout=log,
                    stderr=subprocess.STDOUT,
                    check=False,
                )
            else:
                log.write(f"[exporters] no start_exporters.sh for {topo_name}\n")
        elif topo_name in ("multimaster-failover", "multimaster-hothot"):
            for master in spec.masters:
                subprocess.run(
                    [
                        "docker",
                        "exec",
                        "-d",
                        master,
                        "python3",
                        "/srv/fd_exporter.py",
                    ],
                    stdout=log,
                    stderr=subprocess.STDOUT,
                    check=False,
                )
    finally:
        log.close()


def _snapshot_compose_logs(spec, workdir: Path) -> None:
    """``docker compose ... logs > compose.log``.  Best-effort."""
    with (workdir / "compose.log").open("w") as fh:
        subprocess.run(
            _compose_cmd(spec, "ps"),
            stdout=fh,
            stderr=subprocess.STDOUT,
            check=False,
        )
        fh.write("\n==== docker compose logs ====\n")
        subprocess.run(
            _compose_cmd(spec, "logs", "--no-color"),
            stdout=fh,
            stderr=subprocess.STDOUT,
            check=False,
        )


def _snapshot_prometheus_data(topo_name: str, spec, workdir: Path) -> None:
    """Stop prometheus, then tar the data dir to prometheus-data.tar.gz."""
    subprocess.run(
        _compose_cmd(spec, "stop", "prometheus"),
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        check=False,
    )
    prom_data = PROM_DATA_DIRS.get(topo_name)
    if prom_data is None or not prom_data.exists():
        return
    tar_out = workdir / "prometheus-data.tar.gz"
    cmd = [
        "tar",
        "-czf",
        str(tar_out),
        "-C",
        str(prom_data.parent),
        prom_data.name,
    ]
    rc = subprocess.run(
        cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=False
    ).returncode
    if rc != 0:
        # One retry under sudo; same fallback the bash orchestrator uses.
        subprocess.run(
            ["sudo"] + cmd,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            check=False,
        )


def _record_setup_error_row(scenario: str, message: str) -> None:
    """Append a setup_error row directly (no pytest item context)."""
    results_file = Path(os.environ["RESULTS_FILE"])
    row = {
        "ts": time.time(),
        "topology": os.environ.get("TOPOLOGY", "unknown"),
        "scenario": scenario,
        "outcome": "setup_error",
        "reconnect_seconds": -1,
        "attempts": 0,
        "missing": [],
        "fd_delta": 0,
        "rss_kb_delta": 0,
        "fault_seconds": 0,
        "notes": message,
    }
    with results_file.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(row) + "\n")


# Public helper -- lib.topology.Topology.assert_reconnect calls this to
# push structured result data onto the current pytest item, which then
# flows into the JSONL row via pytest_runtest_makereport.
def stash_result(item_or_request, **kwargs: Any) -> None:
    """Attach resiliency-result fields to the current pytest item.

    Accepts either a pytest ``Item`` or a ``FixtureRequest``.  Keys are
    merged into any previously stashed dict so successive calls within
    the same test refine the row.
    """
    item = getattr(item_or_request, "node", None) or item_or_request
    for key, value in item.user_properties:
        if key == "resiliency":
            value.update(kwargs)
            return
    item.user_properties.append(("resiliency", dict(kwargs)))


@pytest.fixture(scope="session")
def topology(request):
    """Bring up the compose stack, wait for initial auth, yield Topology.

    Teardown: snapshot logs + prometheus data, then ``compose down -v
    --remove-orphans`` unless ``--no-cleanup`` was passed.
    """
    # Deferred import: lib.topology is written by a parallel wave-1 agent.
    from .lib.topology import Topology, load_topology  # type: ignore

    config = request.config
    topo_name = config._resiliency_topology_name
    workdir = config._resiliency_workdir

    spec = load_topology(topo_name)

    # --- compose up ----------------------------------------------------
    up_log_path = workdir / "compose-up.log"
    with up_log_path.open("w") as fh:
        rc = subprocess.run(
            _compose_cmd(spec, "up", "-d", "--build"),
            stdout=fh,
            stderr=subprocess.STDOUT,
            check=False,
        ).returncode
    if rc != 0:
        _record_setup_error_row(
            "topology_setup",
            f"compose up failed (rc={rc}); see {up_log_path}",
        )
        pytest.fail(
            f"docker compose up failed for topology={topo_name!r} "
            f"(rc={rc}); see {up_log_path}",
            pytrace=False,
        )

    # --- exporters -----------------------------------------------------
    _launch_exporters(topo_name, spec, workdir)

    # --- wait for initial auth ----------------------------------------
    topology_handle = Topology(spec)
    try:
        topology_handle.wait_initial_auth(300)
    except Exception as exc:  # noqa: BLE001 -- surface + record anything
        _record_setup_error_row(
            "topology_setup",
            f"wait_initial_auth failed: {exc}",
        )
        _snapshot_compose_logs(spec, workdir)
        if not config.getoption("--no-cleanup"):
            subprocess.run(
                _compose_cmd(spec, "down", "-v", "--remove-orphans"),
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                check=False,
            )
        pytest.fail(
            f"wait_initial_auth(300) timed out for topology={topo_name!r}: {exc}",
            pytrace=False,
        )

    try:
        yield topology_handle
    finally:
        _snapshot_compose_logs(spec, workdir)
        _snapshot_prometheus_data(topo_name, spec, workdir)
        if not config.getoption("--no-cleanup"):
            subprocess.run(
                _compose_cmd(spec, "down", "-v", "--remove-orphans"),
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                check=False,
            )


# ---------------------------------------------------------------------------
# Function-scoped workload fixture
# ---------------------------------------------------------------------------


@pytest.fixture
def workload(topology, request):
    """Run ``workload.sh`` as a background pgroup for the duration of a test."""
    script = HERE / "workload.sh"
    if not script.exists():
        pytest.skip(f"workload.sh missing at {script}")

    log_path = (
        Path(os.environ["RESILIENCY_WORKDIR"]) / f"workload-{request.node.name}.log"
    )
    env = os.environ.copy()
    env["MASTER"] = topology.spec.primary_master

    log_fh = log_path.open("w")
    proc = subprocess.Popen(
        [str(script)],
        stdin=subprocess.DEVNULL,
        stdout=log_fh,
        stderr=subprocess.STDOUT,
        env=env,
        start_new_session=True,  # new pgroup, pgid == pid
        cwd=str(HERE),
    )
    pgid = proc.pid  # start_new_session guarantees pgid == pid

    try:
        yield None
    finally:
        # SIGTERM the whole pgroup; wait; SIGKILL if stubborn.
        try:
            os.killpg(pgid, signal.SIGTERM)
        except ProcessLookupError:
            pass
        try:
            proc.wait(timeout=10)
        except subprocess.TimeoutExpired:
            try:
                os.killpg(pgid, signal.SIGKILL)
            except ProcessLookupError:
                pass
            try:
                proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                pass
        log_fh.close()


# ---------------------------------------------------------------------------
# results.jsonl recording hook
# ---------------------------------------------------------------------------


_RESULT_KEYS: list[str] = [
    "reconnect_seconds",
    "attempts",
    "missing",
    "fd_delta",
    "rss_kb_delta",
    "fault_seconds",
    "notes",
]
_RESULT_DEFAULTS: dict[str, Any] = {
    "reconnect_seconds": -1,
    "attempts": 0,
    "missing": [],
    "fd_delta": 0,
    "rss_kb_delta": 0,
    "fault_seconds": 0,
    "notes": "",
}


def _extract_stash(item) -> dict[str, Any]:
    """Pull the ``resiliency`` dict out of item.user_properties (or empty)."""
    for key, value in item.user_properties:
        if key == "resiliency" and isinstance(value, dict):
            return value
    return {}


def _skipped_for_topology(item) -> bool:
    for key, value in item.user_properties:
        if key == "resiliency_skipped_for_topology":
            return bool(value)
    return False


def _append_jsonl_row(row: dict[str, Any]) -> None:
    results_file = Path(os.environ["RESULTS_FILE"])
    results_file.parent.mkdir(parents=True, exist_ok=True)
    with results_file.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(row) + "\n")


@pytest.hookimpl(hookwrapper=True)
def pytest_runtest_makereport(item, call):
    """One JSONL row per test, keyed off the call phase."""
    outcome = yield
    report = outcome.get_result()

    # Only record on the "call" phase, OR on a "setup" failure (so a
    # fixture explosion still produces a setup_error row rather than
    # silent omission).
    if report.when not in ("call", "setup"):
        return

    # Avoid double-recording: if setup failed we'll emit, then skip call.
    if report.when == "call" and getattr(item, "_resiliency_recorded", False):
        return

    stash = _extract_stash(item)
    nodeid_tail = item.nodeid.split("::", 1)[-1] if "::" in item.nodeid else item.nodeid

    # Determine outcome string
    if report.when == "setup" and report.failed:
        outcome_str = "setup_error"
    elif report.skipped and _skipped_for_topology(item):
        outcome_str = "skipped_for_topology"
    elif report.skipped:
        # Non-topology skip (e.g. --marathon disabled): don't pollute
        # results.jsonl -- the analyzer would count it as a missing
        # scenario.  Bash equivalent is "scenario wasn't invoked".
        return
    elif report.passed:
        outcome_str = "recovered"
    elif report.failed:
        if item.get_closest_marker("setup_error_on_fail") is not None:
            outcome_str = "setup_error"
        else:
            outcome_str = "failed"
    else:
        # Should not happen; be defensive.
        outcome_str = "failed"

    # The bash phase label (passed to assert_reconnect as the first
    # arg) is the authoritative scenario name used by the analyzer.
    # Prefer it over the pytest nodeid.  Fall back to nodeid for tests
    # that didn't call through assert_reconnect (shouldn't happen for
    # fault tests; happens for skip rows).
    scenario_label = stash.get("scenario") or nodeid_tail
    row: dict[str, Any] = {
        "ts": time.time(),
        "topology": os.environ.get("TOPOLOGY", "unknown"),
        "scenario": scenario_label,
        "outcome": outcome_str,
    }
    for key in _RESULT_KEYS:
        row[key] = stash.get(key, _RESULT_DEFAULTS[key])

    # If the scenario failed and left no explicit notes, give the row
    # something to show the analyzer / operator.
    if outcome_str in ("failed", "setup_error") and not row["notes"]:
        longrepr = getattr(report, "longreprtext", "") or ""
        if longrepr:
            # Trim; the JSONL stays operator-readable.
            row["notes"] = longrepr.splitlines()[-1][:500]

    _append_jsonl_row(row)
    item._resiliency_recorded = True


# ---------------------------------------------------------------------------
# Session finish: print a short summary (does NOT fail the session)
# ---------------------------------------------------------------------------


def _analyze_resiliency_summary(results_file: Path) -> str:
    """Render a terse per-scenario table.

    Does not import ``analyze_resiliency`` because that module also
    hits prometheus; the session-finish summary should be fast and
    local-only.  Analyzer verdict runs separately (bash wrapper or
    CI step).
    """
    if not results_file.exists():
        return f"[resiliency] no results at {results_file}"
    records: list[dict[str, Any]] = []
    with results_file.open(encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            try:
                records.append(json.loads(line))
            except json.JSONDecodeError:
                continue
    if not records:
        return f"[resiliency] empty results at {results_file}"

    headers = [
        "scenario",
        "outcome",
        "reconnect_s",
        "missing",
        "fd_delta",
        "rss_kb_delta",
    ]
    rows = []
    for r in records:
        missing = r.get("missing") or []
        missing_s = ",".join(missing) if isinstance(missing, list) and missing else "-"
        rows.append(
            [
                str(r.get("scenario", "?")),
                str(r.get("outcome", "?")),
                str(r.get("reconnect_seconds", "?")),
                missing_s,
                str(r.get("fd_delta", "?")),
                str(r.get("rss_kb_delta", "?")),
            ]
        )
    widths = [len(h) for h in headers]
    for row in rows:
        for i, cell in enumerate(row):
            widths[i] = max(widths[i], len(cell))
    fmt = "  ".join(f"{{:<{w}}}" for w in widths)
    lines = [
        f"[resiliency] summary from {results_file}",
        fmt.format(*headers),
        fmt.format(*["-" * w for w in widths]),
    ]
    for row in rows:
        lines.append(fmt.format(*row))

    # Short tally, operator-friendly.
    tally: dict[str, int] = {}
    for r in records:
        tally[r.get("outcome", "?")] = tally.get(r.get("outcome", "?"), 0) + 1
    tally_s = " ".join(f"{k}={v}" for k, v in sorted(tally.items()))
    lines.append("")
    lines.append(f"[resiliency] totals: {tally_s}")
    return "\n".join(lines)


def pytest_sessionfinish(session, exitstatus):
    results_file = Path(os.environ.get("RESULTS_FILE", ""))
    if not results_file:
        return
    print()
    print(_analyze_resiliency_summary(results_file))
