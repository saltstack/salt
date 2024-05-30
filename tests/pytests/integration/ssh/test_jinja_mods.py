import pytest
from saltfactories.utils.functional import StateResult

pytestmark = [
    pytest.mark.skip_on_windows(reason="salt-ssh not available on Windows"),
]


@pytest.mark.slow_test
def test_echo(salt_ssh_cli, base_env_state_tree_root_dir):
    """
    verify salt-ssh can use imported map files in states
    """
    name = "echo"
    echo = "hello"
    state_file = """
    ssh_test_echo:
      test.show_notification:
        - text: {{{{ salt['test.echo']('{echo}') }}}}
    """.format(
        echo=echo
    )
    state_tempfile = pytest.helpers.temp_file(
        f"{name}.sls", state_file, base_env_state_tree_root_dir
    )

    with state_tempfile:
        ret = salt_ssh_cli.run("state.apply", name)
        result = StateResult(ret.data)
        assert result.comment == echo


@pytest.fixture
def _exewrap(base_env_state_tree_root_dir, salt_run_cli):
    exe = """
def run():
    return "exe"
"""

    wrapper = """
def run():
    return "wrapper"
"""
    name = "exewrap"
    try:
        with pytest.helpers.temp_file(
            f"{name}.py", exe, base_env_state_tree_root_dir / "_modules"
        ):
            with pytest.helpers.temp_file(
                f"{name}.py", wrapper, base_env_state_tree_root_dir / "_wrapper"
            ):
                res = salt_run_cli.run("saltutil.sync_all")
                assert res.returncode == 0
                assert f"modules.{name}" in res.data["modules"]
                assert f"wrapper.{name}" in res.data["wrapper"]
                yield name
    finally:
        res = salt_run_cli.run("saltutil.sync_all")
        assert res.returncode == 0


@pytest.fixture
def _jinja_loader_attr_template(base_env_state_tree_root_dir, _exewrap):
    contents = f"""
foo:
  test.show_notification:
    - text: {{{{ salt.{_exewrap}.run() | json }}}}
    """
    name = "exewrap_test"
    with pytest.helpers.temp_file(
        f"{name}.sls", contents, base_env_state_tree_root_dir
    ):
        yield name


def test_wrapper_attribute_access(_jinja_loader_attr_template, salt_ssh_cli):
    res = salt_ssh_cli.run("state.apply", _jinja_loader_attr_template)
    assert res.returncode == 0
    ret = StateResult(res.data)
    assert ret.result is True
    assert ret.comment == "wrapper"
