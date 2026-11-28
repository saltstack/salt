"""
Verify that a failed Resource discovery leaves the master's inventory intact.
"""

import json
import time
from contextlib import closing

import pytest

import salt.cache
import salt.utils.resource_registry
from tests.conftest import FIPS_TESTRUN

pytestmark = pytest.mark.slow_test

RESOURCE_MODULE = """
import json
from pathlib import Path

RESOURCE_TYPE = {resource_type!r}


def discover(opts):
    inventory = json.loads(Path(opts["discovery_inventory_file"]).read_text())
    yield from inventory[RESOURCE_TYPE]
    if inventory["fail"] == RESOURCE_TYPE:
        raise RuntimeError("Discovery interrupted")


def grains():
    inventory = json.loads(Path(__opts__["discovery_inventory_file"]).read_text())
    return {{"generation": inventory["generation"]}}
"""


@pytest.fixture
def discovery_master(request, salt_factories):
    master = salt_factories.salt_master_daemon(
        "resource-discovery-master",
        overrides={
            "interface": "127.0.0.1",
            "transport": request.config.getoption("--transport"),
            "fips_mode": FIPS_TESTRUN,
            "publish_signing_algorithm": (
                "PKCS1v15-SHA224" if FIPS_TESTRUN else "PKCS1v15-SHA1"
            ),
            # Keep this small inventory below the compaction threshold
            # to exercise discovery independently of registry compaction.
            "resource_registry_compact_tombstone_ratio": 10.0,
        },
    )
    with master.started():
        yield master


def test_failed_discovery_preserves_inventory(discovery_master, tmp_path):
    inventory = tmp_path / "inventory.json"

    def write_inventory(failing, healthy, generation, fail=None):
        inventory.write_text(
            json.dumps(
                {
                    "discovery_failure": failing,
                    "discovery_healthy": healthy,
                    "generation": generation,
                    "fail": fail,
                }
            ),
            encoding="utf-8",
        )

    for resource_type in ("discovery_failure", "discovery_healthy"):
        package = tmp_path / resource_type
        package.mkdir()
        (package / "__init__.py").write_text(
            RESOURCE_MODULE.format(resource_type=resource_type), encoding="utf-8"
        )

    minion = discovery_master.salt_minion_daemon(
        "resource-discovery-failure",
        overrides={
            "fips_mode": FIPS_TESTRUN,
            "encryption_algorithm": "OAEP-SHA224" if FIPS_TESTRUN else "OAEP-SHA1",
            "signing_algorithm": "PKCS1v15-SHA224" if FIPS_TESTRUN else "PKCS1v15-SHA1",
            "resource_types": ["discovery_failure", "discovery_healthy"],
            "resources_dirs": [str(tmp_path)],
            "discovery_inventory_file": str(inventory),
            # Only the failing discovery fills a chunk, so a fix that
            # just skips the final prune still fails this test.
            "resource_register_chunk_size": 3,
        },
    )
    cache = salt.cache.factory(discovery_master.config)
    bank = salt.utils.resource_registry.RESOURCE_GRAINS_BANK
    salt_call = minion.salt_call_cli(timeout=30)

    def assert_inventory(failing_ids, healthy_ids, grains):
        expected_registry = {
            name: set(ids)
            for name, ids in (
                ("discovery_failure", failing_ids),
                ("discovery_healthy", healthy_ids),
            )
            if ids
        }
        deadline = time.monotonic() + 20
        while True:
            cached_grains = {
                srn: (cache.fetch(bank, srn) or {}).get("generation")
                for srn in cache.list(bank)
                if srn.startswith(("discovery_failure:", "discovery_healthy:"))
            }
            if cached_grains == grains or time.monotonic() >= deadline:
                # Open the current mmap after the expected cache update so
                # this process cannot read a prior mapping after compaction.
                with closing(
                    salt.utils.resource_registry.ResourceRegistry(
                        discovery_master.config
                    )
                ) as registry:
                    inventory_by_type = {
                        name: set(ids)
                        for name, ids in registry.get_resources_for_minion(
                            minion.id
                        ).items()
                    }
                assert inventory_by_type == expected_registry
                assert cached_grains == grains
                return
            time.sleep(0.2)

    def refresh():
        ret = salt_call.run("event.fire", "{}", "resource_refresh")
        assert ret.returncode == 0, ret
        assert ret.data is True, ret

    write_inventory(["kept", "old-sibling"], ["healthy-before"], "initial")
    with minion.started():
        assert_inventory(
            ["kept", "old-sibling"],
            ["healthy-before"],
            {
                "discovery_failure:kept": "initial",
                "discovery_failure:old-sibling": "initial",
                "discovery_healthy:healthy-before": "initial",
            },
        )

        write_inventory(
            ["kept", "partial-1", "partial-2", "partial-3"],
            ["healthy-after"],
            "interrupted",
            fail="discovery_failure",
        )
        refresh()
        assert_inventory(
            ["kept", "old-sibling"],
            ["healthy-after"],
            {
                "discovery_failure:kept": "initial",
                "discovery_failure:old-sibling": "initial",
                "discovery_healthy:healthy-after": "interrupted",
            },
        )

        write_inventory(["recovered"], ["healthy-after"], "recovered")
        refresh()
        assert_inventory(
            ["recovered"],
            ["healthy-after"],
            {
                "discovery_failure:recovered": "recovered",
                "discovery_healthy:healthy-after": "recovered",
            },
        )
        # A successful empty discovery still removes the previous IDs.
        write_inventory([], [], "empty")
        refresh()
        assert_inventory([], [], {})
