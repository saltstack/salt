# Author: Bo Maryniuk <bo@suse.de>

import pytest
import salt.modules.ansiblegate as ansiblegate
import salt.utils.json
from tests.support.mock import ANY, MagicMock, patch
import salt.config
import salt.loader

pytestmark = [
    pytest.mark.skip_on_windows(reason="Not supported on Windows"),
]


@pytest.fixture
def configure_loader_modules():
    return {ansiblegate: {"__utils__": {}}}


def test_ansible_module_help():
    """
    Test help extraction from the module
    :return:
    """
    extension = {
        "foo": {
            "doc": {"description": "The description of foo"},
            "examples": "These are the examples",
            "return": {"a": "A return"},
        }
    }

    with patch("subprocess.run") as proc_run_mock:
        proc_run_mock.return_value.stdout = salt.utils.json.dumps(extension)
        ret = ansiblegate.help("foo")
        assert ret["description"] == extension["foo"]["doc"]["description"]


def test_virtual_function(subtests):
    """
    Test Ansible module __virtual__ when ansible is not installed on the minion.
    :return:
    """

    with subtests.test("missing ansible binary"):
        with patch("salt.utils.path.which", side_effect=[None]):
            assert ansiblegate.__virtual__() == (
                False,
                "The 'ansible' binary was not found.",
            )

    with subtests.test("missing ansible-doc binary"):
        with patch(
            "salt.utils.path.which",
            side_effect=["/path/to/ansible", None],
        ):
            assert ansiblegate.__virtual__() == (
                False,
                "The 'ansible-doc' binary was not found.",
            )

    with subtests.test("missing ansible-playbook binary"):
        with patch(
            "salt.utils.path.which",
            side_effect=["/path/to/ansible", "/path/to/ansible-doc", None],
        ):
            assert ansiblegate.__virtual__() == (
                False,
                "The 'ansible-playbook' binary was not found.",
            )

    with subtests.test("Failing to load the ansible modules listing"):
        with patch(
            "salt.utils.path.which",
            side_effect=[
                "/path/to/ansible",
                "/path/to/ansible-doc",
                "/path/to/ansible-playbook",
            ],
        ):
            with patch("subprocess.run") as proc_run_mock:
                proc_run_mock.return_value.retcode = 1
                proc_run_mock.return_value.stderr = "bar"
                proc_run_mock.return_value.stdout = "{}"
                assert ansiblegate.__virtual__() == (
                    False,
                    "Failed to get the listing of ansible modules:\nbar",
                )


def test_ansible_module_call():
    """
    Test Ansible module call from ansible gate module
    :return:
    """

    with patch("subprocess.run") as proc_run_mock:
        proc_run_mock.return_value.stdout = (
            'localhost | SUCCESS => {\n    "completed": true    \n}'
        )

        ret = ansiblegate.call("one.two.three", "arg_1", kwarg1="foobar")
        proc_run_mock.assert_any_call(
            [
                ANY,
                "localhost",
                "--limit",
                "127.0.0.1",
                "-m",
                "one.two.three",
                "-a",
                '"arg_1" kwarg1="foobar"',
                "-i",
                ANY,
            ],
            check=True,
            shell=False,
            stderr=-1,
            stdout=-1,
            timeout=1200,
            universal_newlines=True,
        )
        assert ret == {"completed": True}


def test_ansible_playbooks_return_retcode():
    """
    Test ansible.playbooks execution module function include retcode in the return.
    :return:
    """
    ref_out = {"retcode": 0, "stdout": '{"foo": "bar"}'}
    cmd_run_all = MagicMock(return_value=ref_out)
    with patch.dict(ansiblegate.__salt__, {"cmd.run_all": cmd_run_all}), patch(
        "salt.utils.path.which", MagicMock(return_value=True)
    ):
        ret = ansiblegate.playbooks("fake-playbook.yml")
        assert "retcode" in ret


def test_ansible_targets():
    """
    Test ansible.targets execution module function.
    :return:
    """
    ansible_inventory_ret = """
{
    "_meta": {
        "hostvars": {
            "uyuni-stable-ansible-centos7-1.tf.local": {
                "ansible_ssh_private_key_file": "/etc/ansible/my_ansible_private_key"
            },
            "uyuni-stable-ansible-centos7-2.tf.local": {
                "ansible_ssh_private_key_file": "/etc/ansible/my_ansible_private_key"
            }
        }
    },
    "all": {
        "children": [
            "ungrouped"
        ]
    },
    "ungrouped": {
        "hosts": [
            "uyuni-stable-ansible-centos7-1.tf.local",
            "uyuni-stable-ansible-centos7-2.tf.local"
        ]
    }
}
    """
    ansible_inventory_mock = MagicMock(return_value=ansible_inventory_ret)
    with patch("salt.utils.path.which", MagicMock(return_value=True)):
        opts = salt.config.DEFAULT_MINION_OPTS.copy()
        utils = salt.loader.utils(opts, whitelist=["ansible"])
        with patch("salt.modules.cmdmod.run", ansible_inventory_mock), patch.dict(
            ansible.__utils__, utils), patch(
            "os.path.isfile", MagicMock(return_value=True)
        ):
            ret = ansible.targets()
            assert ansible_inventory_mock.call_args
            assert "_meta" in ret
            assert "uyuni-stable-ansible-centos7-1.tf.local" in ret["_meta"]["hostvars"]
            assert "ansible_ssh_private_key_file" in ret["_meta"]["hostvars"]["uyuni-stable-ansible-centos7-1.tf.local"]
            assert "all" in ret
            assert len(ret["ungrouped"]["hosts"]) == 2
