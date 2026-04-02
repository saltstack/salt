"""
End-to-end integration tests for Salt Resources using the dummy resource type.

These tests verify the full dispatch pipeline:

  salt CLI → master targeting (CkMinions) → minion (_resolve_resource_targets)
  → resource loader → return → master re-key → CLI response

The minion under test is configured with::

    resources:
      dummy:
        - dummy-01
        - dummy-02
    multiprocessing: False

The ``dummy`` resource module (``salt/resource/dummy.py``) and its execution
module (``salt/modules/dummyresource_test.py``) are pure-Python in-process
implementations that require no external services.
"""

import pytest

from tests.pytests.integration.resources.conftest import DUMMY_RESOURCES

pytestmark = [pytest.mark.slow_test]


def test_minion_has_resources_configured(salt_minion, salt_call_cli):
    """Sanity check: the minion must report its resource config before other tests run."""
    ret = salt_call_cli.run("config.get", "resources")
    assert ret.returncode == 0, ret
    data = ret.data
    assert isinstance(data, dict), f"Expected dict, got: {data!r}"
    assert "dummy" in data, f"'dummy' missing from config.get resources: {data}"
    assert set(data["dummy"]) == {
        "dummy-01",
        "dummy-02",
    }, f"Unexpected resource IDs: {data['dummy']}"


def test_glob_wildcard_returns_minion_and_resources(salt_minion, salt_cli):
    """
    ``salt '*' test.ping`` must return ``True`` for the managing minion *and*
    for every resource it manages.

    This exercises the full pipeline:
    - Master ``_augment_with_resources`` adds dummy-01/dummy-02 to the
      expected-minion set so the response window stays open.
    - Minion ``_resolve_resource_targets`` dispatches two resource jobs.
    - Each resource job returns via ``_thread_return`` with ``resource_id``.
    - Master ``_return`` remaps ``resource_id`` → ``id`` before delivering.
    """
    ret = salt_cli.run("test.ping", minion_tgt="*")
    assert ret.returncode == 0, ret

    data = ret.data
    assert isinstance(data, dict), f"Expected dict, got: {data!r}"

    # The managing minion must respond.
    assert (
        salt_minion.id in data
    ), f"Managing minion '{salt_minion.id}' not in response: {list(data)}"
    assert data[salt_minion.id] is True

    # Every configured resource must also respond.
    for rid in DUMMY_RESOURCES:
        assert rid in data, f"Resource '{rid}' missing from response: {list(data)}"
        assert data[rid] is True, f"Resource '{rid}' returned non-True: {data[rid]}"


def test_T_at_full_srn_returns_only_that_resource(salt_minion, salt_cli):
    """
    ``salt -C 'T@dummy:dummy-01' test.ping`` must return a response keyed to
    ``dummy-01`` only — not to the managing minion or to dummy-02.

    This exercises the compound-match targeting path:
    - Master ``_check_resource_minions`` resolves ``T@dummy:dummy-01`` to the
      single resource ID ``dummy-01`` and the managing minion as the delivery
      target.
    - Minion ``_resolve_resource_targets`` (compound path) dispatches only to
      dummy-01 because the T@ term matches exactly one resource.
    """
    ret = salt_cli.run("--compound", "test.ping", minion_tgt="T@dummy:dummy-01")
    assert ret.returncode == 0, ret

    data = ret.data
    assert isinstance(data, dict), f"Expected dict, got: {data!r}"
    assert data == {
        "dummy-01": True
    }, f"Expected only dummy-01 in response, got: {data}"


def test_T_at_bare_type_returns_all_resources_of_type(salt_minion, salt_cli):
    """
    ``salt -C 'T@dummy' test.ping`` must return ``True`` for every dummy
    resource — dummy-01 and dummy-02 — without including the managing minion.
    """
    ret = salt_cli.run("--compound", "test.ping", minion_tgt="T@dummy")
    assert ret.returncode == 0, ret

    data = ret.data
    assert isinstance(data, dict), f"Expected dict, got: {data!r}"

    for rid in DUMMY_RESOURCES:
        assert (
            rid in data
        ), f"Resource '{rid}' missing from T@dummy response: {list(data)}"
        assert data[rid] is True

    # The managing minion should NOT be in the T@-only response.
    assert (
        salt_minion.id not in data
    ), "Managing minion unexpectedly included in T@dummy response"


def test_unknown_resource_function_fails_loudly(salt_minion, salt_cli):
    """
    Calling a function that does not exist on a resource must return an error
    string, not silently fall through to the managing minion's own module.

    This guards against the pre-resource behaviour where an unknown function
    for a resource target would execute on the minion itself.
    """
    ret = salt_cli.run(
        "--compound", "nonexistent.function", minion_tgt="T@dummy:dummy-01"
    )
    # The command fails (non-zero) because the function is unknown.
    assert ret.returncode != 0 or (
        isinstance(ret.data, dict)
        and isinstance(ret.data.get("dummy-01"), str)
        and "nonexistent" in ret.data["dummy-01"].lower()
    ), f"Expected error for unknown resource function, got: {ret.data!r}"
