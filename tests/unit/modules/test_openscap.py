import salt.modules.openscap as openscap
from salt.exceptions import ArgumentValueError
from tests.support.mixins import LoaderModuleMockMixin
from tests.support.mock import MagicMock, patch
from tests.support.unit import TestCase


class OpenscapTestCase(TestCase, LoaderModuleMockMixin):
    """
    Test cases for salt.module.openscap
    """

    def setup_loader_modules(self):
        return {openscap: {}}

    def test_version(self):
        """
        Test, if the short version is returned.
        """

        mocked_oscap_string = """OpenSCAP command line tool (oscap) 1.2.16
Copyright 2009--2017 Red Hat Inc., Durham, North Carolina.

==== Supported specifications ====
XCCDF Version: 1.2
OVAL Version: 5.11.1

==== Capabilities added by auto-loaded plugins ====
SCE Version: 1.0 (from libopenscap_sce.so.8)

==== Paths ====
Schema files: /usr/share/openscap/schemas
Default CPE files: /usr/share/openscap/cpe
Probes: /usr/lib/x86_64-linux-gnu/openscap

==== Inbuilt CPE names ====
Red Hat Enterprise Linux - cpe:/o:redhat:enterprise_linux
Red Hat Enterprise Linux 5 - cpe:/o:redhat:enterprise_linux:5

==== Supported OVAL objects and associated OpenSCAP probes ====
OVAL family   OVAL object                  OpenSCAP probe
----------    ----------                   ----------
(null)        system_info                  probe_system_info
independent   family                       probe_family"""

        with patch.dict(
            openscap.__salt__, {"cmd.run": MagicMock(return_value=mocked_oscap_string)}
        ):
            # Test if short output is correct
            self.assertEqual(openscap.version(), {"oscap": "1.2.16"})

            # Test if long output is correct
            self.assertIsInstance(openscap.version("all"), dict)

    def test_build_cmd(self):
        """
        Test if _build_cmd returns well formed cmds.
        """
        with patch.object(
            openscap, "_has_operation", MagicMock(return_value=True)
        ), patch.object(
            openscap, "_has_param", MagicMock(return_value=True)
        ), patch.object(
            openscap, "_oscap_cmd", MagicMock(return_value="/usr/bin/oscap")
        ):

            _module = "xccdf"
            _operation = "eval"
            _kwargs = {
                "check-engine-results": True,
                "without-syschar": True,
                "progress": True,
                "profile": "test",
                "tailoring-file": "/var/oscap/test_tailoring.xml",
            }

            # Test, if module and operation are added properly to Command. With and **kwargs
            self.assertEqual(
                openscap._build_cmd(_module, _operation, **_kwargs),
                "/usr/bin/oscap xccdf eval --check-engine-results --without-syschar --progress --profile test --tailoring-file /var/oscap/test_tailoring.xml",
            )

            # Test, if only the module without the operation is properly added to the command.
            self.assertEqual(
                openscap._build_cmd("info", **{"profiles": True}),
                "/usr/bin/oscap info --profiles",
            )

            # Test, if only the module without the operation is properly added to the command.
            self.assertEqual(
                openscap._build_cmd("info", **{"profile": "test"}),
                "/usr/bin/oscap info --profile test",
            )

        with patch.object(
            openscap, "_has_operation", MagicMock(return_value=False)
        ), patch.object(
            openscap, "_has_param", MagicMock(return_value=True)
        ), patch.object(
            openscap, "_oscap_cmd", MagicMock(return_value="/usr/bin/oscap")
        ):

            _module = "xccdf"
            _operation = "wrong_op"
            _kwargs = {
                "profile": "test",
                "tailoring-file": "/var/oscap/test_tailoring.xml",
            }

            # Test, if operation is supported by module
            with self.assertRaises(
                expected_exception=ArgumentValueError,
                msg="'xccdf' does not support 'wrong_op' operation!",
            ):
                openscap._build_cmd(_module, _operation, **_kwargs)

        with patch.object(
            openscap, "_has_operation", MagicMock(return_value=True)
        ), patch.object(
            openscap, "_has_param", MagicMock(return_value=False)
        ), patch.object(
            openscap, "_oscap_cmd", MagicMock(return_value="/usr/bin/oscap")
        ):

            _module = "xccdf"
            _operation = "eval"
            _kwargs = {
                "wrong-kw-param": "test",
                "profile": "test",
                "tailoring-file": "/var/oscap/test_tailoring.xml",
            }

            # Test, if args Param is supported by operation and module
            with self.assertRaises(
                expected_exception=ArgumentValueError,
                msg="'xccdf eval' does not support 'wrong-kw-param' parameter!",
            ):
                openscap._build_cmd(_module, _operation, **_kwargs)

    def test_xccdf(self):
        """
        Test the output of info.
        """
        _file = "/var/oscap/test.xml"
        _operation = "eval"
        _kwargs = {
            "profile": "test",
            "tailoring-file": "/var/oscap/test_tailoring.xml",
        }

        with patch.object(
            openscap, "_build_cmd", MagicMock(return_value="/usr/lib/oscap xccdf eval")
        ):

            # Test if 'file' parameter is set.
            self.assertEqual(openscap.xccdf(), "A File must be defined!")

        # Test results with successful upload
        with patch.object(
            openscap, "_has_operation", MagicMock(return_value=True)
        ), patch.object(
            openscap, "_has_param", MagicMock(return_value=True)
        ), patch.object(
            openscap, "_oscap_cmd", MagicMock(return_value="/usr/bin/oscap")
        ), patch.dict(
            openscap.__salt__, {"cp.push_dir": MagicMock(return_value=True)}
        ), patch(
            "salt.modules.openscap.tempfile.mkdtemp",
            MagicMock(return_value="/tmp/rand/path"),
        ), patch.dict(
            openscap.__salt__, {"cmd.retcode": MagicMock(side_effect=[0, 1, 2])}
        ):

            _kwargs = {
                "check-engine-results": True,
                "without-syschar": True,
                "progress": True,
            }

            # Test a Normal run with successful upload
            self.assertEqual(
                openscap.xccdf(file=_file, operation=_operation, **_kwargs),
                {
                    "success": True,
                    "upload_dir": "/tmp/rand/path",
                    "error": None,
                    "returncode": 0,
                },
            )

            # Test a SCAP Fail, which prevents the Upload
            self.assertEqual(
                openscap.xccdf(file=_file, operation=_operation, **_kwargs),
                {"success": False, "upload_dir": None, "error": None, "returncode": 1},
            )

            # Test a SCAP Success with failed checks and successful Upload
            self.assertEqual(
                openscap.xccdf(file=_file, operation=_operation, **_kwargs),
                {
                    "success": True,
                    "upload_dir": "/tmp/rand/path",
                    "error": None,
                    "returncode": 2,
                },
            )

        # Test resulsts with upload failed upload
        with patch.object(
            openscap, "_has_operation", MagicMock(return_value=True)
        ), patch.object(
            openscap, "_has_param", MagicMock(return_value=True)
        ), patch.object(
            openscap, "_oscap_cmd", MagicMock(return_value="/usr/bin/oscap")
        ), patch.dict(
            openscap.__salt__, {"cp.push_dir": MagicMock(return_value=False)}
        ), patch.dict(
            openscap.__salt__, {"cmd.retcode": MagicMock(side_effect=[0, 1, 2])}
        ):

            _kwargs = {
                "check-engine-results": True,
                "without-syschar": True,
                "progress": True,
            }

            # Test a Normal run with failed upload
            self.assertEqual(
                openscap.xccdf(file=_file, operation=_operation, **_kwargs),
                {"success": True, "upload_dir": None, "error": None, "returncode": 0},
            )

            # Test a Failing OpenSCAP run with failed upload (Gets disabled)
            self.assertEqual(
                openscap.xccdf(file=_file, operation=_operation, **_kwargs),
                {"success": False, "upload_dir": None, "error": None, "returncode": 1},
            )

            # Test a SCAP Success with failed checks and failed Upload
            self.assertEqual(
                openscap.xccdf(file=_file, operation=_operation, **_kwargs),
                {"success": True, "upload_dir": None, "error": None, "returncode": 2},
            )

    def test_new_openscap_xccdf_eval_success(self):
        with patch(
            "salt.modules.openscap.Popen",
            MagicMock(
                return_value=Mock(
                    **{"returncode": 0, "communicate.return_value": ("", "")}
                )
            ),
        ):
            response = openscap.xccdf_eval(
                self.policy_file,
                profile="Default",
                oval_results=True,
                results="results.xml",
                report="report.html",
            )

            self.assertEqual(openscap.tempfile.mkdtemp.call_count, 1)
            expected_cmd = [
                "oscap",
                "xccdf",
                "eval",
                "--oval-results",
                "--results",
                "results.xml",
                "--report",
                "report.html",
                "--profile",
                "Default",
                self.policy_file,
            ]
            openscap.Popen.assert_called_once_with(
                expected_cmd,
                cwd=openscap.tempfile.mkdtemp.return_value,
                stderr=subprocess.PIPE,
                stdout=subprocess.PIPE,
            )
            openscap.__salt__["cp.push_dir"].assert_called_once_with(
                self.random_temp_dir
            )
            self.assertEqual(openscap.shutil.rmtree.call_count, 1)
            self.assertEqual(
                response,
                {
                    "upload_dir": self.random_temp_dir,
                    "error": "",
                    "success": True,
                    "returncode": 0,
                },
            )

    def test_new_openscap_xccdf_eval_success_with_extra_ovalfiles(self):
        with patch(
            "salt.modules.openscap.Popen",
            MagicMock(
                return_value=Mock(
                    **{"returncode": 0, "communicate.return_value": ("", "")}
                )
            ),
        ):
            response = openscap.xccdf_eval(
                self.policy_file,
                ["/usr/share/xml/another-oval.xml", "/usr/share/xml/oval.xml"],
                profile="Default",
                oval_results=True,
                results="results.xml",
                report="report.html",
            )

            self.assertEqual(openscap.tempfile.mkdtemp.call_count, 1)
            expected_cmd = [
                "oscap",
                "xccdf",
                "eval",
                "--oval-results",
                "--results",
                "results.xml",
                "--report",
                "report.html",
                "--profile",
                "Default",
                self.policy_file,
                "/usr/share/xml/another-oval.xml",
                "/usr/share/xml/oval.xml",
            ]
            openscap.Popen.assert_called_once_with(
                expected_cmd,
                cwd=openscap.tempfile.mkdtemp.return_value,
                stderr=subprocess.PIPE,
                stdout=subprocess.PIPE,
            )
            openscap.__salt__["cp.push_dir"].assert_called_once_with(
                self.random_temp_dir
            )
            self.assertEqual(openscap.shutil.rmtree.call_count, 1)
            self.assertEqual(
                response,
                {
                    "upload_dir": self.random_temp_dir,
                    "error": "",
                    "success": True,
                    "returncode": 0,
                },
            )

    def test_new_openscap_xccdf_eval_success_with_failing_rules(self):
        with patch(
            "salt.modules.openscap.Popen",
            MagicMock(
                return_value=Mock(
                    **{"returncode": 2, "communicate.return_value": ("", "some error")}
                )
            ),
        ):
            response = openscap.xccdf_eval(
                self.policy_file,
                profile="Default",
                oval_results=True,
                results="results.xml",
                report="report.html",
            )

            self.assertEqual(openscap.tempfile.mkdtemp.call_count, 1)
            expected_cmd = [
                "oscap",
                "xccdf",
                "eval",
                "--oval-results",
                "--results",
                "results.xml",
                "--report",
                "report.html",
                "--profile",
                "Default",
                self.policy_file,
            ]
            openscap.Popen.assert_called_once_with(
                expected_cmd,
                cwd=openscap.tempfile.mkdtemp.return_value,
                stderr=subprocess.PIPE,
                stdout=subprocess.PIPE,
            )
            openscap.__salt__["cp.push_dir"].assert_called_once_with(
                self.random_temp_dir
            )
            self.assertEqual(openscap.shutil.rmtree.call_count, 1)
            self.assertEqual(
                response,
                {
                    "upload_dir": self.random_temp_dir,
                    "error": "some error",
                    "success": True,
                    "returncode": 2,
                },
            )

    def test_new_openscap_xccdf_eval_success_ignore_unknown_params(self):
        with patch(
            "salt.modules.openscap.Popen",
            MagicMock(
                return_value=Mock(
                    **{"returncode": 2, "communicate.return_value": ("", "some error")}
                )
            ),
        ):
            response = openscap.xccdf_eval(
                "/policy/file",
                param="Default",
                profile="Default",
                oval_results=True,
                results="results.xml",
                report="report.html",
            )

            self.assertEqual(
                response,
                {
                    "upload_dir": self.random_temp_dir,
                    "error": "some error",
                    "success": True,
                    "returncode": 2,
                },
            )
            expected_cmd = [
                "oscap",
                "xccdf",
                "eval",
                "--oval-results",
                "--results",
                "results.xml",
                "--report",
                "report.html",
                "--profile",
                "Default",
                "/policy/file",
            ]
            openscap.Popen.assert_called_once_with(
                expected_cmd,
                cwd=openscap.tempfile.mkdtemp.return_value,
                stderr=subprocess.PIPE,
                stdout=subprocess.PIPE,
            )

    def test_new_openscap_xccdf_eval_evaluation_error(self):
        with patch(
            "salt.modules.openscap.Popen",
            MagicMock(
                return_value=Mock(
                    **{
                        "returncode": 1,
                        "communicate.return_value": ("", "evaluation error"),
                    }
                )
            ),
        ):
            response = openscap.xccdf_eval(
                self.policy_file,
                profile="Default",
                oval_results=True,
                results="results.xml",
                report="report.html",
            )

            self.assertEqual(
                response,
                {
                    "upload_dir": None,
                    "error": "evaluation error",
                    "success": False,
                    "returncode": 1,
                },
            )
