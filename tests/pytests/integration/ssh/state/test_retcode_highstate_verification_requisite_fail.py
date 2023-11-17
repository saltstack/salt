"""
Verify salt-ssh fails with a retcode > 0 when a highstate verification fails.
``state.show_highstate`` does not validate this.
"""

import pytest

from salt.defaults.exitcodes import EX_AGGREGATE

pytestmark = [
    pytest.mark.skip_on_windows(reason="salt-ssh not available on Windows"),
    pytest.mark.slow_test,
]


@pytest.fixture(scope="module", autouse=True)
def state_tree_req_fail(base_env_state_tree_root_dir):
    top_file = """
    base:
      'localhost':
        - fail_req
      '127.0.0.1':
        - fail_req
    """
    state_file = """
    This has an invalid requisite:
      test.nop:
        - name: foo
        - require_in:
          - file.managed: invalid_requisite
    """
    top_tempfile = pytest.helpers.temp_file(
        "top.sls", top_file, base_env_state_tree_root_dir
    )
    state_tempfile = pytest.helpers.temp_file(
        "fail_req.sls", state_file, base_env_state_tree_root_dir
    )
    with top_tempfile, state_tempfile:
        yield


def test_retcode_state_sls_invalid_requisite(salt_ssh_cli):
    ret = salt_ssh_cli.run("state.sls", "fail_req")
    _assert_ret(ret, EX_AGGREGATE)


def test_retcode_state_highstate_invalid_requisite(salt_ssh_cli):
    ret = salt_ssh_cli.run("state.highstate")
    _assert_ret(ret, EX_AGGREGATE)


def test_retcode_state_show_sls_invalid_requisite(salt_ssh_cli):
    ret = salt_ssh_cli.run("state.show_sls", "fail_req")
    _assert_ret(ret, EX_AGGREGATE)


def test_retcode_state_show_low_sls_invalid_requisite(salt_ssh_cli):
    ret = salt_ssh_cli.run("state.show_low_sls", "fail_req")
    _assert_ret(ret, EX_AGGREGATE)


def test_retcode_state_show_lowstate_invalid_requisite(salt_ssh_cli):
    ret = salt_ssh_cli.run("state.show_lowstate")
    # state.show_lowstate exits with 0 for non-ssh as well
    _assert_ret(ret, 0)


def test_retcode_state_top_invalid_requisite(salt_ssh_cli):
    ret = salt_ssh_cli.run("state.top", "top.sls")
    _assert_ret(ret, EX_AGGREGATE)


def _assert_ret(ret, retcode):
    assert ret.returncode == retcode
    assert isinstance(ret.data, list)
    assert ret.data
    assert isinstance(ret.data[0], str)
    assert ret.data[0].startswith(
        "Invalid requisite in require: file.managed for invalid_requisite"
    )
