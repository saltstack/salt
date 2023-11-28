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


@pytest.mark.parametrize(
    "args,retcode",
    (
        (("state.sls", "fail_render"), EX_AGGREGATE),
        (("state.highstate",), EX_AGGREGATE),
        (("state.sls_id", "foo", "fail_render"), EX_AGGREGATE),
        (("state.show_sls", "fail_render"), EX_AGGREGATE),
        (("state.show_low_sls", "fail_render"), EX_AGGREGATE),
        (("state.show_highstate",), EX_AGGREGATE),
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
        "Rendering SLS 'base:fail_render' failed: Jinja variable 'abc' is undefined;"
    )


def test_state_single(salt_ssh_cli):
    ret = salt_ssh_cli.run("state.single", "file")
    assert ret.returncode == EX_AGGREGATE
    assert isinstance(ret.data, str)
    assert "single() missing 1 required positional argument" in ret.data
