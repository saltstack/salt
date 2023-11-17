"""
Verify salt-ssh fails with a retcode > 0 when a state rendering fails.
"""

import pytest

from salt.defaults.exitcodes import EX_AGGREGATE

pytestmark = [
    pytest.mark.skip_on_windows(reason="salt-ssh not available on Windows"),
    pytest.mark.slow_test,
]


@pytest.fixture(scope="module", autouse=True)
def state_tree_render_fail(base_env_state_tree_root_dir):
    top_file = """
    base:
      'localhost':
        - fail_render
      '127.0.0.1':
        - fail_render
    """
    state_file = r"""
    abc var is not defined {{ abc }}:
      test.nop
    """
    top_tempfile = pytest.helpers.temp_file(
        "top.sls", top_file, base_env_state_tree_root_dir
    )
    state_tempfile = pytest.helpers.temp_file(
        "fail_render.sls", state_file, base_env_state_tree_root_dir
    )
    with top_tempfile, state_tempfile:
        yield


def test_retcode_state_sls_render_exception(salt_ssh_cli):
    ret = salt_ssh_cli.run("state.sls", "fail_render")
    _assert_ret(ret, EX_AGGREGATE)


def test_retcode_state_highstate_render_exception(salt_ssh_cli):
    ret = salt_ssh_cli.run("state.highstate")
    _assert_ret(ret, EX_AGGREGATE)


def test_retcode_state_sls_id_render_exception(salt_ssh_cli):
    ret = salt_ssh_cli.run("state.sls_id", "foo", "fail_render")
    _assert_ret(ret, EX_AGGREGATE)


def test_retcode_state_show_sls_render_exception(salt_ssh_cli):
    ret = salt_ssh_cli.run("state.show_sls", "fail_render")
    _assert_ret(ret, EX_AGGREGATE)


def test_retcode_state_show_low_sls_render_exception(salt_ssh_cli):
    ret = salt_ssh_cli.run("state.show_low_sls", "fail_render")
    _assert_ret(ret, EX_AGGREGATE)


def test_retcode_state_show_highstate_render_exception(salt_ssh_cli):
    ret = salt_ssh_cli.run("state.show_highstate")
    _assert_ret(ret, EX_AGGREGATE)


def test_retcode_state_show_lowstate_render_exception(salt_ssh_cli):
    ret = salt_ssh_cli.run("state.show_lowstate")
    # state.show_lowstate exits with 0 for non-ssh as well
    _assert_ret(ret, 0)


def test_retcode_state_top_render_exception(salt_ssh_cli):
    ret = salt_ssh_cli.run("state.top", "top.sls")
    _assert_ret(ret, EX_AGGREGATE)


def test_retcode_state_single_render_exception(salt_ssh_cli):
    ret = salt_ssh_cli.run("state.single", "file")
    assert ret.returncode == EX_AGGREGATE
    assert isinstance(ret.data, str)
    assert "single() missing 1 required positional argument" in ret.data


def _assert_ret(ret, retcode):
    assert ret.returncode == retcode
    assert isinstance(ret.data, list)
    assert ret.data
    assert isinstance(ret.data[0], str)
    assert ret.data[0].startswith(
        "Rendering SLS 'base:fail_render' failed: Jinja variable 'abc' is undefined;"
    )
