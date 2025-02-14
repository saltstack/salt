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
