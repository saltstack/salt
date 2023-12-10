"""
    Test cases for salt.modules.helm
"""


import pytest

import salt.modules.helm as helm

# Import Exception
from salt.exceptions import CommandExecutionError
from tests.support.mock import MagicMock, call, patch


@pytest.fixture
def configure_loader_modules():
    return {helm: {}}


def test__prepare_cmd():
    assert helm._prepare_cmd() == ("helm",)


def test__prepare_cmd_binary():
    assert helm._prepare_cmd(binary="binary") == ("binary",)


def test__prepare_cmd_commands():
    assert helm._prepare_cmd(commands=["com1", "com2"]) == (
        "helm",
        "com1",
        "com2",
    )


def test__prepare_cmd_flags():
    assert helm._prepare_cmd(flags=["flag1", "--flag2"]) == (
        "helm",
        "--flag1",
        "--flag2",
    )


def test__prepare_cmd_kvflags():
    result_tuple = helm._prepare_cmd(kvflags={"kflag1": "vflag1", "--kflag2": "vflag2"})
    tuple_valide_1 = (
        "helm",
        "--kflag1",
        "vflag1",
        "--kflag2",
        "vflag2",
    )
    tuple_valide_2 = (
        "helm",
        "--kflag2",
        "vflag2",
        "--kflag1",
        "vflag1",
    )

    assert result_tuple == tuple_valide_1 or result_tuple == tuple_valide_2


def test__exec_cmd():
    cmd_prepare = helm._prepare_cmd()
    cmd_prepare_str = " ".join(cmd_prepare)
    cmd_return = {
        "stdout": "succes",
        "stderr": "",
        "retcode": 0,
    }
    result = cmd_return
    result.update({"cmd": cmd_prepare_str})
    with patch.dict(
        helm.__salt__,
        {  # pylint: disable=no-member
            "cmd.run_all": MagicMock(return_value=cmd_return)
        },
    ):
        assert helm._exec_cmd() == result


def test__exec_true_return_valid():
    _exec_cmd_return = {"retcode": 0}
    with patch("salt.modules.helm._exec_cmd", MagicMock(return_value=_exec_cmd_return)):
        assert True is helm._exec_true_return()


def test__exec_true_return_not_valid():
    _exec_cmd_return = {"retcode": -1, "stderr": "test"}
    with patch("salt.modules.helm._exec_cmd", MagicMock(return_value=_exec_cmd_return)):
        assert "test" == helm._exec_true_return()


def test__exec_string_return_valid():
    _exec_cmd_return = {"retcode": 0, "stdout": "test"}
    with patch("salt.modules.helm._exec_cmd", MagicMock(return_value=_exec_cmd_return)):
        assert "test" == helm._exec_string_return()


def test__exec_string_return_not_valid():
    _exec_cmd_return = {"retcode": -1, "stderr": "test"}
    with patch("salt.modules.helm._exec_cmd", MagicMock(return_value=_exec_cmd_return)):
        assert "test" == helm._exec_string_return()


def test__exec_dict_return_valide():
    _exec_cmd_return = {"retcode": 0, "stdout": '{"test": true}'}
    with patch("salt.modules.helm._exec_cmd", MagicMock(return_value=_exec_cmd_return)):
        assert {"test": True} == helm._exec_dict_return()


def test__exec_dict_return_valide_no_json():
    _exec_cmd_return = {"retcode": 0, "stdout": '{"test": true}'}
    with patch("salt.modules.helm._exec_cmd", MagicMock(return_value=_exec_cmd_return)):
        assert '{"test": true}' == helm._exec_dict_return(kvflags={"output": "table"})


def test__exec_dict_return_not_valid():
    _exec_cmd_return = {"retcode": -1, "stderr": "test"}
    with patch("salt.modules.helm._exec_cmd", MagicMock(return_value=_exec_cmd_return)):
        assert "test" == helm._exec_dict_return()


def test_completion():
    magic_mock = MagicMock(return_value="the_return")
    with patch("salt.modules.helm._exec_string_return", magic_mock):
        assert "the_return" == helm.completion("bash")
        assert [
            call(commands=["completion", "bash"], flags=None, kvflags=None)
        ] == magic_mock.mock_calls


def test_create():
    magic_mock = MagicMock(return_value=True)
    with patch("salt.modules.helm._exec_true_return", magic_mock):
        assert True is helm.create("name")
        assert [
            call(commands=["create", "name"], flags=None, kvflags=None)
        ] == magic_mock.mock_calls


def test_dependency_build():
    magic_mock = MagicMock(return_value=True)
    with patch("salt.modules.helm._exec_true_return", magic_mock):
        assert True is helm.dependency_build("chart")
        assert [
            call(
                commands=["dependency", "build", "chart"],
                flags=None,
                kvflags=None,
            )
        ] == magic_mock.mock_calls


def test_dependency_list():
    magic_mock = MagicMock(return_value="the_return")
    with patch("salt.modules.helm._exec_string_return", magic_mock):
        assert "the_return" == helm.dependency_list("chart")
        assert [
            call(
                commands=["dependency", "list", "chart"],
                flags=None,
                kvflags=None,
            )
        ] == magic_mock.mock_calls


def test_dependency_update():
    magic_mock = MagicMock(return_value=True)
    with patch("salt.modules.helm._exec_true_return", magic_mock):
        assert True is helm.dependency_update("chart")
        assert [
            call(
                commands=["dependency", "update", "chart"],
                flags=None,
                kvflags=None,
            )
        ] == magic_mock.mock_calls


def test_env():
    magic_mock = MagicMock(return_value="the_return")
    with patch("salt.modules.helm._exec_string_return", magic_mock):
        assert "the_return" == helm.env()
        assert [
            call(commands=["env"], flags=None, kvflags=None)
        ] == magic_mock.mock_calls


def test_get_all():
    magic_mock = MagicMock(return_value="the_return")
    with patch("salt.modules.helm._exec_string_return", magic_mock):
        assert "the_return" == helm.get_all("release")
        assert [
            call(commands=["get", "all", "release"], flags=None, kvflags=None)
        ] == magic_mock.mock_calls


def test_get_hooks():
    magic_mock = MagicMock(return_value="the_return")
    with patch("salt.modules.helm._exec_string_return", magic_mock):
        assert "the_return" == helm.get_hooks("release")
        assert [
            call(commands=["get", "hooks", "release"], flags=None, kvflags=None)
        ] == magic_mock.mock_calls


def test_get_manifest():
    magic_mock = MagicMock(return_value="the_return")
    with patch("salt.modules.helm._exec_string_return", magic_mock):
        assert "the_return" == helm.get_manifest("release")
        assert [
            call(
                commands=["get", "manifest", "release"],
                flags=None,
                kvflags=None,
            )
        ] == magic_mock.mock_calls


def test_get_notes():
    magic_mock = MagicMock(return_value="the_return")
    with patch("salt.modules.helm._exec_string_return", magic_mock):
        assert "the_return" == helm.get_notes("release")
        assert [
            call(commands=["get", "notes", "release"], flags=None, kvflags=None)
        ] == magic_mock.mock_calls


def test_get_values():
    magic_mock = MagicMock(return_value={"test": True})
    with patch("salt.modules.helm._exec_dict_return", magic_mock):
        assert {"test": True} == helm.get_values("release")
        assert [
            call(commands=["get", "values", "release"], flags=None, kvflags=None)
        ] == magic_mock.mock_calls


def test_help_():
    magic_mock = MagicMock(return_value="the_return")
    with patch("salt.modules.helm._exec_string_return", magic_mock):
        assert "the_return" == helm.help_("command")
        assert [
            call(commands=["help", "command"], flags=None, kvflags=None)
        ] == magic_mock.mock_calls


def test_history():
    magic_mock = MagicMock(return_value={"test": True})
    with patch("salt.modules.helm._exec_dict_return", magic_mock):
        assert {"test": True} == helm.history("release")
        assert [
            call(commands=["history", "release"], flags=None, kvflags=None)
        ] == magic_mock.mock_calls


def test_install():
    magic_mock = MagicMock(return_value=True)
    with patch("salt.modules.helm._exec_true_return", magic_mock):
        assert True is helm.install("release", "chart")
        assert [
            call(
                commands=["install", "release", "chart"],
                flags=None,
                kvflags=None,
            )
        ] == magic_mock.mock_calls


def test_lint():
    magic_mock = MagicMock(return_value=True)
    with patch("salt.modules.helm._exec_true_return", magic_mock):
        assert True is helm.lint("path")
        assert [
            call(commands=["lint", "path"], flags=None, kvflags=None)
        ] == magic_mock.mock_calls


def test_list_():
    magic_mock = MagicMock(return_value={"test": True})
    with patch("salt.modules.helm._exec_dict_return", magic_mock):
        assert {"test": True} == helm.list_()
        assert [
            call(commands=["list"], flags=None, kvflags=None)
        ] == magic_mock.mock_calls


def test_package():
    magic_mock = MagicMock(return_value=True)
    with patch("salt.modules.helm._exec_true_return", magic_mock):
        assert True is helm.package("chart")
        assert [
            call(commands=["package", "chart"], flags=None, kvflags=None)
        ] == magic_mock.mock_calls


def test_plugin_install():
    magic_mock = MagicMock(return_value=True)
    with patch("salt.modules.helm._exec_true_return", magic_mock):
        assert True is helm.plugin_install("path")
        assert [
            call(commands=["plugin", "install", "path"], flags=None, kvflags=None)
        ] == magic_mock.mock_calls


def test_plugin_list():
    magic_mock = MagicMock(return_value="the_return")
    with patch("salt.modules.helm._exec_string_return", magic_mock):
        assert "the_return" == helm.plugin_list()
        assert [
            call(commands=["plugin", "list"], flags=None, kvflags=None)
        ] == magic_mock.mock_calls


def test_plugin_uninstall():
    magic_mock = MagicMock(return_value=True)
    with patch("salt.modules.helm._exec_true_return", magic_mock):
        assert True is helm.plugin_uninstall("plugin")
        assert [
            call(
                commands=["plugin", "uninstall", "plugin"],
                flags=None,
                kvflags=None,
            )
        ] == magic_mock.mock_calls


def test_plugin_update():
    magic_mock = MagicMock(return_value=True)
    with patch("salt.modules.helm._exec_true_return", magic_mock):
        assert True is helm.plugin_update("plugin")
        assert [
            call(
                commands=["plugin", "update", "plugin"],
                flags=None,
                kvflags=None,
            )
        ] == magic_mock.mock_calls


def test_pull():
    magic_mock = MagicMock(return_value=True)
    with patch("salt.modules.helm._exec_true_return", magic_mock):
        assert True is helm.pull("pkg")
        assert [
            call(commands=["pull", "pkg"], flags=None, kvflags=None)
        ] == magic_mock.mock_calls


def test_repo_add():
    magic_mock = MagicMock(return_value=True)
    with patch("salt.modules.helm._exec_true_return", magic_mock):
        assert True is helm.repo_add("name", "url")
        assert [
            call(
                commands=["repo", "add", "name", "url"],
                flags=None,
                kvflags=None,
            )
        ] == magic_mock.mock_calls


def test_repo_index():
    magic_mock = MagicMock(return_value=True)
    with patch("salt.modules.helm._exec_true_return", magic_mock):
        assert True is helm.repo_index("directory")
        assert [
            call(
                commands=["repo", "index", "directory"],
                flags=None,
                kvflags=None,
            )
        ] == magic_mock.mock_calls


def test_repo_list():
    magic_mock = MagicMock(return_value={"test": True})
    with patch("salt.modules.helm._exec_dict_return", magic_mock):
        assert {"test": True} == helm.repo_list()
        assert [
            call(commands=["repo", "list"], flags=None, kvflags=None)
        ] == magic_mock.mock_calls


def test_repo_remove():
    magic_mock = MagicMock(return_value=True)
    with patch("salt.modules.helm._exec_true_return", magic_mock):
        assert True is helm.repo_remove("name")
        assert [
            call(commands=["repo", "remove", "name"], flags=None, kvflags=None)
        ] == magic_mock.mock_calls


def test_repo_update():
    magic_mock = MagicMock(return_value=True)
    with patch("salt.modules.helm._exec_true_return", magic_mock):
        assert True is helm.repo_update()
        assert [
            call(commands=["repo", "update"], flags=None, kvflags=None)
        ] == magic_mock.mock_calls


def test_repo_manage_present_bad_list():
    with patch("salt.modules.helm.repo_list", MagicMock(return_value=None)):
        with pytest.raises(CommandExecutionError):
            helm.repo_manage(present=["test"])


def test_repo_manage_present_bad_format():
    with patch("salt.modules.helm.repo_list", MagicMock(return_value=None)):
        with pytest.raises(CommandExecutionError):
            helm.repo_manage(present=[{"test": True}])


def test_repo_manage_present_failed():
    result_wanted = {
        "present": [],
        "added": [],
        "absent": [],
        "removed": [],
        "failed": [{"name": "myname", "url": "myurl"}],
    }
    with patch("salt.modules.helm.repo_list", MagicMock(return_value=None)):
        with patch("salt.modules.helm.repo_add", MagicMock(return_value="failed")):
            assert (
                helm.repo_manage(present=[{"name": "myname", "url": "myurl"}])
                == result_wanted
            )


def test_repo_manage_present_succeed():
    result_wanted = {
        "present": [],
        "added": [{"name": "myname", "url": "myurl"}],
        "absent": [],
        "removed": [],
        "failed": [],
    }
    with patch("salt.modules.helm.repo_list", MagicMock(return_value=None)):
        with patch("salt.modules.helm.repo_add", MagicMock(return_value=True)):
            assert (
                helm.repo_manage(present=[{"name": "myname", "url": "myurl"}])
                == result_wanted
            )


def test_repo_manage_present_already_present():
    result_wanted = {
        "present": [{"name": "myname", "url": "myurl"}],
        "added": [],
        "absent": [],
        "removed": [],
        "failed": [],
    }
    with patch(
        "salt.modules.helm.repo_list",
        MagicMock(return_value=[{"name": "myname", "url": "myurl"}]),
    ):
        assert (
            helm.repo_manage(present=[{"name": "myname", "url": "myurl"}])
            == result_wanted
        )


def test_repo_manage_prune():
    result_wanted = {
        "present": [],
        "added": [],
        "absent": [],
        "removed": ["myname"],
        "failed": [],
    }
    with patch(
        "salt.modules.helm.repo_list",
        MagicMock(return_value=[{"name": "myname", "url": "myurl"}]),
    ):
        with patch("salt.modules.helm.repo_remove", MagicMock(return_value=True)):
            assert helm.repo_manage(prune=True) == result_wanted


def test_repo_manage_absent():
    result_wanted = {
        "present": [],
        "added": [],
        "absent": ["myname"],
        "removed": [],
        "failed": [],
    }
    with patch("salt.modules.helm.repo_list", MagicMock(return_value=None)):
        with patch("salt.modules.helm.repo_remove", MagicMock(return_value=False)):
            assert helm.repo_manage(absent=["myname"]) == result_wanted


def test_repo_manage_removed():
    result_wanted = {
        "present": [],
        "added": [],
        "absent": [],
        "removed": ["myname"],
        "failed": [],
    }
    with patch("salt.modules.helm.repo_list", MagicMock(return_value=None)):
        with patch("salt.modules.helm.repo_remove", MagicMock(return_value=True)):
            assert helm.repo_manage(absent=["myname"]) == result_wanted


def test_rollback():
    magic_mock = MagicMock(return_value=True)
    with patch("salt.modules.helm._exec_true_return", magic_mock):
        assert True is helm.rollback("release", "revision")
        assert [
            call(
                commands=["rollback", "release", "revision"],
                flags=None,
                kvflags=None,
            )
        ] == magic_mock.mock_calls


def test_search_hub():
    magic_mock = MagicMock(return_value={"test": True})
    with patch("salt.modules.helm._exec_dict_return", magic_mock):
        assert {"test": True} == helm.search_hub("keyword")
        assert [
            call(commands=["search", "hub", "keyword"], flags=None, kvflags=None)
        ] == magic_mock.mock_calls


def test_search_repo():
    magic_mock = MagicMock(return_value={"test": True})
    with patch("salt.modules.helm._exec_dict_return", magic_mock):
        assert {"test": True} == helm.search_repo("keyword")
        assert [
            call(commands=["search", "repo", "keyword"], flags=None, kvflags=None)
        ] == magic_mock.mock_calls


def test_show_all():
    magic_mock = MagicMock(return_value="the_return")
    with patch("salt.modules.helm._exec_string_return", magic_mock):
        assert "the_return" == helm.show_all("chart")
        assert [
            call(commands=["show", "all", "chart"], flags=None, kvflags=None)
        ] == magic_mock.mock_calls


def test_show_chart():
    magic_mock = MagicMock(return_value="the_return")
    with patch("salt.modules.helm._exec_string_return", magic_mock):
        assert "the_return" == helm.show_chart("chart")
        assert [
            call(commands=["show", "chart", "chart"], flags=None, kvflags=None)
        ] == magic_mock.mock_calls


def test_show_readme():
    magic_mock = MagicMock(return_value="the_return")
    with patch("salt.modules.helm._exec_string_return", magic_mock):
        assert "the_return" == helm.show_readme("chart")
        assert [
            call(commands=["show", "readme", "chart"], flags=None, kvflags=None)
        ] == magic_mock.mock_calls


def test_show_values():
    magic_mock = MagicMock(return_value="the_return")
    with patch("salt.modules.helm._exec_string_return", magic_mock):
        assert "the_return" == helm.show_values("chart")
        assert [
            call(commands=["show", "values", "chart"], flags=None, kvflags=None)
        ] == magic_mock.mock_calls


def test_status():
    magic_mock = MagicMock(return_value={"test": True})
    with patch("salt.modules.helm._exec_dict_return", magic_mock):
        assert {"test": True} == helm.status("release")
        assert [
            call(commands=["status", "release"], flags=None, kvflags=None)
        ] == magic_mock.mock_calls


def test_template():
    magic_mock = MagicMock(return_value="the_return")
    with patch("salt.modules.helm._exec_string_return", magic_mock):
        assert "the_return" == helm.template("name", "chart")
        assert [
            call(commands=["template", "name", "chart"], flags=None, kvflags=None)
        ] == magic_mock.mock_calls


def test_test():
    magic_mock = MagicMock(return_value="the_return")
    with patch("salt.modules.helm._exec_string_return", magic_mock):
        assert "the_return" == helm.test("release")
        assert [
            call(commands=["test", "release"], flags=None, kvflags=None)
        ] == magic_mock.mock_calls


def test_uninstall():
    magic_mock = MagicMock(return_value=True)
    with patch("salt.modules.helm._exec_true_return", magic_mock):
        assert True is helm.uninstall("release")
        assert [
            call(commands=["uninstall", "release"], flags=None, kvflags=None)
        ] == magic_mock.mock_calls


def test_upgrade():
    magic_mock = MagicMock(return_value=True)
    with patch("salt.modules.helm._exec_true_return", magic_mock):
        assert True is helm.upgrade("release", "chart")
        assert [
            call(
                commands=["upgrade", "release", "chart"],
                flags=None,
                kvflags=None,
            )
        ] == magic_mock.mock_calls


def test_verify():
    magic_mock = MagicMock(return_value=True)
    with patch("salt.modules.helm._exec_true_return", magic_mock):
        assert True is helm.verify("path")
        assert [
            call(commands=["verify", "path"], flags=None, kvflags=None)
        ] == magic_mock.mock_calls


def test_version():
    magic_mock = MagicMock(return_value="the_return")
    with patch("salt.modules.helm._exec_string_return", magic_mock):
        assert "the_return" == helm.version()
        assert [
            call(commands=["version"], flags=None, kvflags=None)
        ] == magic_mock.mock_calls
