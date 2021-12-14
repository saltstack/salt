import subprocess

import salt.modules.openscap as openscap
from tests.support.mock import MagicMock, Mock, patch
from tests.support.unit import TestCase


class OpenscapTestCase(TestCase):

    random_temp_dir = "/tmp/unique-name"
    policy_file = "/usr/share/openscap/policy-file-xccdf.xml"

    def setUp(self):
        import salt.modules.openscap

        salt.modules.openscap.__salt__ = MagicMock()
        patchers = [
            patch("salt.modules.openscap.__salt__", MagicMock()),
            patch("salt.modules.openscap.shutil.rmtree", Mock()),
            patch(
                "salt.modules.openscap.tempfile.mkdtemp",
                Mock(return_value=self.random_temp_dir),
            ),
        ]
        for patcher in patchers:
            self.apply_patch(patcher)

    def apply_patch(self, patcher):
        patcher.start()
        self.addCleanup(patcher.stop)

    def test_openscap_xccdf_eval_success(self):
        with patch(
            "salt.modules.openscap.Popen",
            MagicMock(
                return_value=Mock(
                    **{"returncode": 0, "communicate.return_value": ("", "")}
                )
            ),
        ):
            response = openscap.xccdf(
                "eval --profile Default {}".format(self.policy_file)
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

    def test_openscap_xccdf_eval_success_with_failing_rules(self):
        with patch(
            "salt.modules.openscap.Popen",
            MagicMock(
                return_value=Mock(
                    **{"returncode": 2, "communicate.return_value": ("", "some error")}
                )
            ),
        ):
            response = openscap.xccdf(
                "eval --profile Default {}".format(self.policy_file)
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

    def test_openscap_xccdf_eval_fail_no_profile(self):
        response = openscap.xccdf("eval --param Default /unknown/param")
        error = "the following arguments are required: --profile"
        self.assertEqual(
            response,
            {"error": error, "upload_dir": None, "success": False, "returncode": None},
        )

    def test_openscap_xccdf_eval_success_ignore_unknown_params(self):
        with patch(
            "salt.modules.openscap.Popen",
            MagicMock(
                return_value=Mock(
                    **{"returncode": 2, "communicate.return_value": ("", "some error")}
                )
            ),
        ):
            response = openscap.xccdf(
                "eval --profile Default --param Default /policy/file"
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

    def test_openscap_xccdf_eval_evaluation_error(self):
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
            response = openscap.xccdf(
                "eval --profile Default {}".format(self.policy_file)
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

    def test_openscap_xccdf_eval_fail_not_implemented_action(self):
        response = openscap.xccdf("info {}".format(self.policy_file))
        mock_err = "argument action: invalid choice: 'info' (choose from 'eval')"

        self.assertEqual(
            response,
            {
                "upload_dir": None,
                "error": mock_err,
                "success": False,
                "returncode": None,
            },
        )
