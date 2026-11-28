"""Verify per-device driver logging through master-issued Resource jobs."""

import json
from pathlib import Path

import pytest

from tests.conftest import FIPS_TESTRUN

pytestmark = pytest.mark.slow_test

DRIVER = """
import logging

log = logging.getLogger("resource_driver_probe")


def discover(opts):
    return opts["probe_ids"]


def probe():
    resource_id = __resource__["id"]
    log.warning("Driver marker for %s", resource_id)
    try:
        raise RuntimeError("Driver failure for " + resource_id)
    except RuntimeError:
        log.exception("Driver logged an exception")
        raise
"""

MODULE = """
def probe():
    return __resource_funcs__["logging_probe.probe"]()
"""


@pytest.mark.parametrize("multiprocessing", [False, True], ids=["threads", "processes"])
def test_devices_use_separate_log_files(salt_master, tmp_path, multiprocessing):
    suffix = "processes" if multiprocessing else "threads"
    first_id = f"device-a-{suffix}"
    second_id = f"device-b-{suffix}"
    shared_id = f"device-shared-{suffix}"
    ids = [first_id, second_id, shared_id]
    paths = {device: tmp_path / f"{device}.log" for device in ids[:2]}

    resource = tmp_path / "resources" / "logging_probe"
    modules = resource / "modules"
    modules.mkdir(parents=True)
    (resource / "__init__.py").write_text(DRIVER, encoding="utf-8")
    (modules / "logprobe.py").write_text(MODULE, encoding="utf-8")

    minion = salt_master.salt_minion_daemon(
        f"resource-logging-{suffix}",
        overrides={
            "fips_mode": FIPS_TESTRUN,
            "encryption_algorithm": "OAEP-SHA224" if FIPS_TESTRUN else "OAEP-SHA1",
            "signing_algorithm": "PKCS1v15-SHA224" if FIPS_TESTRUN else "PKCS1v15-SHA1",
            "multiprocessing": multiprocessing,
            "log_level_logfile": "warning",
            "module_dirs": [str(tmp_path)],
            "resource_types": ["logging_probe"],
            "probe_ids": ids,
            "resource_log_files": {
                f"logging_probe:{device}": str(path) for device, path in paths.items()
            },
        },
    )
    with minion.started():
        target = " or ".join(f"T@logging_probe:{device}" for device in ids)
        ret = salt_master.salt_cli(timeout=20).run(
            "--out-indent=-1", "-C", "logprobe.probe", minion_tgt=target
        )
        results = {}
        for line in ret.stdout.splitlines():
            results.update(json.loads(line))
        assert results.keys() == set(ids), ret
        for device in ids:
            assert f"Driver failure for {device}" in results[device], ret

        paths[shared_id] = Path(minion.config["log_file"])
        for device, path in paths.items():
            messages = path.read_text(encoding="utf-8")
            assert f"[resource_id={device!r}] Driver marker for {device}" in messages
            assert (
                f"[resource_id={device!r}] The minion function caused an exception"
                in messages
            )
            assert f"[resource_id={device!r}] Driver logged an exception" in messages
            assert "Traceback (most recent call last):" in messages
            assert f"\nRuntimeError: Driver failure for {device}" in messages
            for other in set(ids) - {device}:
                assert f"Driver marker for {other}" not in messages
                assert f"\nRuntimeError: Driver failure for {other}" not in messages
