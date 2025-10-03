"""
Verify salt-ssh passes on a failing retcode from state execution.
"""

import pytest

from salt.defaults.exitcodes import EX_AGGREGATE

pytestmark = [
    pytest.mark.skip_on_windows(reason="salt-ssh not available on Windows"),
    pytest.mark.slow_test,
]


@pytest.fixture(scope="module", autouse=True)
def state_tree_run_fail(base_env_state_tree_root_dir):
    top_file = """
    base:
      'localhost':
        - fail_run
      '127.0.0.1':
        - fail_run
    """
    state_file = """
    This file state fails:
      file.managed:
        - name: /tmp/non/ex/is/tent
        - makedirs: false
        - contents: foo
    """
    top_tempfile = pytest.helpers.temp_file(
        "top.sls", top_file, base_env_state_tree_root_dir
    )
    state_tempfile = pytest.helpers.temp_file(
        "fail_run.sls", state_file, base_env_state_tree_root_dir
    )
    with top_tempfile, state_tempfile:
        yield


@pytest.mark.parametrize(
    "args",
    (
        ("state.sls", "fail_run"),
        ("state.highstate",),
        ("state.sls_id", "This file state fails", "fail_run"),
        ("state.top", "top.sls"),
    ),
)
def test_it(salt_ssh_cli, args):
    ret = salt_ssh_cli.run(*args)
    assert ret.returncode == EX_AGGREGATE
    assert isinstance(ret.data, dict)
    state = next(iter(ret.data))
    assert isinstance(ret.data[state], dict)
    assert "result" in ret.data[state]
    assert ret.data[state]["result"] is False
