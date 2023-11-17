"""
Verify salt-ssh fails with a retcode > 0 when a highstate verification fails.
This targets another step of the verification.
``state.sls_id`` does not seem to support extends.
``state.show_highstate`` does not validate this.
"""

import pytest

from salt.defaults.exitcodes import EX_AGGREGATE

pytestmark = [
    pytest.mark.skip_on_windows(reason="salt-ssh not available on Windows"),
    pytest.mark.slow_test,
]


@pytest.fixture(scope="module", autouse=True)
def state_tree_structure_fail(base_env_state_tree_root_dir):
    top_file = """
    base:
      'localhost':
        - fail_structure
      '127.0.0.1':
        - fail_structure
    """
    state_file = """
    extend:
      Some file state:
        file:
            - name: /tmp/bar
            - contents: bar
    """
    top_tempfile = pytest.helpers.temp_file(
        "top.sls", top_file, base_env_state_tree_root_dir
    )
    state_tempfile = pytest.helpers.temp_file(
        "fail_structure.sls", state_file, base_env_state_tree_root_dir
    )
    with top_tempfile, state_tempfile:
        yield


def test_retcode_state_sls_invalid_structure(salt_ssh_cli):
    ret = salt_ssh_cli.run("state.sls", "fail_structure")
    _assert_ret(ret, EX_AGGREGATE)


def test_retcode_state_highstate_invalid_structure(salt_ssh_cli):
    ret = salt_ssh_cli.run("state.highstate")
    _assert_ret(ret, EX_AGGREGATE)


def test_retcode_state_show_sls_invalid_structure(salt_ssh_cli):
    ret = salt_ssh_cli.run("state.show_sls", "fail_structure")
    _assert_ret(ret, EX_AGGREGATE)


def test_retcode_state_show_low_sls_invalid_structure(salt_ssh_cli):
    ret = salt_ssh_cli.run("state.show_low_sls", "fail_structure")
    _assert_ret(ret, EX_AGGREGATE)


def test_retcode_state_show_lowstate_invalid_structure(salt_ssh_cli):
    ret = salt_ssh_cli.run("state.show_lowstate")
    # state.show_lowstate exits with 0 for non-ssh as well
    _assert_ret(ret, 0)


def test_retcode_state_top_invalid_structure(salt_ssh_cli):
    ret = salt_ssh_cli.run("state.top", "top.sls")
    _assert_ret(ret, EX_AGGREGATE)


def _assert_ret(ret, retcode):
    assert ret.returncode == retcode
    assert isinstance(ret.data, list)
    assert ret.data
    assert isinstance(ret.data[0], str)
    assert ret.data[0].startswith(
        "Cannot extend ID 'Some file state' in 'base:fail_structure"
    )
