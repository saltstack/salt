"""
End-to-end test: ``state.apply`` against a dummy resource using a normal
``.sls`` file and the ``salt/states/dummyresource_test.py`` state module.

Verifies that when a state run is dispatched into a resource context, the
``State`` object loads its execution modules through the per-resource loader
so ``__salt__`` in state modules resolves to the resource's own modules
(e.g. ``dummyresource_test.ping`` rather than the managing minion's
``test.ping``).  No ``__resource_funcs__`` dunder is required in the state
module — it uses plain ``__salt__`` like any other state.
"""

import textwrap

import pytest

from tests.pytests.integration.resources.conftest import DUMMY_RESOURCES

pytestmark = [pytest.mark.slow_test]


@pytest.fixture
def dummy_state_sls(salt_master):
    """
    Drop a small ``.sls`` into the master's base file_roots that exercises
    the new ``salt/states/dummyresource_test.py`` state module.
    """
    sls = textwrap.dedent(
        """
        ping the resource:
          dummy_test.present:
            - name: ping the resource
        """
    )
    with salt_master.state_tree.base.temp_file("dummy_resource_state.sls", sls):
        yield "dummy_resource_state"


def _state_results(payload):
    """Yield (state_id, state_dict) pairs from a state.apply return value."""
    if isinstance(payload, dict):
        for sid, sval in payload.items():
            if isinstance(sval, dict) and "result" in sval:
                yield sid, sval


def test_state_apply_targets_dummy_resource_by_id(
    salt_minion, salt_cli, dummy_state_sls
):
    """
    ``salt -C 'T@dummy:dummy-01' state.apply <sls>`` must:

    * Be delivered to the managing minion: ``state.apply`` is in
      :data:`salt.utils.minions._MERGE_RESOURCE_FUNS` so the master remaps
      the wait list from the resource id to the managing minion id and
      the managing minion runs the state for ``dummy-01`` inline,
      returning ONE combined dict.
    * Apply the state only to ``dummy-01`` (not the other dummy resources)
      via the per-resource execution loader: ``__salt__["test.ping"]``
      resolves to ``salt.modules.dummyresource_test.ping``, which delegates
      to ``salt.resource.dummy.ping``.
    """
    target_id = DUMMY_RESOURCES[0]
    ret = salt_cli.run(
        "-C", "state.apply", dummy_state_sls, minion_tgt=f"T@dummy:{target_id}"
    )
    assert ret.returncode == 0, ret

    data = ret.data
    assert isinstance(data, dict), f"Expected dict, got: {data!r}"
    # Managing minion is the response key for merge-mode functions; the
    # other dummy resources must not appear as separate keys.
    assert salt_minion.id in data, f"Managing minion missing from response: {data!r}"
    for other in DUMMY_RESOURCES[1:]:
        assert other not in data, f"Unexpected {other!r} in response: {data}"

    minion_payload = data[salt_minion.id]
    assert isinstance(minion_payload, dict), minion_payload

    # The merged payload should contain a state result whose key encodes the
    # target resource id (master merge format prefixes the state id with the
    # rid so operators see per-resource provenance).
    found = False
    for sid, sval in _state_results(minion_payload):
        if target_id in sid and "dummy_test" in sid:
            found = True
            assert sval["result"] is True, (sid, sval)
            assert "ping returned True" in sval.get("comment", "")
    assert found, (
        f"No dummy_test.present result for {target_id!r} found in merged "
        f"managing-minion payload: {minion_payload!r}"
    )
