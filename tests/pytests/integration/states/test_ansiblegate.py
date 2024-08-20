"""
Test AnsibleGate State Module
"""

import logging
import shutil
import textwrap

import pytest
import yaml
from pytestshellutils.exceptions import FactoryTimeout
from saltfactories.utils.functional import StateResult

import salt.utils.files
import salt.utils.path
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

log = logging.getLogger(__name__)


@pytest.fixture(scope="module")
def ansible_inventory_directory(tmp_path_factory, grains):
    if grains["os_family"] != "RedHat" or grains["os"] == "VMware Photon OS":
        pytest.skip("Currently, the test targets the RedHat OS familly only.")
    tmp_dir = tmp_path_factory.mktemp("ansible")
    try:
        yield tmp_dir
    finally:
        shutil.rmtree(str(tmp_dir))


@pytest.fixture(scope="module", autouse=True)
def ansible_inventory(ansible_inventory_directory, sshd_server, known_hosts_file):
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
                        f"-o UserKnownHostsFile={known_hosts_file} "
                    ),
                },
            },
        },
    }
    with salt.utils.files.fopen(inventory, "w") as yaml_file:
        yaml.dump(data, yaml_file, default_flow_style=False)
    return inventory


@pytest.mark.requires_sshd_server
@pytest.mark.timeout_unless_on_windows(240)
def test_ansible_playbook(salt_call_cli, ansible_inventory, tmp_path):
    rundir = tmp_path / "rundir"
    rundir.mkdir(exist_ok=True, parents=True)
    remove_contents = textwrap.dedent(
        """
    ---
    - hosts: all
      tasks:
      - name: remove postfix
        yum:
          name: postfix
          state: absent
        become: true
        become_user: root
    """
    )
    remove_playbook = rundir / "remove.yml"
    remove_playbook.write_text(remove_contents)
    install_contents = textwrap.dedent(
        """
    ---
    - hosts: all
      tasks:
      - name: install postfix
        yum:
          name: postfix
          state: present
        become: true
        become_user: root
    """
    )
    install_playbook = rundir / "install.yml"
    install_playbook.write_text(install_contents)

    # These tests have been known to timeout, so allow them longer if needed.
    timeouts = [60, 120, 180]
    names = ["remove.yml", "install.yml"]

    for name in names:
        for timeout in timeouts:
            try:
                ret = salt_call_cli.run(
                    "state.single",
                    "ansible.playbooks",
                    name=name,
                    rundir=str(rundir),
                    ansible_kwargs={"inventory": ansible_inventory},
                    _timeout=timeout,  # The removal can take over 60 seconds
                )
            except FactoryTimeout:
                log.debug("%s took longer than %s seconds", name, timeout)
                if timeout == timeouts[-1]:
                    pytest.fail(f"Failed to run {name}")
            else:
                assert ret.returncode == 0
                assert StateResult(ret.data).result is True
                break
