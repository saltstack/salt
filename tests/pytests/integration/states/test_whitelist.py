"""
Integration tests for the ``whitelist_state_modules`` minion option.

Complements the exec-loader test
``tests/pytests/integration/loader/test_module_whitelist_dunder.py``.
Boots a real salt-master + salt-minion pair, configures the minion with
``whitelist_state_modules``, dispatches ``state.apply`` from the wire,
and verifies that whitelisted state modules run while non-whitelisted
ones are reported as ``not found`` -- no silent execution.
"""

import pytest

from tests.conftest import FIPS_TESTRUN


@pytest.fixture
def state_whitelisted_minion(salt_master):
    """
    A minion whose ``whitelist_state_modules`` allows only the state
    modules needed to run the tests below.  ``cmd`` state is
    deliberately absent -- that's the escape target we're gating.
    """
    minion = salt_master.salt_minion_daemon(
        "test-state-whitelist-minion",
        overrides={
            "whitelist_state_modules": [
                "test",
                "file",
            ],
            "fips_mode": FIPS_TESTRUN,
            "encryption_algorithm": "OAEP-SHA224" if FIPS_TESTRUN else "OAEP-SHA1",
            "signing_algorithm": (
                "PKCS1v15-SHA224" if FIPS_TESTRUN else "PKCS1v15-SHA1"
            ),
        },
    )
    minion.after_terminate(
        pytest.helpers.remove_stale_minion_key, salt_master, minion.id
    )
    with minion.started():
        yield minion


def test_whitelisted_state_apply_succeeds(salt_cli, state_whitelisted_minion, tmp_path):
    """
    ``state.apply`` of an SLS that declares a whitelisted state module
    (``file.managed``) must run end-to-end -- the state loader loads the
    module and the state produces its normal changes result.
    """
    target = tmp_path / "state-whitelist-marker"
    sls = f"""
create_marker:
  file.managed:
    - name: {target}
    - contents: 'wl-ok'
    - makedirs: True
"""
    ret = salt_cli.run(
        "state.template_str", sls, minion_tgt=state_whitelisted_minion.id
    )
    assert isinstance(ret.data, dict), ret.stdout
    chunk_id = next(iter(ret.data))
    assert ret.data[chunk_id]["result"] is True, ret.data[chunk_id]
    assert target.is_file()


def test_non_whitelisted_state_apply_is_rejected(
    salt_cli, state_whitelisted_minion, tmp_path
):
    """
    ``state.apply`` of an SLS that declares a non-whitelisted state
    module (``cmd.run``) must fail with a ``"Specified state ... was
    not found"`` result and produce NO side effects -- no ``id``
    execution, no file writes.

    ``cmd.run`` is picked because it exists as both an exec module
    (which we're explicitly not restricting here) and a state module
    (which we are).  The point of the gate is precisely that
    ``salt.states.cmd.run`` must not be a back-door around
    ``whitelist_modules``.
    """
    canary = tmp_path / "should-not-exist"
    sls = f"""
try_escape:
  cmd.run:
    - name: 'touch {canary}'
"""
    ret = salt_cli.run(
        "state.template_str", sls, minion_tgt=state_whitelisted_minion.id
    )
    assert isinstance(ret.data, dict), ret.stdout
    chunk_id = next(iter(ret.data))
    chunk = ret.data[chunk_id]
    assert chunk["result"] is False
    assert "cmd.run" in chunk["comment"] or "not found" in chunk["comment"].lower()
    assert not chunk["changes"]
    # And the canary must not have been created.
    assert not canary.exists()


def test_whitelist_modules_still_gates_wire_dispatch(
    salt_cli, state_whitelisted_minion
):
    """
    Sanity: ``whitelist_state_modules`` is orthogonal to
    ``whitelist_modules`` -- because we set only the state-side opt on
    the fixture, wire dispatch of any execution module (e.g.
    ``test.ping``) is unaffected by the state-side gate.
    """
    ret = salt_cli.run("test.ping", minion_tgt=state_whitelisted_minion.id)
    assert ret.data is True


def test_whitelisted_module_state_composes_with_exec(
    salt_cli, state_whitelisted_minion, tmp_path
):
    """
    Sanity: ``file.managed`` -> ``__salt__['file.source_list']`` still
    works.  The new state-side gate does not disturb the two-loader
    exec-module composition path from PR #69983.  Uses the same fixture
    (which only sets ``whitelist_state_modules``, not
    ``whitelist_modules``), so exec modules are fully available.
    """
    target = tmp_path / "compose-ok"
    sls = f"""
compose_check:
  file.managed:
    - name: {target}
    - contents: 'compose-ok'
    - makedirs: True
"""
    ret = salt_cli.run(
        "state.template_str", sls, minion_tgt=state_whitelisted_minion.id
    )
    assert isinstance(ret.data, dict), ret.stdout
    chunk_id = next(iter(ret.data))
    assert ret.data[chunk_id]["result"] is True, ret.data[chunk_id]
    assert target.is_file()
