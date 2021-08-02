"""
Integration tests for the saltutil module.
"""


import pathlib
import shutil

import pytest

pytestmark = [
    pytest.mark.windows_whitelisted,
]


@pytest.fixture(scope="module", autouse=True)
def setup_test_module(salt_call_cli, salt_master, salt_minion):
    # Whell functions, on a minion, must run with the master running
    # along side the minion.
    # We copy the master config to the minion's configuration directory just
    # for this test since the test suite master and minion(s) do not share the
    # same configuration directory
    src = salt_master.config["conf_file"]
    dst = pathlib.Path(salt_minion.config_dir) / "master"
    shutil.copyfile(src, str(dst))
    try:
        yield
    finally:
        dst.unlink()


@pytest.fixture(autouse=True)
def refresh_pillar(salt_cli, salt_minion, salt_sub_minion):
    ret = salt_cli.run("saltutil.refresh_pillar", wait=True, minion_tgt="*")
    assert ret.exitcode == 0
    assert ret.json
    assert salt_minion.id in ret.json
    assert ret.json[salt_minion.id] is True
    assert salt_sub_minion.id in ret.json
    assert ret.json[salt_sub_minion.id] is True


@pytest.mark.slow_test
def test_wheel_just_function(salt_call_cli, salt_minion, salt_sub_minion):
    """
    Tests using the saltutil.wheel function when passing only a function.
    """
    ret = salt_call_cli.run("saltutil.wheel", "minions.connected")
    assert ret.exitcode == 0
    assert ret.json
    assert salt_minion.id in ret.json["return"]
    assert salt_sub_minion.id in ret.json["return"]


@pytest.mark.slow_test
def test_wheel_with_arg(salt_call_cli):
    """
    Tests using the saltutil.wheel function when passing a function and an arg.
    """
    ret = salt_call_cli.run("saltutil.wheel", "key.list", "minion")
    assert ret.exitcode == 0
    assert ret.json["return"] == {}


@pytest.mark.slow_test
def test_wheel_no_arg_raise_error(salt_call_cli):
    """
    Tests using the saltutil.wheel function when passing a function that requires
    an arg, but one isn't supplied.
    """
    ret = salt_call_cli.run("--retcode-passthrough", "saltutil.wheel", "key.list")
    assert ret.exitcode == 0


@pytest.mark.slow_test
def test_wheel_with_kwarg(salt_call_cli):
    """
    Tests using the saltutil.wheel function when passing a function and a kwarg.
    This function just generates a key pair, but doesn't do anything with it. We
    just need this for testing purposes.
    """
    ret = salt_call_cli.run("saltutil.wheel", "key.gen", keysize=1024)
    assert ret.exitcode == 0
    assert "pub" in ret.json["return"]
    assert "priv" in ret.json["return"]
