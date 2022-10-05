import pytest
from saltfactories.utils.functional import StateResult

pytestmark = [
    pytest.mark.slow_test,
    pytest.mark.skip_on_windows(reason="salt-ssh not available on Windows"),
]


def test_dateutils_strftime(salt_master, salt_ssh_cli):
    """
    test jinja filter datautils.strftime
    """
    sls_contents = """
    {% set result = none | strftime('%Y-%m-%d') %}
    test:
      module.run:
        - name: test.echo
        - text: {{ result }}
    """
    with salt_master.state_tree.base.temp_file("dateutils.sls", sls_contents):
        ret = salt_ssh_cli.run("state.sls", "dateutils")
        assert ret.returncode == 0
        staterun = StateResult(ret.data)
        assert staterun.result is True
        assert staterun.changes
        assert "ret" in staterun.changes
