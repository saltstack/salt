import subprocess

import pytest

import salt.modules.openscap as openscap
from tests.support.mock import MagicMock, Mock, patch


@pytest.fixture
def policy_file():
    yield "/usr/share/openscap/policy-file-xccdf.xml"


@pytest.fixture
def configure_loader_modules(tmp_path):
    random_temp_dir = tmp_path / "unique"
    random_temp_dir.mkdir()
    with patch("salt.modules.openscap.shutil.rmtree", Mock()), patch(
        "salt.modules.openscap.tempfile.mkdtemp",
        Mock(return_value=str(random_temp_dir)),
    ), patch("salt.modules.openscap.os.path.exists", Mock(return_value=True)):
        yield {openscap: {"__salt__": {"cp.push_dir": MagicMock()}}}


def test_openscap_xccdf_eval_success(policy_file):
    mock_popen = MagicMock(
        return_value=Mock(**{"returncode": 0, "communicate.return_value": ("", "")})
    )
    patch_popen = patch("salt.modules.openscap.subprocess.Popen", mock_popen)
    with patch_popen:
        response = openscap.xccdf(f"eval --profile Default {policy_file}")

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
        openscap.subprocess.Popen.assert_called_once_with(
            expected_cmd,
            cwd=openscap.tempfile.mkdtemp.return_value,
            stderr=subprocess.PIPE,
            stdout=subprocess.PIPE,
        )
        openscap.__salt__["cp.push_dir"].assert_called_once_with(
            openscap.tempfile.mkdtemp.return_value
        )
        assert openscap.shutil.rmtree.call_count == 1
        expected = {
            "upload_dir": openscap.tempfile.mkdtemp.return_value,
            "error": "",
            "success": True,
            "returncode": 0,
        }
        assert response == expected


def test_openscap_xccdf_eval_success_with_failing_rules(policy_file):
    mock_popen = MagicMock(
        return_value=Mock(
            **{"returncode": 2, "communicate.return_value": ("", "some error")}
        )
    )
    patch_popen = patch("salt.modules.openscap.subprocess.Popen", mock_popen)
    with patch_popen:
        response = openscap.xccdf(f"eval --profile Default {policy_file}")

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
        openscap.subprocess.Popen.assert_called_once_with(
            expected_cmd,
            cwd=openscap.tempfile.mkdtemp.return_value,
            stderr=subprocess.PIPE,
            stdout=subprocess.PIPE,
        )
        openscap.__salt__["cp.push_dir"].assert_called_once_with(
            openscap.tempfile.mkdtemp.return_value
        )
        expected = {
            "upload_dir": openscap.tempfile.mkdtemp.return_value,
            "error": "some error",
            "success": True,
            "returncode": 2,
        }
        assert response == expected


def test_openscap_xccdf_eval_fail_no_profile():
    response = openscap.xccdf("eval --param Default /unknown/param")
    error = "the following arguments are required: --profile"
    expected = {
        "error": error,
        "upload_dir": None,
        "success": False,
        "returncode": None,
    }
    assert response == expected


def test_openscap_xccdf_eval_success_ignore_unknown_params():
    mock_popen = MagicMock(
        return_value=Mock(
            **{"returncode": 2, "communicate.return_value": ("", "some error")}
        )
    )
    patch_popen = patch("salt.modules.openscap.subprocess.Popen", mock_popen)
    with patch_popen:
        response = openscap.xccdf("eval --profile Default --param Default /policy/file")
        expected = {
            "upload_dir": openscap.tempfile.mkdtemp.return_value,
            "error": "some error",
            "success": True,
            "returncode": 2,
        }
        assert response == expected
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
        openscap.subprocess.Popen.assert_called_once_with(
            expected_cmd,
            cwd=openscap.tempfile.mkdtemp.return_value,
            stderr=subprocess.PIPE,
            stdout=subprocess.PIPE,
        )


def test_openscap_xccdf_eval_evaluation_error(policy_file):
    mock_popen = MagicMock(
        return_value=Mock(
            **{
                "returncode": 1,
                "communicate.return_value": ("", "evaluation error"),
            }
        )
    )
    patch_popen = patch("salt.modules.openscap.subprocess.Popen", mock_popen)
    with patch_popen:
        response = openscap.xccdf(f"eval --profile Default {policy_file}")
        expected = {
            "upload_dir": None,
            "error": "evaluation error",
            "success": False,
            "returncode": 1,
        }
        assert response == expected


def test_openscap_xccdf_eval_fail_not_implemented_action(policy_file):
    response = openscap.xccdf(f"info {policy_file}")
    mock_err = "argument action: invalid choice: 'info' (choose from 'eval')"
    expected = {
        "upload_dir": None,
        "error": mock_err,
        "success": False,
        "returncode": None,
    }
    assert response == expected


def test_openscap_xccdf_eval_evaluation_unknown_error(policy_file):
    mock_popen = MagicMock(
        return_value=Mock(
            **{
                "returncode": 255,
                "communicate.return_value": ("", "unknown error"),
            }
        )
    )
    patch_popen = patch("salt.modules.openscap.subprocess.Popen", mock_popen)
    with patch_popen:
        response = openscap.xccdf(f"eval --profile Default {policy_file}")
        expected = {
            "upload_dir": None,
            "error": "unknown error",
            "success": False,
            "returncode": 255,
        }
        assert response == expected


def test_new_openscap_xccdf_eval_success(policy_file):
    with patch(
        "salt.modules.openscap.subprocess.Popen",
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
        openscap.subprocess.Popen.assert_called_once_with(
            expected_cmd,
            cwd=openscap.tempfile.mkdtemp.return_value,
            stderr=subprocess.PIPE,
            stdout=subprocess.PIPE,
        )
        openscap.__salt__["cp.push_dir"].assert_called_once_with(
            openscap.tempfile.mkdtemp.return_value
        )
        assert openscap.shutil.rmtree.call_count == 1
        assert response == {
            "upload_dir": openscap.tempfile.mkdtemp.return_value,
            "error": "",
            "success": True,
            "returncode": 0,
        }


def test_new_openscap_xccdf_eval_success_with_extra_ovalfiles(policy_file):
    with patch(
        "salt.modules.openscap.subprocess.Popen",
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
        openscap.subprocess.Popen.assert_called_once_with(
            expected_cmd,
            cwd=openscap.tempfile.mkdtemp.return_value,
            stderr=subprocess.PIPE,
            stdout=subprocess.PIPE,
        )
        openscap.__salt__["cp.push_dir"].assert_called_once_with(
            openscap.tempfile.mkdtemp.return_value
        )
        assert openscap.shutil.rmtree.call_count == 1
        assert response == {
            "upload_dir": openscap.tempfile.mkdtemp.return_value,
            "error": "",
            "success": True,
            "returncode": 0,
        }


def test_new_openscap_xccdf_eval_success_with_failing_rules(policy_file):
    with patch(
        "salt.modules.openscap.subprocess.Popen",
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
        openscap.subprocess.Popen.assert_called_once_with(
            expected_cmd,
            cwd=openscap.tempfile.mkdtemp.return_value,
            stderr=subprocess.PIPE,
            stdout=subprocess.PIPE,
        )
        openscap.__salt__["cp.push_dir"].assert_called_once_with(
            openscap.tempfile.mkdtemp.return_value
        )
        assert openscap.shutil.rmtree.call_count == 1
        assert response == {
            "upload_dir": openscap.tempfile.mkdtemp.return_value,
            "error": "some error",
            "success": True,
            "returncode": 2,
        }


def test_new_openscap_xccdf_eval_evaluation_error(policy_file):
    with patch(
        "salt.modules.openscap.subprocess.Popen",
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
