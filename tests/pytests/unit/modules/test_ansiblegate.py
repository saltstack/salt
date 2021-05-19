# Author: Bo Maryniuk <bo@suse.de>

import os
import sys

import pytest
import salt.modules.ansiblegate as ansiblegate
from salt.exceptions import LoaderError
from tests.support.mock import MagicMock, patch

pytestmark = [
    pytest.mark.skip_on_windows(reason="Not supported on Windows"),
]


@pytest.fixture
def configure_loader_modules():
    return {ansiblegate: {}}


@pytest.fixture
def resolver():
    _resolver = ansiblegate.AnsibleModuleResolver({})
    _resolver._modules_map = {
        "one.two.three": os.sep + os.path.join("one", "two", "three.py"),
        "four.five.six": os.sep + os.path.join("four", "five", "six.py"),
        "three.six.one": os.sep + os.path.join("three", "six", "one.py"),
    }
    return _resolver


def test_ansible_module_help(resolver):
    """
    Test help extraction from the module
    :return:
    """

    class Module:
        """
        An ansible module mock.
        """

        __name__ = "foo"
        DOCUMENTATION = """
---
one:
    text here
---
two:
    text here
description:
    describe the second part
    """

    with patch.object(ansiblegate, "_resolver", resolver), patch.object(
        ansiblegate._resolver, "load_module", MagicMock(return_value=Module())
    ):
        ret = ansiblegate.help("dummy")
        assert sorted(
            ret.get('Available sections on module "{}"'.format(Module().__name__))
        ) == ["one", "two"]
        assert ret.get("Description") == "describe the second part"


def test_module_resolver_modlist(resolver):
    """
    Test Ansible resolver modules list.
    :return:
    """
    assert resolver.get_modules_list() == [
        "four.five.six",
        "one.two.three",
        "three.six.one",
    ]
    for ptr in ["five", "fi", "ve"]:
        assert resolver.get_modules_list(ptr) == ["four.five.six"]
    for ptr in ["si", "ix", "six"]:
        assert resolver.get_modules_list(ptr) == ["four.five.six", "three.six.one"]
    assert resolver.get_modules_list("one") == ["one.two.three", "three.six.one"]
    assert resolver.get_modules_list("one.two") == ["one.two.three"]
    assert resolver.get_modules_list("four") == ["four.five.six"]


def test_resolver_module_loader_failure(resolver):
    """
    Test Ansible module loader.
    :return:
    """
    mod = "four.five.six"
    with pytest.raises(ImportError):
        resolver.load_module(mod)

    mod = "i.even.do.not.exist.at.all"
    with pytest.raises(LoaderError):
        resolver.load_module(mod)


def test_resolver_module_loader(resolver):
    """
    Test Ansible module loader.
    :return:
    """
    with patch("salt.modules.ansiblegate.importlib", MagicMock()), patch(
        "salt.modules.ansiblegate.importlib.import_module", lambda x: x
    ):
        assert resolver.load_module("four.five.six") == "ansible.modules.four.five.six"


def test_resolver_module_loader_import_failure(resolver):
    """
    Test Ansible module loader failure.
    :return:
    """
    with patch("salt.modules.ansiblegate.importlib", MagicMock()), patch(
        "salt.modules.ansiblegate.importlib.import_module", lambda x: x
    ):
        with pytest.raises(LoaderError):
            resolver.load_module("something.strange")


def test_virtual_function(resolver):
    """
    Test Ansible module __virtual__ when ansible is not installed on the minion.
    :return:
    """
    with patch("salt.modules.ansiblegate.ansible", None):
        assert ansiblegate.__virtual__() == (
            False,
            "Ansible is not installed on this system",
        )


@pytest.mark.skipif(
    sys.version_info < (3, 6),
    reason="Skipped on Py3.5, the mock of subprocess.run is different",
)
def test_ansible_module_call(resolver):
    """
    Test Ansible module call from ansible gate module
    :return:
    """

    class Module:
        """
        An ansible module mock.
        """

        __name__ = "one.two.three"
        __file__ = "foofile"

        def main():  # pylint: disable=no-method-argument
            pass

    with patch.object(ansiblegate, "_resolver", resolver), patch.object(
        ansiblegate._resolver, "load_module", MagicMock(return_value=Module())
    ):
        _ansible_module_caller = ansiblegate.AnsibleModuleCaller(ansiblegate._resolver)
        with patch("subprocess.run") as proc_run_mock:
            proc_run_mock.return_value.stdout = '{"completed": true}'

            ret = _ansible_module_caller.call("one.two.three", "arg_1", kwarg1="foobar")
            proc_run_mock.assert_any_call(
                [
                    sys.executable,
                    "-c",
                    "import sys, one.two.three; print(one.two.three.main(), file=sys.stdout); sys.stdout.flush()",
                ],
                input='{"ANSIBLE_MODULE_ARGS": {"kwarg1": "foobar", "_raw_params": "arg_1"}}',
                stdout=-1,
                stderr=-1,
                check=True,
                shell=False,
                universal_newlines=True,
                timeout=1200,
            )
            assert ret == {"completed": True, "timeout": 1200}


def test_ansible_playbooks_return_retcode(resolver):
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
