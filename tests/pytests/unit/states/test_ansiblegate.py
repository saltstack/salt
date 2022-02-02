import json
import pathlib

import pytest
import salt.states.ansiblegate as ansiblegate
from tests.support.mock import MagicMock, patch
from tests.support.runtests import RUNTIME_VARS


@pytest.fixture
def configure_loader_modules():
    return {ansiblegate: {}}


@pytest.fixture
def playbooks_examples_dir():
    return pathlib.Path(RUNTIME_VARS.TESTS_DIR) / "unit" / "files" / "playbooks"


def test_ansible_playbooks_states_success(playbooks_examples_dir):
    """
    Test ansible.playbooks states executions success.
    """

    success_output = json.loads(
        playbooks_examples_dir.joinpath("success_example.json").read_text()
    )

    with patch.dict(
        ansiblegate.__salt__,
        {"ansible.playbooks": MagicMock(return_value=success_output)},
    ), patch("salt.utils.path.which", return_value=True), patch.dict(
        ansiblegate.__opts__, {"test": False}
    ):
        ret = ansiblegate.playbooks("foobar")
        assert ret["result"] is True
        assert ret["comment"] == "Changes were made by playbook foobar"
        assert ret["changes"] == {
            "py2hosts": {
                "Ansible copy file to remote server": {"centos7-host1.tf.local": {}}
            }
        }


def test_ansible_playbooks_states_failed(playbooks_examples_dir):
    """
    Test ansible.playbooks failed states executions.
    :return:
    """
    failed_output = json.loads(
        playbooks_examples_dir.joinpath("failed_example.json").read_text()
    )
    with patch.dict(
        ansiblegate.__salt__,
        {"ansible.playbooks": MagicMock(return_value=failed_output)},
    ), patch("salt.utils.path.which", return_value=True), patch.dict(
        ansiblegate.__opts__, {"test": False}
    ):
        ret = ansiblegate.playbooks("foobar")
        assert ret["result"] is False
        assert ret["comment"] == "There were some issues running the playbook foobar"
        assert ret["changes"] == {
            "py2hosts": {
                "yum": {
                    "centos7-host1.tf.local": [
                        "No package matching 'rsyndc' found available, installed or"
                        " updated"
                    ]
                }
            }
        }
