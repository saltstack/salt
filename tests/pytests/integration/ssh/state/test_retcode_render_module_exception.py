"""
Verify salt-ssh stops state execution and fails with a retcode > 0
when a state rendering fails because an execution module throws an exception.
"""

import pytest

from salt.defaults.exitcodes import EX_AGGREGATE

pytestmark = [
    pytest.mark.skip_on_windows(reason="salt-ssh not available on Windows"),
    pytest.mark.slow_test,
]


@pytest.fixture(scope="module", autouse=True)
def state_tree_render_module_exception(base_env_state_tree_root_dir):
    top_file = """
    base:
      'localhost':
        - fail_module_exception
      '127.0.0.1':
        - fail_module_exception
    """
    state_file = r"""
    This should fail being rendered:
      test.show_notification:
        - text: {{ salt["disk.usage"]("c") | yaml_dquote }}
    """
    top_tempfile = pytest.helpers.temp_file(
        "top.sls", top_file, base_env_state_tree_root_dir
    )
    state_tempfile = pytest.helpers.temp_file(
        "fail_module_exception.sls", state_file, base_env_state_tree_root_dir
    )
    with top_tempfile, state_tempfile:
        yield


@pytest.mark.parametrize(
    "args,retcode",
    (
        (("state.sls", "fail_module_exception"), EX_AGGREGATE),
        (("state.highstate",), EX_AGGREGATE),
        (("state.sls_id", "foo", "fail_module_exception"), EX_AGGREGATE),
        (("state.show_sls", "fail_module_exception"), EX_AGGREGATE),
        (("state.show_low_sls", "fail_module_exception"), EX_AGGREGATE),
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
    # While these three should usually follow each other, there
    # can be warnings in between that would break such a logic.
    assert "Rendering SLS 'base:fail_module_exception' failed:" in ret.data[0]
    assert "Problem running salt function in Jinja template:" in ret.data[0]
    assert (
        "Error running 'disk.usage': Invalid flag passed to disk.usage" in ret.data[0]
    )
