import subprocess

import pytest

import salt.modules.openscap as openscap
from tests.support.mock import MagicMock, Mock, patch

policy_file = "/usr/share/openscap/policy-file-xccdf.xml"


@pytest.fixture
def random_temp_dir(tmp_path):
    tmp_dir = tmp_path / "unique"
    tmp_dir.mkdir()
    return str(tmp_dir)


@pytest.fixture
def configure_loader_modules(random_temp_dir):
    with patch("salt.modules.openscap.shutil.rmtree", Mock()), patch(
        "salt.modules.openscap.tempfile.mkdtemp",
        Mock(return_value=random_temp_dir),
    ), patch("salt.modules.openscap.os.path.exists", Mock(return_value=True)):
        yield {openscap: {"__salt__": {"cp.push_dir": MagicMock()}}}


def test_openscap_xccdf_eval_success(random_temp_dir):
    with patch(
        "salt.modules.openscap.Popen",
        MagicMock(
            return_value=Mock(**{"returncode": 0, "communicate.return_value": ("", "")})
        ),
    ):
        response = openscap.xccdf(f"eval --profile Default {policy_file}")

        assert openscap.tempfile.mkdtemp.call_count == 1
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
            policy_file,
        ]
        openscap.Popen.assert_called_once_with(
            expected_cmd,
            cwd=openscap.tempfile.mkdtemp.return_value,
            stderr=subprocess.PIPE,
            stdout=subprocess.PIPE,
        )
        openscap.__salt__["cp.push_dir"].assert_called_once_with(random_temp_dir)
        assert openscap.shutil.rmtree.call_count == 1
        assert response == {
            "upload_dir": random_temp_dir,
            "error": "",
            "success": True,
            "returncode": 0,
        }


def test_openscap_xccdf_eval_success_with_failing_rules(random_temp_dir):
    with patch(
        "salt.modules.openscap.Popen",
        MagicMock(
            return_value=Mock(
                **{"returncode": 2, "communicate.return_value": ("", "some error")}
            )
        ),
    ):
        response = openscap.xccdf(f"eval --profile Default {policy_file}")

        assert openscap.tempfile.mkdtemp.call_count == 1
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
            policy_file,
        ]
        openscap.Popen.assert_called_once_with(
            expected_cmd,
            cwd=openscap.tempfile.mkdtemp.return_value,
            stderr=subprocess.PIPE,
            stdout=subprocess.PIPE,
        )
        openscap.__salt__["cp.push_dir"].assert_called_once_with(random_temp_dir)
        assert openscap.shutil.rmtree.call_count == 1
        assert response == {
            "upload_dir": random_temp_dir,
            "error": "some error",
            "success": True,
            "returncode": 2,
        }


def test_openscap_xccdf_eval_fail_no_profile():
    response = openscap.xccdf("eval --param Default /unknown/param")
    error = "the following arguments are required: --profile"
    assert response == {
        "error": error,
        "upload_dir": None,
        "success": False,
        "returncode": None,
    }


def test_openscap_xccdf_eval_success_ignore_unknown_params(random_temp_dir):
    with patch(
        "salt.modules.openscap.Popen",
        MagicMock(
            return_value=Mock(
                **{"returncode": 2, "communicate.return_value": ("", "some error")}
            )
        ),
    ):
        response = openscap.xccdf("eval --profile Default --param Default /policy/file")
        assert response == {
            "upload_dir": random_temp_dir,
            "error": "some error",
            "success": True,
            "returncode": 2,
        }
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


def test_openscap_xccdf_eval_evaluation_error():
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
        response = openscap.xccdf(f"eval --profile Default {policy_file}")

        assert response == {
            "upload_dir": None,
            "error": "evaluation error",
            "success": False,
            "returncode": 1,
        }


def test_openscap_xccdf_eval_fail_not_implemented_action():
    response = openscap.xccdf(f"info {policy_file}")
    mock_err = "argument action: invalid choice: 'info' (choose from 'eval')"

    assert response == {
        "upload_dir": None,
        "error": mock_err,
        "success": False,
        "returncode": None,
    }


def test_new_openscap_xccdf_eval_success(random_temp_dir):
    with patch(
        "salt.modules.openscap.Popen",
        MagicMock(
            return_value=Mock(**{"returncode": 0, "communicate.return_value": ("", "")})
        ),
    ):
        response = openscap.xccdf_eval(
            policy_file,
            profile="Default",
            oval_results=True,
            results="results.xml",
            report="report.html",
        )

        assert openscap.tempfile.mkdtemp.call_count == 1
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
            policy_file,
        ]
        openscap.Popen.assert_called_once_with(
            expected_cmd,
            cwd=openscap.tempfile.mkdtemp.return_value,
            stderr=subprocess.PIPE,
            stdout=subprocess.PIPE,
        )
        openscap.__salt__["cp.push_dir"].assert_called_once_with(random_temp_dir)
        assert openscap.shutil.rmtree.call_count == 1
        assert response == {
            "upload_dir": random_temp_dir,
            "error": "",
            "success": True,
            "returncode": 0,
        }


def test_new_openscap_xccdf_eval_success_with_extra_ovalfiles(random_temp_dir):
    with patch(
        "salt.modules.openscap.Popen",
        MagicMock(
            return_value=Mock(**{"returncode": 0, "communicate.return_value": ("", "")})
        ),
    ):
        response = openscap.xccdf_eval(
            policy_file,
            ["/usr/share/xml/another-oval.xml", "/usr/share/xml/oval.xml"],
            profile="Default",
            oval_results=True,
            results="results.xml",
            report="report.html",
        )

        assert openscap.tempfile.mkdtemp.call_count == 1
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
            policy_file,
            "/usr/share/xml/another-oval.xml",
            "/usr/share/xml/oval.xml",
        ]
        openscap.Popen.assert_called_once_with(
            expected_cmd,
            cwd=openscap.tempfile.mkdtemp.return_value,
            stderr=subprocess.PIPE,
            stdout=subprocess.PIPE,
        )
        openscap.__salt__["cp.push_dir"].assert_called_once_with(random_temp_dir)
        assert openscap.shutil.rmtree.call_count == 1
        assert response == {
            "upload_dir": random_temp_dir,
            "error": "",
            "success": True,
            "returncode": 0,
        }


def test_new_openscap_xccdf_eval_success_with_failing_rules(random_temp_dir):
    with patch(
        "salt.modules.openscap.Popen",
        MagicMock(
            return_value=Mock(
                **{"returncode": 2, "communicate.return_value": ("", "some error")}
            )
        ),
    ):
        response = openscap.xccdf_eval(
            policy_file,
            profile="Default",
            oval_results=True,
            results="results.xml",
            report="report.html",
        )

        assert openscap.tempfile.mkdtemp.call_count == 1
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
            policy_file,
        ]
        openscap.Popen.assert_called_once_with(
            expected_cmd,
            cwd=openscap.tempfile.mkdtemp.return_value,
            stderr=subprocess.PIPE,
            stdout=subprocess.PIPE,
        )
        openscap.__salt__["cp.push_dir"].assert_called_once_with(random_temp_dir)
        assert openscap.shutil.rmtree.call_count == 1
        assert response == {
            "upload_dir": random_temp_dir,
            "error": "some error",
            "success": True,
            "returncode": 2,
        }


def test_new_openscap_xccdf_eval_evaluation_error():
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
            policy_file,
            profile="Default",
            oval_results=True,
            results="results.xml",
            report="report.html",
        )

        assert response == {
            "upload_dir": None,
            "error": "evaluation error",
            "success": False,
            "returncode": 1,
        }
