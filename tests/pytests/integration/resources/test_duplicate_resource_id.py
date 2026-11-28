"""Verify that multiple claims to a Resource cannot cause double execution."""

import json
import time

import pytest

from tests.conftest import FIPS_TESTRUN

pytestmark = pytest.mark.slow_test

DRIVER = """
def discover(opts):
    return ["firewall-a", __opts__["id"] + "-ready"]


def grains():
    return {"owner": __opts__["id"]}
"""

MODULE = """
from pathlib import Path


def mark():
    Path(__opts__["probe_marker"]).touch()
    return __opts__["id"]
"""


STATE = """
def single(fun, name):
    owner = __salt__[fun]()
    return {name: {"result": True, "changes": {"owner": owner}, "name": name, "comment": ""}}
"""


def test_duplicate_resource_only_runs_on_registered_owner(salt_master, tmp_path):
    package = tmp_path / "resources" / "duplicate_probe"
    modules = package / "modules"
    modules.mkdir(parents=True)
    (package / "__init__.py").write_text(DRIVER, encoding="utf-8")
    (modules / "duplicate_probe.py").write_text(MODULE, encoding="utf-8")
    (modules / "state.py").write_text(STATE, encoding="utf-8")

    markers = [tmp_path / "executed-a", tmp_path / "executed-b"]
    minions = [
        salt_master.salt_minion_daemon(
            f"duplicate-resource-{index}",
            overrides={
                "fips_mode": FIPS_TESTRUN,
                "encryption_algorithm": "OAEP-SHA224" if FIPS_TESTRUN else "OAEP-SHA1",
                "signing_algorithm": (
                    "PKCS1v15-SHA224" if FIPS_TESTRUN else "PKCS1v15-SHA1"
                ),
                "module_dirs": [str(tmp_path)],
                "resource_types": ["duplicate_probe"],
                "probe_marker": str(marker),
            },
        )
        for index, marker in enumerate(markers)
    ]
    # Exercise both registration orders across the transport matrix.
    if minions[0].config["transport"] == "zeromq":
        minions.reverse()
        markers.reverse()
    owner, contender = minions
    owner_marker, contender_marker = markers
    runner = salt_master.salt_run_cli(timeout=10)
    cli = salt_master.salt_cli(timeout=10)

    def wait_for_registration(minion):
        deadline = time.monotonic() + 30
        while True:
            ret = runner.run(
                "resource.show_grains", type="duplicate_probe", id=f"{minion.id}-ready"
            )
            if ret.returncode == 0 and (ret.data or {}).get("owner") == minion.id:
                return
            assert time.monotonic() < deadline, ret
            time.sleep(0.2)

    with owner.started():
        wait_for_registration(owner)
        with contender.started():
            wait_for_registration(contender)
            grains = runner.run(
                "resource.show_grains", type="duplicate_probe", id="firewall-a"
            )
            assert grains.returncode == 0, grains
            assert grains.data["owner"] == owner.id
            for args, target in (
                ((), "firewall-a"),
                (("-C",), "T@duplicate_probe:firewall-a"),
            ):
                ret = cli.run(*args, "duplicate_probe.mark", minion_tgt=target)
                assert ret.returncode == 0, ret
                assert json.loads(ret.stdout) == {"firewall-a": owner.id}
                assert owner_marker.exists()
                owner_marker.unlink()
            ret = cli.run(
                "-C",
                "state.single",
                "duplicate_probe.mark",
                "name=mark",
                minion_tgt="T@duplicate_probe:firewall-a",
            )
            assert ret.returncode == 0, ret
            assert set(json.loads(ret.stdout)) == {"firewall-a"}
            assert owner_marker.exists()
            assert not contender_marker.exists()
