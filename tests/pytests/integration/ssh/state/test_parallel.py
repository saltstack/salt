"""
Verify salt-ssh states support ``parallel``.
"""

import pytest

pytestmark = [
    pytest.mark.skip_on_windows(reason="salt-ssh not available on Windows"),
    pytest.mark.slow_test,
]


@pytest.fixture(scope="module", autouse=True)
def state_tree_parallel(base_env_state_tree_root_dir):
    top_file = """
    base:
      'localhost':
        - parallel
      '127.0.0.1':
        - parallel
    """
    state_file = """
    {%- for i in range(5) %}
    This runs in parallel {{ i }}:
      cmd.run:
        - name: sleep 0.{{ i }}
        - parallel: true
    {%- endfor %}
    """
    top_tempfile = pytest.helpers.temp_file(
        "top.sls", top_file, base_env_state_tree_root_dir
    )
    state_tempfile = pytest.helpers.temp_file(
        "parallel.sls", state_file, base_env_state_tree_root_dir
    )
    with top_tempfile, state_tempfile:
        yield


@pytest.mark.parametrize(
    "args",
    (
        pytest.param(("state.sls", "parallel"), id="sls"),
        pytest.param(("state.highstate",), id="highstate"),
        pytest.param(("state.top", "top.sls"), id="top"),
    ),
)
def test_it(salt_ssh_cli, args):
    """
    Ensure states with ``parallel: true`` do not cause a crash.
    This does not check that they were actually run in parallel
    since that would result either in a long-running or flaky test.
    """
    ret = salt_ssh_cli.run(*args)
    assert ret.returncode == 0
    assert isinstance(ret.data, dict)
    for i in range(5):
        key = f"cmd_|-This runs in parallel {i}_|-sleep 0.{i}_|-run"
        assert key in ret.data
        assert "pid" in ret.data[key]["changes"]
        assert ret.data[key]["changes"]["retcode"] == 0
