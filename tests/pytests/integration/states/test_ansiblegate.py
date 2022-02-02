"""
Test AnsibleGate State Module
"""

import shutil

import pytest
import salt.utils.files
import salt.utils.path
import yaml
from saltfactories.utils.functional import StateResult
from tests.support.runtests import RUNTIME_VARS

pytestmark = [
    # root access is necessary because the playbooks install/uninstall software
    pytest.mark.skip_if_not_root,
    # Because of the above, these are also destructive tests
    pytest.mark.destructive_test,
    pytest.mark.skip_if_binaries_missing(
        "ansible-playbook", reason="ansible-playbook is not installed"
    ),
]


@pytest.fixture(scope="module")
def ansible_inventory_directory(tmp_path_factory, grains):
    if grains["os_family"] != "RedHat":
        pytest.skip("Currently, the test targets the RedHat OS familly only.")
    tmp_dir = tmp_path_factory.mktemp("ansible")
    try:
        yield tmp_dir
    finally:
        shutil.rmtree(str(tmp_dir))


@pytest.fixture(scope="module", autouse=True)
def ansible_inventory(ansible_inventory_directory, sshd_server):
    inventory = str(ansible_inventory_directory / "inventory")
    client_key = str(sshd_server.config_dir / "client_key")
    data = {
        "all": {
            "hosts": {
                "localhost": {
                    "ansible_host": "127.0.0.1",
                    "ansible_port": sshd_server.listen_port,
                    "ansible_user": RUNTIME_VARS.RUNNING_TESTS_USER,
                    "ansible_ssh_private_key_file": client_key,
                    "ansible_ssh_extra_args": (
                        "-o StrictHostKeyChecking=false "
                        "-o UserKnownHostsFile=/dev/null "
                    ),
                },
            },
        },
    }
    with salt.utils.files.fopen(inventory, "w") as yaml_file:
        yaml.dump(data, yaml_file, default_flow_style=False)
    return inventory


@pytest.mark.requires_sshd_server
def test_ansible_playbook(salt_call_cli, ansible_inventory):
    ret = salt_call_cli.run(
        "state.single",
        "ansible.playbooks",
        name="remove.yml",
        git_repo="https://github.com/saltstack/salt-test-suite-ansible-playbooks.git",
        ansible_kwargs={"inventory": ansible_inventory},
    )
    assert ret.exitcode == 0
    assert StateResult(ret.json).result is True

    ret = salt_call_cli.run(
        "state.single",
        "ansible.playbooks",
        name="install.yml",
        git_repo="https://github.com/saltstack/salt-test-suite-ansible-playbooks.git",
        ansible_kwargs={"inventory": ansible_inventory},
    )
    assert ret.exitcode == 0
    assert StateResult(ret.json).result is True
