"""
Unit tests for the ``prometheus_client`` backend of salt.utils.metrics.
"""

import logging
import os
import socket
import sys
import threading
import urllib.request

import pytest

import salt.utils.metrics as metrics
import salt.utils.metrics_prometheus as backend

pytest.importorskip("prometheus_client")

pytestmark = [pytest.mark.skip_on_windows]


@pytest.fixture(autouse=True)
def _reset_metrics(monkeypatch):
    metrics.shutdown()
    monkeypatch.setattr(metrics, "_cached_opts", None)
    yield
    metrics.shutdown()


def _configure(tmp_path, **extra):
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        port = sock.getsockname()[1]
    metrics.configure(
        {
            "metrics": {
                "enabled": True,
                "exporter": "prometheus",
                "prometheus": {
                    "host": "127.0.0.1",
                    "port": port,
                    "multiproc_dir": str(tmp_path / "prom"),
                },
                **extra,
            },
            "__role": "master",
        }
    )
    return port


def _scrape(port):
    with urllib.request.urlopen(f"http://127.0.0.1:{port}/metrics", timeout=5) as resp:
        return resp.read().decode()


@pytest.mark.parametrize(
    "name,unit,expected",
    [
        ("salt.jobs.completed", "", "salt_jobs_completed"),
        ("salt.job.duration", "ms", "salt_job_duration_milliseconds"),
        ("salt.process.open_fds", "{fd}", "salt_process_open_fds"),
        ("salt.x", "By", "salt_x_bytes"),
    ],
)
def test_metric_names_follow_the_otel_exporter(name, unit, expected):
    assert backend._metric_name(name, unit) == expected


def test_label_set_mismatch_does_not_raise(tmp_path):
    port = _configure(tmp_path)
    counter = metrics.counter("salt.test.mixed")
    counter.add(1, attributes={"cmd": "a"})
    # Missing and extra labels are mapped onto the first label set.
    counter.add(1)
    counter.add(1, attributes={"cmd": "a", "extra": "x"})
    body = _scrape(port)
    assert 'salt_test_mixed_total{cmd="a"} 2.0' in body
    assert 'salt_test_mixed_total{cmd=""} 1.0' in body


def test_same_name_returns_same_instrument(tmp_path):
    _configure(tmp_path)
    assert metrics.counter("salt.test.same") is metrics.counter("salt.test.same")


def test_stale_files_in_configured_directory_are_removed(tmp_path):
    directory = tmp_path / "prom"
    directory.mkdir()
    stale = directory / "counter_999999.db"
    stale.write_bytes(b"old")
    _configure(tmp_path)
    assert not stale.exists()


def test_prometheus_exporter_builds_no_otel_provider(tmp_path):
    _configure(tmp_path)
    assert metrics.get_meter() is None
    assert metrics._provider is None


def test_missing_prometheus_client_is_graceful(tmp_path, monkeypatch):
    monkeypatch.setitem(sys.modules, "prometheus_client", None)
    monkeypatch.setattr(backend, "_pc", None)
    monkeypatch.setattr(backend, "_load_failed", False)
    metrics.configure(
        {
            "metrics": {"enabled": True, "exporter": "prometheus"},
            "__role": "master",
        }
    )
    assert metrics.is_enabled() is False
    assert metrics.counter("salt.test.none") is metrics._NOOP_COUNTER
    assert "PROMETHEUS_MULTIPROC_DIR" not in os.environ


def _series(body, name):
    """Return ``{labels-part: value}`` for the sample lines of ``name``."""
    out = {}
    for line in body.splitlines():
        if line.startswith(name + "{"):
            labels, value = line.rsplit(" ", 1)
            out[labels] = float(value)
    return out


def test_concurrent_threads_lose_no_counts(tmp_path):
    port = _configure(tmp_path)
    threads_count, per_thread = 16, 1000
    barrier = threading.Barrier(threads_count)

    def work(index):
        # Every thread asks for the instrument and records the very first
        # measurement at the same moment, to race the lazy creation.
        counter = metrics.counter("salt.test.threads")
        barrier.wait()
        for _ in range(per_thread):
            counter.add(1, attributes={"cmd": f"c{index % 4}"})

    threads = [threading.Thread(target=work, args=(i,)) for i in range(threads_count)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(timeout=60)
        assert not thread.is_alive()

    series = _series(_scrape(port), "salt_test_threads_total")
    assert series == {
        f'salt_test_threads_total{{cmd="c{n}"}}': float(per_thread * 4)
        for n in range(4)
    }


def test_scraping_while_threads_write(tmp_path):
    port = _configure(tmp_path)
    writers, per_writer = 4, 2000
    counter = metrics.counter("salt.test.scrape")
    done = threading.Event()
    totals = []
    errors = []

    def write():
        for _ in range(per_writer):
            counter.add(1, attributes={"cmd": "x"})

    def scrape():
        while not done.is_set():
            try:
                series = _series(_scrape(port), "salt_test_scrape_total")
            except Exception as exc:  # pylint: disable=broad-except
                errors.append(exc)
                return
            totals.append(sum(series.values()))

    scraper = threading.Thread(target=scrape)
    threads = [threading.Thread(target=write) for _ in range(writers)]
    scraper.start()
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(timeout=60)
    done.set()
    scraper.join(timeout=60)

    assert not errors, errors
    assert totals, "no scrape completed"
    # A counter never goes down between two scrapes.
    assert totals == sorted(totals)
    final = _series(_scrape(port), "salt_test_scrape_total")
    assert final == {'salt_test_scrape_total{cmd="x"}': float(writers * per_writer)}


def test_target_info_carries_the_resource_attributes(tmp_path):
    port = _configure(
        tmp_path,
        service_name="salt-master-x",
        resource_attributes={"deployment.environment": "prod"},
    )
    body = _scrape(port)
    assert (
        'target_info{deployment_environment="prod",service_name="salt-master-x"} 1.0'
        in body
    )


def test_environment_variable_is_overridden_with_a_warning(
    tmp_path, monkeypatch, caplog
):
    foreign = tmp_path / "foreign"
    foreign.mkdir()
    monkeypatch.setenv("PROMETHEUS_MULTIPROC_DIR", str(foreign))
    with caplog.at_level(logging.WARNING):
        port = _configure(tmp_path)
    metrics.counter("salt.test.env").add(1)
    assert "salt_test_env_total 1.0" in _scrape(port)
    assert os.environ["PROMETHEUS_MULTIPROC_DIR"] == str(tmp_path / "prom")
    assert any("PROMETHEUS_MULTIPROC_DIR" in rec.message for rec in caplog.records)
    assert not list(foreign.iterdir())


def test_bind_failure_is_not_retried(tmp_path, monkeypatch):
    with socket.socket() as busy:
        busy.bind(("127.0.0.1", 0))
        busy.listen()
        opts = {
            "prometheus": {
                "host": "127.0.0.1",
                "port": busy.getsockname()[1],
                "multiproc_dir": str(tmp_path / "prom"),
            }
        }
        assert backend.start(opts) is False

        def retried(*args, **kwargs):
            raise AssertionError("tried to bind again")

        monkeypatch.setattr(backend._pc.lib, "start_http_server", retried)
        assert backend.start(opts) is False


def test_write_failure_is_reported_once(tmp_path, monkeypatch, caplog):
    _configure(tmp_path)
    counter = metrics.counter("salt.test.fail")

    def broken(attributes):
        raise OSError("disk full")

    monkeypatch.setattr(counter, "_child", broken)
    with caplog.at_level(logging.WARNING):
        for _ in range(3):
            counter.add(1)
    warnings = [
        rec
        for rec in caplog.records
        if rec.levelno == logging.WARNING and "salt_test_fail" in rec.getMessage()
    ]
    assert len(warnings) == 1


def test_bad_histogram_boundaries_are_reported_once(caplog):
    with caplog.at_level(logging.WARNING):
        for _ in range(3):
            assert backend._parse_boundaries({"salt.x": ["a", "b"]}) == {}
    warnings = [
        rec
        for rec in caplog.records
        if rec.levelno == logging.WARNING and "salt.x" in rec.getMessage()
    ]
    assert len(warnings) == 1
