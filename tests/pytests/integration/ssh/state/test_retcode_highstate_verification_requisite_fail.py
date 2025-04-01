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


@pytest.mark.parametrize(
    "args,retcode",
    (
        (("state.sls", "fail_req"), EX_AGGREGATE),
        (("state.highstate",), EX_AGGREGATE),
        (("state.show_sls", "fail_req"), EX_AGGREGATE),
        (("state.show_low_sls", "fail_req"), EX_AGGREGATE),
        # state.show_lowstate exits with 0 for non-ssh as well
        (("state.show_lowstate",), 0),
        (("state.top", "top.sls"), EX_AGGREGATE),
    ),
)
def test_it(salt_ssh_cli, args, retcode):
    ret = salt_ssh_cli.run(*args)
    assert ret.returncode == retcode
    assert isinstance(ret.data, list)
    assert ret.data
    assert isinstance(ret.data[0], str)
    assert ret.data[0].startswith(
        "Invalid requisite in require: file.managed for invalid_requisite"
    )
