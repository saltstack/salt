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


@pytest.mark.parametrize(
    "args,retcode",
    (
        (("state.sls", "fail_structure"), EX_AGGREGATE),
        (("state.highstate",), EX_AGGREGATE),
        (("state.show_sls", "fail_structure"), EX_AGGREGATE),
        (("state.show_low_sls", "fail_structure"), EX_AGGREGATE),
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
        "Cannot extend ID 'Some file state' in 'base:fail_structure"
    )
