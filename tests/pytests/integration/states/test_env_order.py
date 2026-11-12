"""
Integration regression tests for issue #70618.

With ``env_order`` configured on the master, environments that are present on
the fileserver but absent from ``env_order`` must still be considered
available by ``LazyAvailStates``. Before PR #70695 ``BaseHighState._get_envs``
unconditionally filtered the fileserver's env list through ``env_order``, so
``render_highstate`` reported::

    No matching salt environment for environment '<env>' found

for any saltenv (for example a gitfs branch exposed through
``gitfs_saltenv_whitelist``) that could not be enumerated in ``env_order``.

These tests reproduce the end-to-end behaviour over the ``roots`` fileserver
because ``BaseHighState._get_envs`` reads ``file_roots`` and
``client.envs()``; whether the extra env is served by ``roots`` or ``gitfs``
does not change the code path that was broken.
"""

import shutil

import pytest
from saltfactories.utils import random_string

from tests.conftest import FIPS_TESTRUN

pytestmark = [
    pytest.mark.slow_test,
]


@pytest.fixture(scope="module")
def env_order_state_tree(tmp_path_factory):
    """
    Build three file_roots directories:

    * ``base`` and ``prod`` are inside ``env_order``.
    * ``feature_branch`` is on the fileserver but deliberately NOT listed in
      ``env_order`` -- this is the environment that was hidden by the bug.

    Each env ships a trivial ``mystate/init.sls`` so the rendered high data
    carries an env-specific marker. That lets the assertions distinguish which
    env actually produced the state instead of relying on a matching error
    string.
    """
    tree = tmp_path_factory.mktemp("env-order-70618")
    base_root = tree / "base"
    prod_root = tree / "prod"
    feature_root = tree / "feature_branch"
    for root in (base_root, prod_root, feature_root):
        (root / "mystate").mkdir(parents=True)

    (base_root / "mystate" / "init.sls").write_text(
        "env marker base:\n  test.nop:\n    - name: base\n",
        encoding="utf-8",
    )
    (prod_root / "mystate" / "init.sls").write_text(
        "env marker prod:\n  test.nop:\n    - name: prod\n",
        encoding="utf-8",
    )
    (feature_root / "mystate" / "init.sls").write_text(
        "env marker feature_branch:\n  test.nop:\n    - name: feature_branch\n",
        encoding="utf-8",
    )
    try:
        yield {
            "base": [str(base_root)],
            "prod": [str(prod_root)],
            "feature_branch": [str(feature_root)],
        }
    finally:
        shutil.rmtree(str(tree), ignore_errors=True)


@pytest.fixture(scope="module")
def env_order_master(salt_factories, env_order_state_tree):
    """
    A dedicated master whose ``env_order`` is intentionally narrower than its
    ``file_roots``. This is the configuration that triggered #70618.
    """
    config_overrides = {
        "file_roots": env_order_state_tree,
        "env_order": ["base", "prod"],
        "top_file_merging_strategy": "merge_all",
        "open_mode": True,
        "fips_mode": FIPS_TESTRUN,
        "publish_signing_algorithm": (
            "PKCS1v15-SHA224" if FIPS_TESTRUN else "PKCS1v15-SHA1"
        ),
    }
    factory = salt_factories.salt_master_daemon(
        random_string("env-order-master-", uppercase=False),
        overrides=config_overrides,
    )
    with factory.started():
        yield factory


@pytest.fixture(scope="module")
def env_order_minion(env_order_master, env_order_state_tree):
    config_overrides = {
        "file_roots": env_order_state_tree,
        "env_order": ["base", "prod"],
        "open_mode": True,
        "fips_mode": FIPS_TESTRUN,
        "encryption_algorithm": "OAEP-SHA224" if FIPS_TESTRUN else "OAEP-SHA1",
        "signing_algorithm": "PKCS1v15-SHA224" if FIPS_TESTRUN else "PKCS1v15-SHA1",
    }
    factory = env_order_master.salt_minion_daemon(
        random_string("env-order-minion-", uppercase=False),
        overrides=config_overrides,
    )
    with factory.started():
        yield factory


@pytest.fixture(scope="module")
def env_order_call_cli(env_order_minion):
    return env_order_minion.salt_call_cli(timeout=60)


def _assert_mystate_rendered(ret, expected_env):
    """
    ``state.show_sls`` returns the rendered high data as a dict. The fixture
    uses a per-env state id ``env marker <env>`` so a successful render lands
    exactly one key whose value points at ``test.nop``.
    """
    assert ret.returncode == 0, ret
    assert isinstance(ret.data, dict), ret.data
    marker = f"env marker {expected_env}"
    assert marker in ret.data, (
        f"Expected rendered state id {marker!r} for saltenv={expected_env!r}, "
        f"got keys: {sorted(ret.data)}"
    )
    # Guard against the regression-mode output where render_highstate returns
    # a list of error strings instead of a dict of rendered states.
    assert "test" in ret.data[marker], ret.data[marker]


def test_show_sls_saltenv_outside_env_order(env_order_call_cli):
    """
    Regression test for #70618.

    ``state.show_sls`` with ``saltenv=feature_branch`` must render the sls
    even though ``feature_branch`` is not listed in ``env_order``. Before PR
    #70695 this returned ``["No matching salt environment for environment
    'feature_branch' found"]``.
    """
    ret = env_order_call_cli.run("state.show_sls", "mystate", saltenv="feature_branch")
    assert ret.returncode == 0, ret
    # When the bug is present, ``ret.data`` is a list whose single element is
    # the "No matching salt environment" string. Catch that explicitly so the
    # failure message points at the right fix.
    assert not (
        isinstance(ret.data, list)
        and any("No matching salt environment" in str(item) for item in ret.data)
    ), (
        "render_highstate rejected saltenv='feature_branch' even though it is "
        f"served by file_roots. This is the #70618 regression. ret.data={ret.data!r}"
    )
    _assert_mystate_rendered(ret, "feature_branch")


def test_show_sls_saltenv_inside_env_order_still_works(env_order_call_cli):
    """
    The fix must not regress the happy path: an env that *is* in
    ``env_order`` must continue to render.
    """
    ret = env_order_call_cli.run("state.show_sls", "mystate", saltenv="prod")
    _assert_mystate_rendered(ret, "prod")


def test_show_sls_unknown_saltenv_still_errors(env_order_call_cli):
    """
    The fix widens which envs count as available; it must not silence the
    error for environments that truly do not exist. Asking for a saltenv that
    is in neither ``env_order`` nor ``file_roots`` must still produce the
    "No matching salt environment" diagnostic.
    """
    ret = env_order_call_cli.run("state.show_sls", "mystate", saltenv="doesnotexist")
    # ``state.show_sls`` returns a non-zero retcode via EX_STATE_COMPILER_ERROR
    # when render_highstate reports errors.
    assert ret.returncode != 0, ret
    error_payload = ret.data
    if isinstance(error_payload, dict):
        # ``state.show_sls`` surfaces compiler errors via the "comment" key in
        # some code paths; fall back to a string representation for the
        # assertion to stay robust across shapes.
        error_payload = str(error_payload)
    assert "No matching salt environment" in str(error_payload), ret


def test_sls_saltenv_outside_env_order_renders(env_order_call_cli):
    """
    ``state.sls`` exercises the same ``render_highstate`` path as
    ``state.show_sls`` but also executes the states. Verify the full
    execution path recovers for an env outside ``env_order``.
    """
    ret = env_order_call_cli.run(
        "state.sls", "mystate", saltenv="feature_branch", test=True
    )
    assert ret.returncode == 0, ret
    assert isinstance(ret.data, dict), ret.data
    key = next(
        (k for k in ret.data if k.startswith("test_|-env marker feature_branch")),
        None,
    )
    assert key is not None, (
        "state.sls did not execute mystate from saltenv='feature_branch'. "
        f"ret.data keys={sorted(ret.data)}"
    )
    assert ret.data[key].get("result") is True, ret.data[key]
