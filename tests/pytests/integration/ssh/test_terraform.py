import textwrap

import pytest

import salt.utils.platform
from tests.support.runtests import RUNTIME_VARS

pytestmark = [
    pytest.mark.skip_on_windows(reason="salt-ssh not available on Windows"),
    pytest.mark.slow_test,
]


@pytest.fixture(scope="module")
def minion_id():
    return "terraform_ssh_minion"


@pytest.fixture(scope="module")
def terraform_roster_file(sshd_server, salt_master, tmp_path_factory, minion_id):
    darwin_addon = ""
    if salt.utils.platform.is_darwin():
        darwin_addon = ',\n        "set_path": "$PATH:/usr/local/bin/"\n'
    roster_contents = textwrap.dedent(
        """    {{
      "version": 4,
      "terraform_version": "1.4.3",
      "serial": 1,
      "outputs": {{}},
      "resources": [
        {{
          "mode": "managed",
          "type": "salt_host",
          "name": "{minion}",
          "instances": [
            {{
              "schema_version": 0,
              "attributes": {{
                "cmd_umask": null,
                "host": "localhost",
                "id": "{minion}",
                "minion_opts": null,
                "passwd": "",
                "port": {port},
                "priv": null,
                "salt_id": "{minion}",
                "sudo": null,
                "sudo_user": null,
                "thin_dir": null,
                "timeout": null,
                "tty": null,
                "user": "{user}"{darwin_addon}
              }}
            }}
          ]
        }}
      ],
      "check_results": null
    }}
    """
    ).format(
        minion=minion_id,
        port=sshd_server.listen_port,
        user=RUNTIME_VARS.RUNNING_TESTS_USER,
        darwin_addon=darwin_addon,
    )
    roster_file = tmp_path_factory.mktemp("terraform_roster") / "terraform.tfstate"
    roster_file.write_text(roster_contents)
    yield roster_file
    roster_file.unlink()


@pytest.fixture(scope="module")
def salt_ssh_cli(salt_master, terraform_roster_file, sshd_config_dir):
    """
    The ``salt-ssh`` CLI as a fixture against the running master
    """
    assert salt_master.is_running()
    return salt_master.salt_ssh_cli(
        roster_file=terraform_roster_file,
        target_host="*",
        client_key=str(sshd_config_dir / "client_key"),
        base_script_args=["--ignore-host-keys"],
    )


def test_terraform_roster(salt_ssh_cli, minion_id):
    """
    Test that the terraform roster operates as intended
    """
    ret = salt_ssh_cli.run("--roster=terraform", "test.ping")
    assert ret.data.get(minion_id) is True
