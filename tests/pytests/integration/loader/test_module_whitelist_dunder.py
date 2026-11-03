"""
Integration tests for the split-loader behavior in ``salt.loader.minion_mods``.

``minion_mods()`` returns a whitelist-filtered LazyLoader for remote
dispatch, but packs an *unfiltered* loader as ``__salt__`` inside every
loaded module.

Effect on a whitelisted minion:
  - Remote publishers can only invoke functions from whitelisted modules.
  - A whitelisted module can still compose with non-whitelisted modules
    via ``__salt__[...]``.
"""

import pytest

from tests.conftest import FIPS_TESTRUN

SECTEST_MODULE = """
def run(cmd):
    return __salt__["cmd.run"](cmd)
"""


@pytest.fixture
def whitelisted_minion(salt_master):
    """
    A minion configured with ``whitelist_modules: [test, sectest, saltutil]``.
    ``cmd`` is *deliberately absent* from the whitelist.
    """
    minion = salt_master.salt_minion_daemon(
        "test-whitelist-dunder-minion",
        overrides={
            "whitelist_modules": [
                "test",
                "sectest",
                "saltutil",
                # Needed for the SLS-render tests below (state.template_str
                # touches config/grains/pillar/slsutil during compilation).
                "state",
                "config",
                "grains",
                "pillar",
                "slsutil",
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
    with salt_master.state_tree.base.temp_file("_modules/sectest.py", SECTEST_MODULE):
        with minion.started():
            salt_cli = salt_master.salt_cli()
            salt_cli.run("saltutil.sync_modules", minion_tgt=minion.id)
            yield minion


def test_whitelisted_function_returns(salt_cli, whitelisted_minion):
    """
    ``test.ping`` is on the whitelist and must return normally.
    """
    ret = salt_cli.run("test.ping", minion_tgt=whitelisted_minion.id)
    assert ret.data is True


def test_nonwhitelisted_function_is_blocked(salt_cli, whitelisted_minion):
    """
    ``cmd.run`` is *not* on the whitelist. Remote publish must not
    execute it: the minion's outer (filtered) loader has no ``cmd``
    entry, so the function is unavailable and the CLI reports either
    "'cmd.run' is not available." or "Minion did not return" -- both
    prove the whitelist rejected the call.
    """
    ret = salt_cli.run(
        "cmd.run", "echo blocked", minion_tgt=whitelisted_minion.id, _timeout=15
    )
    data = str(ret.data or "")
    assert "not available" in data or "did not return" in data


def test_whitelisted_module_reaches_nonwhitelisted_via_dunder(
    salt_cli, whitelisted_minion
):
    """
    ``sectest`` is whitelisted; its ``run()`` internally calls
    ``__salt__['cmd.run']``. Because the packed ``__salt__`` is the
    *unfiltered* loader, the call succeeds even though direct remote
    dispatch of ``cmd.run`` is blocked (previous test).
    """
    ret = salt_cli.run(
        "sectest.run", "echo hello-from-dunder", minion_tgt=whitelisted_minion.id
    )
    assert ret.data == "hello-from-dunder"


def test_sls_render_can_call_whitelisted_module(salt_cli, whitelisted_minion):
    """
    SLS files render on the minion with the whitelist-filtered loader
    exposed as ``salt`` / ``__salt__``. A whitelisted module call inside
    the template must render normally and the resulting state must run.
    """
    template = (
        "{% set r = salt['test.echo']('hi-from-sls') %}\n"
        "probe:\n"
        "  test.nop:\n"
        "    - name: {{ r }}\n"
    )
    ret = salt_cli.run("state.template_str", template, minion_tgt=whitelisted_minion.id)
    # state.template_str returns a dict keyed by state chunk id.
    assert isinstance(ret.data, dict)
    key = next(iter(ret.data))
    assert ret.data[key]["result"] is True
    assert ret.data[key]["name"] == "hi-from-sls"


def test_sls_render_cannot_call_nonwhitelisted_module(salt_cli, whitelisted_minion):
    """
    ``cmd`` is not on ``whitelist_modules``. A template that tries
    ``salt['cmd.run'](...)`` must fail *at render time* -- the render
    pipeline receives the same filtered loader that the wire dispatch
    uses, not the unfiltered ``salt_dunder`` that execution modules see.

    Jinja surfaces the missing key as ``UndefinedError: '...AliasedLoader
    object' has no attribute 'cmd.run'``.
    """
    template = (
        "{% set r = salt['cmd.run']('id') %}\n"
        "probe:\n"
        "  test.nop:\n"
        "    - name: {{ r }}\n"
    )
    ret = salt_cli.run("state.template_str", template, minion_tgt=whitelisted_minion.id)
    text = str(ret.data or ret.stdout)
    assert "cmd.run" in text
    assert "UndefinedError" in text or "no attribute" in text
