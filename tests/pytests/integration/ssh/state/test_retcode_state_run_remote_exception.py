"""
Verify salt-ssh does not report success when it cannot parse
the return value.
"""

import pytest

from salt.defaults.exitcodes import EX_AGGREGATE

pytestmark = [
    pytest.mark.skip_on_windows(reason="salt-ssh not available on Windows"),
    pytest.mark.slow_test,
]


@pytest.fixture(scope="module")
def state_tree_remote_exception_mod(salt_run_cli, base_env_state_tree_root_dir):
    module_contents = r"""
import os
import sys


def __virtual__():
    return "whoops"


def do_stuff(name):
    print("Hi there, nice that you're trying to make me do stuff.", file=sys.stderr)
    print("Traceback (most recent call last):", file=sys.stderr)
    print('  File "/dont/treat/me/like/that.py" in buzz_off', file=sys.stderr)
    print("ComplianceError: 'Outlaw detected'", file=sys.stderr)
    sys.stderr.flush()
    os._exit(1)
"""
    module_dir = base_env_state_tree_root_dir / "_states"
    module_tempfile = pytest.helpers.temp_file("whoops.py", module_contents, module_dir)
    try:
        with module_tempfile:
            ret = salt_run_cli.run("saltutil.sync_states")
            assert ret.returncode == 0
            assert "states.whoops" in ret.data
            yield
    finally:
        ret = salt_run_cli.run("saltutil.sync_states")
        assert ret.returncode == 0


@pytest.fixture(scope="module", autouse=True)
def state_tree_remote_exception(
    base_env_state_tree_root_dir, state_tree_remote_exception_mod
):
    top_file = """
    base:
      'localhost':
        - remote_stacktrace
      '127.0.0.1':
        - remote_stacktrace
    """
    state_file = r"""
    This should be detected as failure:
      whoops.do_stuff
    """
    top_tempfile = pytest.helpers.temp_file(
        "top.sls", top_file, base_env_state_tree_root_dir
    )
    state_tempfile = pytest.helpers.temp_file(
        "remote_stacktrace.sls", state_file, base_env_state_tree_root_dir
    )
    with top_tempfile, state_tempfile:
        yield


@pytest.mark.slow_test
@pytest.mark.usefixtures("state_tree_remote_exception")
@pytest.mark.parametrize(
    "args",
    (
        ("state.sls", "remote_stacktrace"),
        ("state.highstate",),
        ("state.sls_id", "This should be detected as failure", "remote_stacktrace"),
        ("state.top", "top.sls"),
        ("state.single", "whoops.do_stuff", "now"),
    ),
)
def test_it(salt_ssh_cli, args):
    ret = salt_ssh_cli.run(*args)

    assert ret.returncode == EX_AGGREGATE
    assert ret.data
    assert isinstance(ret.data, dict)
    assert "ComplianceError: 'Outlaw detected'" in ret.data["stderr"]
