"""
End-to-end tests for the ``resource_pillar_key`` minion option.

By default the resources framework reads its declarations from
``pillar["resources"]``. Operators can override that with the
:conf_minion:`resource_pillar_key` config option — e.g. to avoid a
collision with existing pillar that already uses ``resources`` for
something else.

These tests exercise the full pipeline (discovery → registration →
targeting) for a minion configured to read from ``salt_resources``
instead. Companion to the unit coverage in
``tests/pytests/unit/utils/test_resources.py``.
"""

import json

import pytest

from tests.pytests.integration.resources.conftest import (
    CUSTOM_KEY_DUMMY_RESOURCES,
    CUSTOM_PILLAR_KEY,
    MINION_ID_CUSTOM_KEY,
)

pytestmark = [pytest.mark.slow_test]


def _parse_cli_dict(ret):
    """Salt CLI sometimes returns the dict directly, sometimes unwrapped
    when a single resource matches. Re-derive a dict from stdout."""
    if isinstance(ret.data, dict):
        return ret.data
    return json.loads(ret.stdout.strip())


def test_custom_pillar_key_discovers_resources(salt_minion_custom_pillar_key):
    """
    The minion's ``opts["resources"]`` (populated by
    ``_discover_resources``) must reflect the ids declared under the
    *custom* pillar key, not the default ``resources`` key.
    """
    salt_call_cli = salt_minion_custom_pillar_key.salt_call_cli(timeout=60)
    ret = salt_call_cli.run("config.get", "resources")
    assert ret.returncode == 0, ret
    data = ret.data
    assert isinstance(data, dict), f"Expected dict, got: {data!r}"
    assert "dummy" in data, f"Custom-key discovery missed: {data!r}"
    dummy = data["dummy"]
    ids = dummy.get("resource_ids") if isinstance(dummy, dict) else dummy
    assert set(ids) == set(CUSTOM_KEY_DUMMY_RESOURCES), (
        f"Custom-key discovery returned wrong ids. "
        f"Expected {set(CUSTOM_KEY_DUMMY_RESOURCES)}, got {set(ids)}."
    )


def test_custom_pillar_key_targets_resources(
    salt_minion_custom_pillar_key, salt_master
):
    """
    With the minion's resources registered under the custom key, the
    master must still target them by id (proves discovery →
    registration → targeting all honour the key).
    """
    salt_cli = salt_master.salt_cli(timeout=60)
    ret = salt_cli.run("-C", "test.ping", minion_tgt="T@dummy")
    assert ret.returncode == 0, ret
    data = _parse_cli_dict(ret)
    for rid in CUSTOM_KEY_DUMMY_RESOURCES:
        assert rid in data, (
            f"Custom-key resource {rid!r} not in T@dummy response: " f"{list(data)}"
        )
        assert data[rid] is True


def test_custom_pillar_key_default_key_does_not_pollute(
    salt_minion_custom_pillar_key,
):
    """
    The pillar also contains an empty ``resources:`` block (the
    framework's default key). The minion must NOT pick up those entries
    — only the configured key matters. Asserts the minion's discovered
    resources match exactly the ids under ``salt_resources``, with no
    extra entries from the default key.
    """
    salt_call_cli = salt_minion_custom_pillar_key.salt_call_cli(timeout=60)
    ret = salt_call_cli.run("config.get", "resource_pillar_key")
    assert ret.returncode == 0, ret
    assert (
        ret.data == CUSTOM_PILLAR_KEY
    ), f"Minion config reports wrong resource_pillar_key: {ret.data!r}"

    ret = salt_call_cli.run("config.get", "resources")
    assert ret.returncode == 0, ret
    data = ret.data
    assert isinstance(data, dict), data
    # Only the custom-key dummy ids should appear; the default
    # ``resources: {}`` block must contribute nothing.
    assert set(data.keys()) == {
        "dummy"
    }, f"Default-key pollution: discovery picked up extra types {list(data)}"
    dummy = data["dummy"]
    ids = dummy.get("resource_ids") if isinstance(dummy, dict) else dummy
    assert set(ids) == set(CUSTOM_KEY_DUMMY_RESOURCES)


def test_custom_pillar_key_minion_id_present(salt_minion_custom_pillar_key):
    """Sanity: the custom-key minion's id is the expected fixture value."""
    assert salt_minion_custom_pillar_key.id == MINION_ID_CUSTOM_KEY
