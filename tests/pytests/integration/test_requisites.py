import pytest
import salt.modules.state as statemod
# from salt.modules.state import apply
from unittest import mock
from pprint import pprint

@pytest.fixture
def configure_loader_modules():
    return {
        statemod: {
            "__opts__": {
                "file_client": "local",
                "master_type": "disable",
                "state_aggregate": True,
            },
            "__salt__": {
                "pkg.install": mock.Mock(return_value={"hello": "new", "cowsay": "new", "fortune-mod": "new"}),
                "pkg.remove": mock.Mock(return_value={}),
                "pkg.list_pkgs": mock.Mock(return_value={}),
            },
            "__grains__": {
                "os": "Linux",
            },
        },
    }

def test_aggregate_requisites(salt_master, salt_call_cli):
    """Test to ensure that aggregated states honor requisites"""
    sls_name = "requisite_aggregate_test"
    sls_contents = """
    "packages 1":
      pkg.installed:
        - pkgs:
          - hello

    "listen to packages 2":
      test.succeed_with_changes:
        - listen:
          - "packages 2"

    "packages 2":
      pkg:
        - installed
        - pkgs:
          - cowsay
          - fortune-mod
        - require:
          - "requirement"

    "packages 3":
      pkg.installed:
        - name: cowsay
        - require:
          - "test": "requirement"

    "requirement":
      test.nop:
        - name: "requirement_name"
    """
    sls_tempfile = salt_master.state_tree.base.temp_file(
        f"{sls_name}.sls", sls_contents
    )
    with sls_tempfile:
        # Apply the state file
        ret = salt_call_cli.run("state.sls", sls_name)

        # Check the results
        assert ret.returncode == 0
        assert ret.data
        assert ret.data['pkg_|-packages 1_|-packages 1_|-installed']["result"] is True
        assert ret.data['pkg_|-packages 2_|-packages 2_|-installed']["result"] is True
        assert ret.data['test_|-listen to packages 2_|-listen to packages 2_|-succeed_with_changes']["result"] is True
        assert ret.data['pkg_|-packages 3_|-cowsay_|-installed']["result"] is True
        expected_order = [
            'pkg_|-packages 1_|-packages 1_|-installed',
            'test_|-listen to packages 2_|-listen to packages 2_|-succeed_with_changes',
            'test_|-requirement_|-requirement_name_|-nop',
            'pkg_|-packages 2_|-packages 2_|-installed',
            'pkg_|-packages 3_|-cowsay_|-installed',
            'test_|-listener_listen to packages 2_|-listen to packages 2_|-mod_watch',
        ]
        for index, result_id in enumerate(ret.data):
            assert result_id == expected_order[index]


def test_many_requisites(salt_master, salt_call_cli):
    """Test to make sure that many requisites does not take too long"""

    sls_name = "many_aggregates_test"
    sls_contents = """
    {%- for i in range(1000) %}
    nop-{{ i }}:
      test.nop:
        {%- if i > 0 %}
        - require:
          - test: nop-{{ i - 1 }}
        {%- else %}
        - require: []
        {%- endif %}
    {%- endfor %}
    """
    sls_tempfile = salt_master.state_tree.base.temp_file(
        f"{sls_name}.sls", sls_contents
    )
    with sls_tempfile:
        # Apply the state file
        ret = salt_call_cli.run("state.sls", sls_name)

        # Check the results
        assert ret.returncode == 0
        assert ret.data
        expected_order = [
            f'test_|-nop-{i}_|-nop-{i}_|-nop'
            for i in range(1000)]
        for index, result_id in enumerate(ret.data):
            assert result_id == expected_order[index]
