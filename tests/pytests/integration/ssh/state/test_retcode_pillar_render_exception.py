"""
Verify salt-ssh fails with a retcode > 0 when a pillar rendering fails.
"""

import pytest

from salt.defaults.exitcodes import EX_AGGREGATE

pytestmark = [
    pytest.mark.skip_on_windows(reason="salt-ssh not available on Windows"),
    pytest.mark.slow_test,
]


@pytest.fixture(scope="module", autouse=True)
def pillar_tree_render_fail(base_env_pillar_tree_root_dir):
    top_file = """
    base:
      'localhost':
        - fail_render
      '127.0.0.1':
        - fail_render
    """
    pillar_file = r"""
    not_defined: {{ abc }}
    """
    top_tempfile = pytest.helpers.temp_file(
        "top.sls", top_file, base_env_pillar_tree_root_dir
    )
    pillar_tempfile = pytest.helpers.temp_file(
        "fail_render.sls", pillar_file, base_env_pillar_tree_root_dir
    )
    with top_tempfile, pillar_tempfile:
        yield


@pytest.mark.parametrize(
    "args",
    (
        ("state.sls", "basic"),
        ("state.highstate",),
        ("state.sls_id", "foo", "basic"),
        ("state.show_sls", "basic"),
        ("state.show_low_sls", "basic"),
        ("state.show_highstate",),
        ("state.show_lowstate",),
        ("state.top", "top.sls"),
    ),
)
def test_it(salt_ssh_cli, args):
    ret = salt_ssh_cli.run(*args)
    assert ret.returncode == EX_AGGREGATE
    assert isinstance(ret.data, list)
    assert ret.data
    assert isinstance(ret.data[0], str)
    assert ret.data[0] == "Pillar failed to render with the following messages:"
    assert ret.data[1].startswith("Rendering SLS 'fail_render' failed.")
