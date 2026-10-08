"""
End-to-end check of ``exporter: prometheus`` with forked master processes.

The parent (standing in for the master) serves ``/metrics``; forked
children (standing in for MWorkers) record into the same counter and
histogram.  A scrape must show one series per label set with the sum of
all processes, with no per-process label (#70248).
"""

import multiprocessing
import os
import socket
import time
import urllib.request
from types import SimpleNamespace

import pytest

import salt.utils.metrics as metrics

pytest.importorskip("prometheus_client")

pytestmark = [
    pytest.mark.skipif(
        "fork" not in multiprocessing.get_all_start_methods(), reason="needs fork"
    ),
]

WORKERS = 3
ROUNDS = 4
PER_ROUND = 2


def _opts(port, tmp_path):
    return {
        "metrics": {
            "enabled": True,
            "exporter": "prometheus",
            "prometheus": {
                "host": "127.0.0.1",
                "port": port,
                "multiproc_dir": str(tmp_path / "prom"),
            },
        },
        "__role": "master",
    }


def _record(opts):
    """Run in a forked child: act as one MWorker."""
    metrics.configure(opts)
    counter = metrics.counter("salt.test.jobs")
    duration = metrics.histogram("salt.test.duration", unit="ms")
    for _ in range(ROUNDS):
        for _ in range(PER_ROUND):
            counter.add(1, attributes={"cmd": "ret"})
            duration.record(10, attributes={"cmd": "ret"})


def _scrape(port):
    deadline = time.time() + 10
    while True:
        try:
            with urllib.request.urlopen(
                f"http://127.0.0.1:{port}/metrics", timeout=2
            ) as resp:
                return resp.read().decode()
        except OSError:
            if time.time() > deadline:
                raise
            time.sleep(0.2)


def _value(body, series):
    for line in body.splitlines():
        if line.startswith(series + " "):
            return float(line.split()[-1])
    raise AssertionError(f"{series} not in:\n{body}")


@pytest.fixture(autouse=True)
def _reset_metrics(monkeypatch):
    metrics.shutdown()
    monkeypatch.setattr(metrics, "_cached_opts", None)
    yield
    metrics.shutdown()


def test_forked_processes_are_added_up_on_one_endpoint(tmp_path):
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        port = sock.getsockname()[1]
    opts = _opts(port, tmp_path)

    # The parent configures first (it serves /metrics), then forks workers.
    metrics.configure(opts)
    metrics.observable_gauge(
        "salt.test.depth",
        lambda _options: [SimpleNamespace(value=5, attributes={"pool": "default"})],
    )
    per_process = ROUNDS * PER_ROUND

    ctx = multiprocessing.get_context("fork")
    procs = [ctx.Process(target=_record, args=(opts,)) for _ in range(WORKERS)]
    for proc in procs:
        proc.start()
    for proc in procs:
        proc.join(timeout=60)
        assert proc.exitcode == 0

    # The parent records too, after its workers have exited: their values
    # must still be part of the total.
    metrics.counter("salt.test.jobs").add(per_process, attributes={"cmd": "ret"})
    body = _scrape(port)

    total = (WORKERS + 1) * per_process
    assert _value(body, 'salt_test_jobs_total{cmd="ret"}') == total
    assert (
        _value(body, 'salt_test_duration_milliseconds_count{cmd="ret"}')
        == WORKERS * per_process
    )
    assert (
        _value(body, 'salt_test_duration_milliseconds_sum{cmd="ret"}')
        == WORKERS * per_process * 10
    )
    assert (
        _value(body, 'salt_test_duration_milliseconds_bucket{cmd="ret",le="10.0"}')
        == WORKERS * per_process
    )
    # Callback gauges are evaluated in the serving process at scrape time.
    assert _value(body, 'salt_test_depth{pool="default"}') == 5
    # Nothing identifies a worker: one series, nothing to sum.
    assert "pid=" not in body
    assert body.count("salt_test_jobs_total{") == 1


def test_directory_is_removed_on_shutdown():
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        port = sock.getsockname()[1]
    metrics.configure(
        {
            "metrics": {
                "enabled": True,
                "exporter": "prometheus",
                "prometheus": {"host": "127.0.0.1", "port": port},
            },
            "__role": "master",
        }
    )
    directory = os.environ["PROMETHEUS_MULTIPROC_DIR"]
    metrics.counter("salt.test.jobs").add(1)
    assert os.listdir(directory)
    metrics.shutdown()
    assert not os.path.exists(directory)
    assert "PROMETHEUS_MULTIPROC_DIR" not in os.environ
