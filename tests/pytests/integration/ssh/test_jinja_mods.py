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
    name = "funcwrapper_attr_exewrap_test"
    with pytest.helpers.temp_file(
        f"{name}.sls", contents, base_env_state_tree_root_dir
    ):
        yield name


def test_wrapper_attribute_access(_jinja_loader_attr_template, salt_ssh_cli):
    """
    Ensure wrappers can be accessed via the attribute syntax.
    It's not recommended to use this syntax, but the regular loader supports it
    as well, so we should have feature parity.
    Issue #66600.
    """
    res = salt_ssh_cli.run("state.apply", _jinja_loader_attr_template)
    assert res.returncode == 0
    ret = StateResult(res.data)
    assert ret.result is True
    assert ret.comment == "wrapper"


@pytest.fixture
def _jinja_loader_get_template(base_env_state_tree_root_dir, _exewrap):
    contents = """
foo:
  test.show_notification:
    - text: {{ salt.grains.get("id") | json }}
    """
    name = "funcwrapper_attr_get_test"
    with pytest.helpers.temp_file(
        f"{name}.sls", contents, base_env_state_tree_root_dir
    ):
        yield name


def test_wrapper_attribute_access_get(_jinja_loader_get_template, salt_ssh_cli):
    """
    Ensure a function named `.get` is not shadowed when accessed via attribute syntax.
    It's not recommended to use it, but the regular loader supports it
    as well, so we should have feature parity.
    Issue #41794.
    """
    res = salt_ssh_cli.run("state.apply", _jinja_loader_get_template)
    assert res.returncode == 0
    ret = StateResult(res.data)
    assert ret.result is True
    assert ret.comment == "localhost"


@pytest.fixture
def _python_loader_attribute_access_template(base_env_state_tree_root_dir, _exewrap):
    contents = """
#!py
def run():
    return {
        "foo": {
            "test.show_notification": [
                {"text": __salt__.grains.get("id")}
            ]
        }
    }
    """
    name = "funcwrapper_attr_python_test"
    with pytest.helpers.temp_file(
        f"{name}.sls", contents, base_env_state_tree_root_dir
    ):
        yield name


def test_wrapper_attribute_access_non_jinja(
    _python_loader_attribute_access_template, salt_ssh_cli
):
    """
    Ensure attribute access works with non-Jinja renderers.
    It's not recommended to use this syntax, but the regular loader supports it
    as well, so we should have feature parity.
    Issue #66376.
    """
    res = salt_ssh_cli.run("state.apply", _python_loader_attribute_access_template)
    assert res.returncode == 0
    ret = StateResult(res.data)
    assert ret.result is True
    assert ret.comment == "localhost"
