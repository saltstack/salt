import salt.modules.helm as helm

# Import Exception
from salt.exceptions import CommandExecutionError
from tests.support.mixins import LoaderModuleMockMixin
from tests.support.mock import MagicMock, call, patch
from tests.support.unit import TestCase


class HelmTestCase(TestCase, LoaderModuleMockMixin):
    """
    Test cases for salt.modules.helm
    """

    def setup_loader_modules(self):
        return {helm: {}}

    def test__prepare_cmd(self):
        self.assertEqual(helm._prepare_cmd(), ("helm",))

    def test__prepare_cmd_binary(self):
        self.assertEqual(helm._prepare_cmd(binary="binary"), ("binary",))

    def test__prepare_cmd_commands(self):
        self.assertEqual(
            helm._prepare_cmd(commands=["com1", "com2"]),
            (
                "helm",
                "com1",
                "com2",
            ),
        )

    def test__prepare_cmd_flags(self):
        self.assertEqual(
            helm._prepare_cmd(flags=["flag1", "--flag2"]),
            (
                "helm",
                "--flag1",
                "--flag2",
            ),
        )

    def test__prepare_cmd_kvflags(self):
        result_tuple = helm._prepare_cmd(
            kvflags={"kflag1": "vflag1", "--kflag2": "vflag2"}
        )
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

        #
        self.assertEqual(
            True, result_tuple == tuple_valide_1 or result_tuple == tuple_valide_2
        )

    def test__exec_cmd(self):
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
            self.assertEqual(helm._exec_cmd(), result)

    def test__exec_true_return_valid(self):
        _exec_cmd_return = {"retcode": 0}
        with patch(
            "salt.modules.helm._exec_cmd", MagicMock(return_value=_exec_cmd_return)
        ):
            self.assertEqual(True, helm._exec_true_return())

    def test__exec_true_return_not_valid(self):
        _exec_cmd_return = {"retcode": -1, "stderr": "test"}
        with patch(
            "salt.modules.helm._exec_cmd", MagicMock(return_value=_exec_cmd_return)
        ):
            self.assertEqual("test", helm._exec_true_return())

    def test__exec_string_return_valid(self):
        _exec_cmd_return = {"retcode": 0, "stdout": "test"}
        with patch(
            "salt.modules.helm._exec_cmd", MagicMock(return_value=_exec_cmd_return)
        ):
            self.assertEqual("test", helm._exec_string_return())

    def test__exec_string_return_not_valid(self):
        _exec_cmd_return = {"retcode": -1, "stderr": "test"}
        with patch(
            "salt.modules.helm._exec_cmd", MagicMock(return_value=_exec_cmd_return)
        ):
            self.assertEqual("test", helm._exec_string_return())

    def test__exec_dict_return_valide(self):
        _exec_cmd_return = {"retcode": 0, "stdout": '{"test": true}'}
        with patch(
            "salt.modules.helm._exec_cmd", MagicMock(return_value=_exec_cmd_return)
        ):
            self.assertEqual({"test": True}, helm._exec_dict_return())

    def test__exec_dict_return_valide_no_json(self):
        _exec_cmd_return = {"retcode": 0, "stdout": '{"test": true}'}
        with patch(
            "salt.modules.helm._exec_cmd", MagicMock(return_value=_exec_cmd_return)
        ):
            self.assertEqual(
                '{"test": true}', helm._exec_dict_return(kvflags={"output": "table"})
            )

    def test__exec_dict_return_not_valid(self):
        _exec_cmd_return = {"retcode": -1, "stderr": "test"}
        with patch(
            "salt.modules.helm._exec_cmd", MagicMock(return_value=_exec_cmd_return)
        ):
            self.assertEqual("test", helm._exec_dict_return())

    def test_completion(self):
        magic_mock = MagicMock(return_value="the_return")
        with patch("salt.modules.helm._exec_string_return", magic_mock):
            self.assertEqual("the_return", helm.completion("bash"))
            self.assertEqual(
                [call(commands=["completion", "bash"], flags=None, kvflags=None)],
                magic_mock.mock_calls,
            )

    def test_create(self):
        magic_mock = MagicMock(return_value=True)
        with patch("salt.modules.helm._exec_true_return", magic_mock):
            self.assertEqual(True, helm.create("name"))
            self.assertEqual(
                [call(commands=["create", "name"], flags=None, kvflags=None)],
                magic_mock.mock_calls,
            )

    def test_dependency_build(self):
        magic_mock = MagicMock(return_value=True)
        with patch("salt.modules.helm._exec_true_return", magic_mock):
            self.assertEqual(True, helm.dependency_build("chart"))
            self.assertEqual(
                [
                    call(
                        commands=["dependency", "build", "chart"],
                        flags=None,
                        kvflags=None,
                    )
                ],
                magic_mock.mock_calls,
            )

    def test_dependency_list(self):
        magic_mock = MagicMock(return_value="the_return")
        with patch("salt.modules.helm._exec_string_return", magic_mock):
            self.assertEqual("the_return", helm.dependency_list("chart"))
            self.assertEqual(
                [
                    call(
                        commands=["dependency", "list", "chart"],
                        flags=None,
                        kvflags=None,
                    )
                ],
                magic_mock.mock_calls,
            )

    def test_dependency_update(self):
        magic_mock = MagicMock(return_value=True)
        with patch("salt.modules.helm._exec_true_return", magic_mock):
            self.assertEqual(True, helm.dependency_update("chart"))
            self.assertEqual(
                [
                    call(
                        commands=["dependency", "update", "chart"],
                        flags=None,
                        kvflags=None,
                    )
                ],
                magic_mock.mock_calls,
            )

    def test_env(self):
        magic_mock = MagicMock(return_value="the_return")
        with patch("salt.modules.helm._exec_string_return", magic_mock):
            self.assertEqual("the_return", helm.env())
            self.assertEqual(
                [call(commands=["env"], flags=None, kvflags=None)],
                magic_mock.mock_calls,
            )

    def test_get_all(self):
        magic_mock = MagicMock(return_value="the_return")
        with patch("salt.modules.helm._exec_string_return", magic_mock):
            self.assertEqual("the_return", helm.get_all("release"))
            self.assertEqual(
                [call(commands=["get", "all", "release"], flags=None, kvflags=None)],
                magic_mock.mock_calls,
            )

    def test_get_hooks(self):
        magic_mock = MagicMock(return_value="the_return")
        with patch("salt.modules.helm._exec_string_return", magic_mock):
            self.assertEqual("the_return", helm.get_hooks("release"))
            self.assertEqual(
                [call(commands=["get", "hooks", "release"], flags=None, kvflags=None)],
                magic_mock.mock_calls,
            )

    def test_get_manifest(self):
        magic_mock = MagicMock(return_value="the_return")
        with patch("salt.modules.helm._exec_string_return", magic_mock):
            self.assertEqual("the_return", helm.get_manifest("release"))
            self.assertEqual(
                [
                    call(
                        commands=["get", "manifest", "release"],
                        flags=None,
                        kvflags=None,
                    )
                ],
                magic_mock.mock_calls,
            )

    def test_get_notes(self):
        magic_mock = MagicMock(return_value="the_return")
        with patch("salt.modules.helm._exec_string_return", magic_mock):
            self.assertEqual("the_return", helm.get_notes("release"))
            self.assertEqual(
                [call(commands=["get", "notes", "release"], flags=None, kvflags=None)],
                magic_mock.mock_calls,
            )

    def test_get_values(self):
        magic_mock = MagicMock(return_value={"test": True})
        with patch("salt.modules.helm._exec_dict_return", magic_mock):
            self.assertEqual({"test": True}, helm.get_values("release"))
            self.assertEqual(
                [call(commands=["get", "values", "release"], flags=None, kvflags=None)],
                magic_mock.mock_calls,
            )

    def test_help_(self):
        magic_mock = MagicMock(return_value="the_return")
        with patch("salt.modules.helm._exec_string_return", magic_mock):
            self.assertEqual("the_return", helm.help_("command"))
            self.assertEqual(
                [call(commands=["help", "command"], flags=None, kvflags=None)],
                magic_mock.mock_calls,
            )

    def test_history(self):
        magic_mock = MagicMock(return_value={"test": True})
        with patch("salt.modules.helm._exec_dict_return", magic_mock):
            self.assertEqual({"test": True}, helm.history("release"))
            self.assertEqual(
                [call(commands=["history", "release"], flags=None, kvflags=None)],
                magic_mock.mock_calls,
            )

    def test_install(self):
        magic_mock = MagicMock(return_value=True)
        with patch("salt.modules.helm._exec_true_return", magic_mock):
            self.assertEqual(True, helm.install("release", "chart"))
            self.assertEqual(
                [
                    call(
                        commands=["install", "release", "chart"],
                        flags=None,
                        kvflags=None,
                    )
                ],
                magic_mock.mock_calls,
            )

    def test_lint(self):
        magic_mock = MagicMock(return_value=True)
        with patch("salt.modules.helm._exec_true_return", magic_mock):
            self.assertEqual(True, helm.lint("path"))
            self.assertEqual(
                [call(commands=["lint", "path"], flags=None, kvflags=None)],
                magic_mock.mock_calls,
            )

    def test_list_(self):
        magic_mock = MagicMock(return_value={"test": True})
        with patch("salt.modules.helm._exec_dict_return", magic_mock):
            self.assertEqual({"test": True}, helm.list_())
            self.assertEqual(
                [call(commands=["list"], flags=None, kvflags=None)],
                magic_mock.mock_calls,
            )

    def test_package(self):
        magic_mock = MagicMock(return_value=True)
        with patch("salt.modules.helm._exec_true_return", magic_mock):
            self.assertEqual(True, helm.package("chart"))
            self.assertEqual(
                [call(commands=["package", "chart"], flags=None, kvflags=None)],
                magic_mock.mock_calls,
            )

    def test_plugin_install(self):
        magic_mock = MagicMock(return_value=True)
        with patch("salt.modules.helm._exec_true_return", magic_mock):
            self.assertEqual(True, helm.plugin_install("path"))
            self.assertEqual(
                [
                    call(
                        commands=["plugin", "install", "path"], flags=None, kvflags=None
                    )
                ],
                magic_mock.mock_calls,
            )

    def test_plugin_list(self):
        magic_mock = MagicMock(return_value="the_return")
        with patch("salt.modules.helm._exec_string_return", magic_mock):
            self.assertEqual("the_return", helm.plugin_list())
            self.assertEqual(
                [call(commands=["plugin", "list"], flags=None, kvflags=None)],
                magic_mock.mock_calls,
            )

    def test_plugin_uninstall(self):
        magic_mock = MagicMock(return_value=True)
        with patch("salt.modules.helm._exec_true_return", magic_mock):
            self.assertEqual(True, helm.plugin_uninstall("plugin"))
            self.assertEqual(
                [
                    call(
                        commands=["plugin", "uninstall", "plugin"],
                        flags=None,
                        kvflags=None,
                    )
                ],
                magic_mock.mock_calls,
            )

    def test_plugin_update(self):
        magic_mock = MagicMock(return_value=True)
        with patch("salt.modules.helm._exec_true_return", magic_mock):
            self.assertEqual(True, helm.plugin_update("plugin"))
            self.assertEqual(
                [
                    call(
                        commands=["plugin", "update", "plugin"],
                        flags=None,
                        kvflags=None,
                    )
                ],
                magic_mock.mock_calls,
            )

    def test_pull(self):
        magic_mock = MagicMock(return_value=True)
        with patch("salt.modules.helm._exec_true_return", magic_mock):
            self.assertEqual(True, helm.pull("pkg"))
            self.assertEqual(
                [call(commands=["pull", "pkg"], flags=None, kvflags=None)],
                magic_mock.mock_calls,
            )

    def test_repo_add(self):
        magic_mock = MagicMock(return_value=True)
        with patch("salt.modules.helm._exec_true_return", magic_mock):
            self.assertEqual(True, helm.repo_add("name", "url"))
            self.assertEqual(
                [
                    call(
                        commands=["repo", "add", "name", "url"],
                        flags=None,
                        kvflags=None,
                    )
                ],
                magic_mock.mock_calls,
            )

    def test_repo_index(self):
        magic_mock = MagicMock(return_value=True)
        with patch("salt.modules.helm._exec_true_return", magic_mock):
            self.assertEqual(True, helm.repo_index("directory"))
            self.assertEqual(
                [
                    call(
                        commands=["repo", "index", "directory"],
                        flags=None,
                        kvflags=None,
                    )
                ],
                magic_mock.mock_calls,
            )

    def test_repo_list(self):
        magic_mock = MagicMock(return_value={"test": True})
        with patch("salt.modules.helm._exec_dict_return", magic_mock):
            self.assertEqual({"test": True}, helm.repo_list())
            self.assertEqual(
                [call(commands=["repo", "list"], flags=None, kvflags=None)],
                magic_mock.mock_calls,
            )

    def test_repo_remove(self):
        magic_mock = MagicMock(return_value=True)
        with patch("salt.modules.helm._exec_true_return", magic_mock):
            self.assertEqual(True, helm.repo_remove("name"))
            self.assertEqual(
                [call(commands=["repo", "remove", "name"], flags=None, kvflags=None)],
                magic_mock.mock_calls,
            )

    def test_repo_update(self):
        magic_mock = MagicMock(return_value=True)
        with patch("salt.modules.helm._exec_true_return", magic_mock):
            self.assertEqual(True, helm.repo_update())
            self.assertEqual(
                [call(commands=["repo", "update"], flags=None, kvflags=None)],
                magic_mock.mock_calls,
            )

    def test_repo_manage_present_bad_list(self):
        with patch("salt.modules.helm.repo_list", MagicMock(return_value=None)):
            with self.assertRaises(CommandExecutionError):
                helm.repo_manage(present=["test"])

    def test_repo_manage_present_bad_format(self):
        with patch("salt.modules.helm.repo_list", MagicMock(return_value=None)):
            with self.assertRaises(CommandExecutionError):
                helm.repo_manage(present=[{"test": True}])

    def test_repo_manage_present_failed(self):
        result_wanted = {
            "present": [],
            "added": [],
            "absent": [],
            "removed": [],
            "failed": [{"name": "myname", "url": "myurl"}],
        }
        with patch("salt.modules.helm.repo_list", MagicMock(return_value=None)):
            with patch("salt.modules.helm.repo_add", MagicMock(return_value="failed")):
                self.assertEqual(
                    helm.repo_manage(present=[{"name": "myname", "url": "myurl"}]),
                    result_wanted,
                )

    def test_repo_manage_present_succeed(self):
        result_wanted = {
            "present": [],
            "added": [{"name": "myname", "url": "myurl"}],
            "absent": [],
            "removed": [],
            "failed": [],
        }
        with patch("salt.modules.helm.repo_list", MagicMock(return_value=None)):
            with patch("salt.modules.helm.repo_add", MagicMock(return_value=True)):
                self.assertEqual(
                    helm.repo_manage(present=[{"name": "myname", "url": "myurl"}]),
                    result_wanted,
                )

    def test_repo_manage_present_already_present(self):
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
            self.assertEqual(
                helm.repo_manage(present=[{"name": "myname", "url": "myurl"}]),
                result_wanted,
            )

    def test_repo_manage_prune(self):
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
                self.assertEqual(helm.repo_manage(prune=True), result_wanted)

    def test_repo_manage_absent(self):
        result_wanted = {
            "present": [],
            "added": [],
            "absent": ["myname"],
            "removed": [],
            "failed": [],
        }
        with patch("salt.modules.helm.repo_list", MagicMock(return_value=None)):
            with patch("salt.modules.helm.repo_remove", MagicMock(return_value=False)):
                self.assertEqual(helm.repo_manage(absent=["myname"]), result_wanted)

    def test_repo_manage_removed(self):
        result_wanted = {
            "present": [],
            "added": [],
            "absent": [],
            "removed": ["myname"],
            "failed": [],
        }
        with patch("salt.modules.helm.repo_list", MagicMock(return_value=None)):
            with patch("salt.modules.helm.repo_remove", MagicMock(return_value=True)):
                self.assertEqual(helm.repo_manage(absent=["myname"]), result_wanted)

    def test_rollback(self):
        magic_mock = MagicMock(return_value=True)
        with patch("salt.modules.helm._exec_true_return", magic_mock):
            self.assertEqual(True, helm.rollback("release", "revision"))
            self.assertEqual(
                [
                    call(
                        commands=["rollback", "release", "revision"],
                        flags=None,
                        kvflags=None,
                    )
                ],
                magic_mock.mock_calls,
            )

    def test_search_hub(self):
        magic_mock = MagicMock(return_value={"test": True})
        with patch("salt.modules.helm._exec_dict_return", magic_mock):
            self.assertEqual({"test": True}, helm.search_hub("keyword"))
            self.assertEqual(
                [call(commands=["search", "hub", "keyword"], flags=None, kvflags=None)],
                magic_mock.mock_calls,
            )

    def test_search_repo(self):
        magic_mock = MagicMock(return_value={"test": True})
        with patch("salt.modules.helm._exec_dict_return", magic_mock):
            self.assertEqual({"test": True}, helm.search_repo("keyword"))
            self.assertEqual(
                [
                    call(
                        commands=["search", "repo", "keyword"], flags=None, kvflags=None
                    )
                ],
                magic_mock.mock_calls,
            )

    def test_show_all(self):
        magic_mock = MagicMock(return_value="the_return")
        with patch("salt.modules.helm._exec_string_return", magic_mock):
            self.assertEqual("the_return", helm.show_all("chart"))
            self.assertEqual(
                [call(commands=["show", "all", "chart"], flags=None, kvflags=None)],
                magic_mock.mock_calls,
            )

    def test_show_chart(self):
        magic_mock = MagicMock(return_value="the_return")
        with patch("salt.modules.helm._exec_string_return", magic_mock):
            self.assertEqual("the_return", helm.show_chart("chart"))
            self.assertEqual(
                [call(commands=["show", "chart", "chart"], flags=None, kvflags=None)],
                magic_mock.mock_calls,
            )

    def test_show_readme(self):
        magic_mock = MagicMock(return_value="the_return")
        with patch("salt.modules.helm._exec_string_return", magic_mock):
            self.assertEqual("the_return", helm.show_readme("chart"))
            self.assertEqual(
                [call(commands=["show", "readme", "chart"], flags=None, kvflags=None)],
                magic_mock.mock_calls,
            )

    def test_show_values(self):
        magic_mock = MagicMock(return_value="the_return")
        with patch("salt.modules.helm._exec_string_return", magic_mock):
            self.assertEqual("the_return", helm.show_values("chart"))
            self.assertEqual(
                [call(commands=["show", "values", "chart"], flags=None, kvflags=None)],
                magic_mock.mock_calls,
            )

    def test_status(self):
        magic_mock = MagicMock(return_value={"test": True})
        with patch("salt.modules.helm._exec_dict_return", magic_mock):
            self.assertEqual({"test": True}, helm.status("release"))
            self.assertEqual(
                [call(commands=["status", "release"], flags=None, kvflags=None)],
                magic_mock.mock_calls,
            )

    def test_template(self):
        magic_mock = MagicMock(return_value="the_return")
        with patch("salt.modules.helm._exec_string_return", magic_mock):
            self.assertEqual("the_return", helm.template("name", "chart"))
            self.assertEqual(
                [
                    call(
                        commands=["template", "name", "chart"], flags=None, kvflags=None
                    )
                ],
                magic_mock.mock_calls,
            )

    def test_test(self):
        magic_mock = MagicMock(return_value="the_return")
        with patch("salt.modules.helm._exec_string_return", magic_mock):
            self.assertEqual("the_return", helm.test("release"))
            self.assertEqual(
                [call(commands=["test", "release"], flags=None, kvflags=None)],
                magic_mock.mock_calls,
            )

    def test_uninstall(self):
        magic_mock = MagicMock(return_value=True)
        with patch("salt.modules.helm._exec_true_return", magic_mock):
            self.assertEqual(True, helm.uninstall("release"))
            self.assertEqual(
                [call(commands=["uninstall", "release"], flags=None, kvflags=None)],
                magic_mock.mock_calls,
            )

    def test_upgrade(self):
        magic_mock = MagicMock(return_value=True)
        with patch("salt.modules.helm._exec_true_return", magic_mock):
            self.assertEqual(True, helm.upgrade("release", "chart"))
            self.assertEqual(
                [
                    call(
                        commands=["upgrade", "release", "chart"],
                        flags=None,
                        kvflags=None,
                    )
                ],
                magic_mock.mock_calls,
            )

    def test_verify(self):
        magic_mock = MagicMock(return_value=True)
        with patch("salt.modules.helm._exec_true_return", magic_mock):
            self.assertEqual(True, helm.verify("path"))
            self.assertEqual(
                [call(commands=["verify", "path"], flags=None, kvflags=None)],
                magic_mock.mock_calls,
            )

    def test_version(self):
        magic_mock = MagicMock(return_value="the_return")
        with patch("salt.modules.helm._exec_string_return", magic_mock):
            self.assertEqual("the_return", helm.version())
            self.assertEqual(
                [call(commands=["version"], flags=None, kvflags=None)],
                magic_mock.mock_calls,
            )
