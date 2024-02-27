import subprocess

import pytest

import salt.modules.openscap as openscap
from tests.support.mock import MagicMock, Mock, patch


@pytest.fixture
def policy_file():
    yield "/usr/share/openscap/policy-file-xccdf.xml"


@pytest.fixture
def configure_loader_modules(tmp_path):
    return {
        openscap: {
            "__salt__": MagicMock(),
        }
    }


def test_openscap_xccdf_eval_success(policy_file, tmp_path):
    patch_rmtree = patch("shutil.rmtree", Mock())
    mock_mkdtemp = Mock(return_value=str(tmp_path))
    patch_mkdtemp = patch("tempfile.mkdtemp", mock_mkdtemp)
    mock_popen = MagicMock(
        return_value=Mock(**{"returncode": 0, "communicate.return_value": ("", "")})
    )
    patch_popen = patch.object(openscap, "Popen", mock_popen)
    with patch_popen, patch_rmtree, patch_mkdtemp:
        response = openscap.xccdf(f"eval --profile Default {policy_file}")

        assert mock_mkdtemp.call_count == 1
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
        openscap.__salt__["cp.push_dir"].assert_called_once_with(str(tmp_path))
        assert openscap.shutil.rmtree.call_count == 1
        expected = {
            "upload_dir": str(tmp_path),
            "error": "",
            "success": True,
            "returncode": 0,
        }
        assert response == expected


def test_openscap_xccdf_eval_success_with_failing_rules(policy_file, tmp_path):
    patch_rmtree = patch("shutil.rmtree", Mock())
    mock_mkdtemp = Mock(return_value=str(tmp_path))
    patch_mkdtemp = patch("tempfile.mkdtemp", mock_mkdtemp)
    mock_popen = MagicMock(
        return_value=Mock(
            **{"returncode": 2, "communicate.return_value": ("", "some error")}
        )
    )
    patch_popen = patch.object(openscap, "Popen", mock_popen)
    with patch_popen, patch_mkdtemp, patch_rmtree as mock_rmtree:
        response = openscap.xccdf(f"eval --profile Default {policy_file}")

        assert mock_mkdtemp.call_count == 1
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
        openscap.__salt__["cp.push_dir"].assert_called_once_with(str(tmp_path))
        assert mock_rmtree.call_count == 1
        expected = {
            "upload_dir": str(tmp_path),
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


def test_openscap_xccdf_eval_success_ignore_unknown_params(tmp_path):
    mock_mkdtemp = Mock(return_value=str(tmp_path))
    patch_mkdtemp = patch("tempfile.mkdtemp", mock_mkdtemp)
    mock_popen = MagicMock(
        return_value=Mock(
            **{"returncode": 2, "communicate.return_value": ("", "some error")}
        )
    )
    patch_popen = patch("salt.modules.openscap.Popen", mock_popen)
    with patch_popen, patch_mkdtemp:
        response = openscap.xccdf("eval --profile Default --param Default /policy/file")
        expected = {
            "upload_dir": str(tmp_path),
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
        openscap.Popen.assert_called_once_with(
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
    patch_popen = patch("salt.modules.openscap.Popen", mock_popen)
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
    patch_popen = patch("salt.modules.openscap.Popen", mock_popen)
    with patch_popen:
        response = openscap.xccdf(f"eval --profile Default {policy_file}")
        expected = {
            "upload_dir": None,
            "error": "unknown error",
            "success": False,
            "returncode": 255,
        }
        assert response == expected
