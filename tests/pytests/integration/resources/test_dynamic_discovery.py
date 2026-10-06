"""
End-to-end integration tests for the discovery side of the resources
framework.

Uses the synthetic ``dynamic_test`` resource type defined in
``conftest.py`` — a resource type whose ``discover()`` reads its ids
from a top-level pillar key (``_dynamic_test_ids``) rather than the
standard ``resources:`` subtree. That's the only shape today that
exercises the "discover() is the sole authority for ids" code path
end-to-end. Dummy and ssh both re-read pillar's resources subtree, so
the question of "what happens when pillar and discover disagree" is
unobservable through them.

Tests covered:

* Ids returned by ``discover()`` register with the master even when
  pillar's ``resources.dynamic_test`` block declares no ids.
* When pillar declares ids under ``resources.dynamic_test.resource_ids``
  AND ``discover()`` returns a different set, the master sees only
  ``discover()``'s set — current contract: discover is authoritative,
  no framework-level merge.
* Mutating ``_dynamic_test_ids`` in pillar and running
  ``saltutil.refresh_pillar`` makes the master pick up the new ids
  within a bounded poll window.
* Same for removal: ids that disappear from pillar disappear from the
  master's resource_grains bank after refresh.
"""

import time

import pytest

from tests.pytests.integration.resources.conftest import (
    sync_resources_and_refresh,
    write_dynamic_ids_pillar,
)

pytestmark = [pytest.mark.slow_test]


def _poll_for_ids(salt_master, expected_ids, timeout=20):
    """Poll ``resource.list_grains`` until the master sees expected ids.

    Returns the final list of dynamic_test SRNs the master knows about.
    Raises ``AssertionError`` if the expected set isn't reached within
    ``timeout`` seconds.
    """
    salt_run = salt_master.salt_run_cli(timeout=30)
    expected = {f"dynamic_test:{rid}" for rid in expected_ids}
    deadline = time.monotonic() + timeout
    last_seen = None
    while time.monotonic() < deadline:
        ret = salt_run.run("resource.list_grains", _timeout=30)
        if ret.returncode == 0 and isinstance(ret.data, dict):
            last_seen = {srn for srn in ret.data if srn.startswith("dynamic_test:")}
            if last_seen == expected:
                return last_seen
        time.sleep(1)
    raise AssertionError(
        f"Master did not converge on expected dynamic_test SRNs. "
        f"Expected {expected}, last saw {last_seen}"
    )


def test_dynamic_discovery_registers_ids_not_in_pillar_resources(
    salt_minion_dynamic, salt_master
):
    """
    Pillar's ``resources.dynamic_test`` block is empty — no ``resource_ids``
    declared there — yet ``discover()`` returns ids read from a separate
    top-level pillar key. The master must register exactly those ids.
    """
    expected = ["d-alpha", "d-beta"]
    with write_dynamic_ids_pillar(salt_master, expected):
        salt_call_cli = salt_minion_dynamic.salt_call_cli(timeout=120)
        sync_resources_and_refresh(salt_call_cli)
        seen = _poll_for_ids(salt_master, expected)
    assert seen == {f"dynamic_test:{rid}" for rid in expected}


def test_dynamic_discovery_overrides_pillar_resource_ids(
    salt_minion_dynamic, salt_master
):
    """
    Pillar declares ids under the standard
    ``resources.dynamic_test.resource_ids`` shape that other types use,
    but ``dynamic_test.discover()`` ignores that key and reads from
    ``_dynamic_test_ids`` instead.

    The framework today stores ``discover()``'s output verbatim — the
    pillar-declared ``resource_ids`` are NOT merged in. This pins the
    current contract; when union-with-override lands later the
    assertion will need updating.
    """
    discovered = ["live-1", "live-2"]
    body = (
        "resources:\n"
        "  dynamic_test:\n"
        "    resource_ids:\n"
        "      - stale-pillar-id\n"
        f"_dynamic_test_ids: {discovered!r}\n"
    )
    with salt_master.pillar_tree.base.temp_file("dynamic_resources.sls", body):
        salt_call_cli = salt_minion_dynamic.salt_call_cli(timeout=120)
        sync_resources_and_refresh(salt_call_cli)
        seen = _poll_for_ids(salt_master, discovered)
    assert seen == {f"dynamic_test:{rid}" for rid in discovered}
    assert "dynamic_test:stale-pillar-id" not in seen, (
        "Pillar's resources.dynamic_test.resource_ids must not be merged "
        "into the registered set when discover() returns its own ids "
        "(current framework contract: discover() is authoritative)."
    )


def test_dynamic_discovery_refresh_picks_up_new_ids(salt_minion_dynamic, salt_master):
    """
    Start with a single id; rewrite pillar to add a second; refresh;
    confirm the master sees both within the poll window.
    """
    salt_call_cli = salt_minion_dynamic.salt_call_cli(timeout=120)

    # Initial state: single id.
    with write_dynamic_ids_pillar(salt_master, ["d-only"]):
        sync_resources_and_refresh(salt_call_cli)
        _poll_for_ids(salt_master, ["d-only"])

    # Replace with two ids and re-sync.
    with write_dynamic_ids_pillar(salt_master, ["d-only", "d-new"]):
        sync_resources_and_refresh(salt_call_cli)
        seen = _poll_for_ids(salt_master, ["d-only", "d-new"])
    assert seen == {"dynamic_test:d-only", "dynamic_test:d-new"}


def test_dynamic_discovery_removed_ids_disappear_from_master(
    salt_minion_dynamic, salt_master
):
    """
    Inverse of :func:`test_dynamic_discovery_refresh_picks_up_new_ids`:
    start with two ids, drop to one, confirm the dropped id is gone
    from the master's resource_grains bank.
    """
    salt_call_cli = salt_minion_dynamic.salt_call_cli(timeout=120)

    with write_dynamic_ids_pillar(salt_master, ["d-keep", "d-drop"]):
        sync_resources_and_refresh(salt_call_cli)
        _poll_for_ids(salt_master, ["d-keep", "d-drop"])

    with write_dynamic_ids_pillar(salt_master, ["d-keep"]):
        sync_resources_and_refresh(salt_call_cli)
        seen = _poll_for_ids(salt_master, ["d-keep"])
    assert seen == {"dynamic_test:d-keep"}
    assert "dynamic_test:d-drop" not in seen
