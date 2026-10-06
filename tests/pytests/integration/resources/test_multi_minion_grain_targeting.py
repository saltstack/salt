"""
Multi-minion integration coverage for grain targeting of resources.

The single-minion ``test_dummy_resource.py`` suite verifies that one
minion's resources reach the master's ``resource_grains`` bank and that
``-G`` matches them. This module spins up a *second* minion (via the
``salt_minion_2`` package fixture) managing a disjoint set of dummy
resources and confirms:

* The master's ``resource_grains`` bank holds entries from both minions.
* ``salt -G '<key>:<value>'`` matches resources from EITHER minion when
  both have the matching grain (here: ``dummy_grain_1:one`` is the same
  static value for every dummy resource on every minion).
* The managing minions themselves are excluded from the response — the
  match comes purely from the per-resource grain bank.
"""

import pytest

from tests.pytests.integration.resources.conftest import (
    DUMMY_RESOURCES,
    DUMMY_RESOURCES_2,
    MINION_ID,
    MINION_ID_2,
)

pytestmark = [pytest.mark.slow_test, pytest.mark.timeout(240)]


def test_grain_targeting_matches_resources_across_two_minions(
    salt_minion, salt_minion_2, salt_cli
):
    """
    ``salt -G 'dummy_grain_1:one' test.ping`` must include the dummy
    resources managed by **both** minions in a single response. Every
    dummy resource statically reports ``dummy_grain_1: one`` (see
    ``salt.resources.dummy.grains``), so the grain match should hit all
    five resources (3 on minion-1 + 2 on minion-2) and exclude the
    managing minions themselves.
    """
    ret = salt_cli.run("-G", "test.ping", minion_tgt="dummy_grain_1:one")
    assert ret.returncode == 0, ret

    data = ret.data
    assert isinstance(data, dict), f"Expected dict, got: {data!r}"

    expected = set(DUMMY_RESOURCES) | set(DUMMY_RESOURCES_2)
    for rid in expected:
        assert rid in data, f"Resource {rid!r} missing from response: {list(data)}"
        assert data[rid] is True

    assert (
        MINION_ID not in data
    ), f"Managing minion '{MINION_ID}' must not match a resource grain"
    assert (
        MINION_ID_2 not in data
    ), f"Second minion '{MINION_ID_2}' must not match a resource grain"


def test_grain_targeting_unique_resource_id_picks_correct_minion(
    salt_minion, salt_minion_2, salt_cli
):
    """
    The ``resource_id`` grain is unique per resource. Targeting
    ``resource_id:dummy-05`` must hit only the resource on minion-2;
    minion-1 has no ``dummy-05``. This proves the master picks the
    right SRN out of the union and dispatches to the owning minion.
    """
    ret = salt_cli.run("-G", "test.ping", minion_tgt="resource_id:dummy-05")
    assert ret.returncode == 0, ret

    # Salt-factories may unwrap a single-key envelope when only one id
    # responds. Accept both shapes.
    if isinstance(ret.data, dict):
        assert ret.data.get("dummy-05") is True
        # No minion-1-owned resource may appear.
        for rid in DUMMY_RESOURCES:
            assert (
                rid not in ret.data
            ), f"Unexpected {rid!r} in response: {list(ret.data)}"
    else:
        assert ret.data is True
