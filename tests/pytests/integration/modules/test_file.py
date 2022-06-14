"""
Tests for the file state
"""
import pytest


@pytest.mark.parametrize("verify_ssl", [True, False])
@pytest.mark.slow_test
def test_get_source_sum_verify_ssl_false(
    salt_call_cli, tmp_path, ssl_webserver, verify_ssl
):
    """
    test verify_ssl with get_source_sum
    """
    web_file = ssl_webserver.url("this.txt")
    ret = salt_call_cli.run(
        "--local",
        "file.get_source_sum",
        str(tmp_path / "test_source_sum.txt"),
        web_file,
        web_file + ".sha256",
        "verify_ssl={}".format(verify_ssl),
    )
    if not verify_ssl:
        assert (
            ret.data["hsum"]
            == "f2ca1bb6c7e907d06dafe4687e579fce76b37e4e93b7605022da52e6ccc26fd2"
        )
        assert ret.data["hash_type"] == "sha256"
    else:
        assert "SSL: CERTIFICATE_VERIFY_FAILED" in ret.stderr


@pytest.mark.parametrize("verify_ssl", [True, False])
@pytest.mark.slow_test
def test_get_managed_verify_ssl(salt_call_cli, tmp_path, ssl_webserver, verify_ssl):
    """
    test verify_ssl with get_managed
    """
    web_file = ssl_webserver.url("this.txt")
    ret = salt_call_cli.run(
        "--local",
        "file.get_managed",
        str(tmp_path / "test_managed.txt"),
        "",
        web_file,
        web_file + ".sha256",
        "",
        "",
        "",
        "",
        "",
        "base",
        "{}",
        "",
        "True",
        "verify_ssl={}".format(verify_ssl),
    )
    if not verify_ssl:
        assert "this.txt" in ret.data[0]
    else:
        assert "SSL: CERTIFICATE_VERIFY_FAILED" in ret.stdout


@pytest.mark.parametrize("verify_ssl", [True, False])
@pytest.mark.slow_test
def test_manage_file_verify_ssl(salt_call_cli, tmp_path, ssl_webserver, verify_ssl):
    """
    test verify_ssl with manage_file
    """
    test_file = tmp_path / "test_manage_file.txt"
    ret = salt_call_cli.run(
        "--local",
        "file.manage_file",
        str(test_file),
        "",
        "",
        ssl_webserver.url("this.txt"),
        "{hash_type: 'sha256', 'hsum':"
        " 'f2ca1bb6c7e907d06dafe4687e579fce76b37e4e93b7605022da52e6ccc26fd2'}",
        "",
        "",
        "",
        "",
        "base",
        "",
        "verify_ssl={}".format(verify_ssl),
    )
    if not verify_ssl:
        assert ret.data["changes"] == {"diff": "New file", "mode": "0000"}
        assert ret.data["comment"] == "File {} updated".format(test_file)
    else:
        assert "SSL: CERTIFICATE_VERIFY_FAILED" in ret.stderr


@pytest.mark.parametrize("verify_ssl", [True, False])
@pytest.mark.slow_test
def test_check_managed_changes_verify_ssl(
    salt_call_cli, tmp_path, ssl_webserver, verify_ssl
):
    """
    test verify_ssl with check_managed_changes
    """
    test_file = tmp_path / "test_managed_changes.txt"
    web_url = ssl_webserver.url("this.txt")
    ret = salt_call_cli.run(
        "--local",
        "file.check_managed_changes",
        str(test_file),
        web_url,
        web_url + ".sha256",
        "",
        "",
        "",
        "",
        "",
        "jinja",
        "",
        "",
        "base",
        "verify_ssl={}".format(verify_ssl),
    )

    if not verify_ssl:
        assert ret.data["newfile"] == str(test_file)
    else:
        assert "SSL: CERTIFICATE_VERIFY_FAILED" in ret.stderr


@pytest.mark.parametrize("verify_ssl", [True, False])
@pytest.mark.slow_test
def test_check_file_meta_verify_ssl(salt_call_cli, tmp_path, ssl_webserver, verify_ssl):
    """
    test verify_ssl with check_file_meta
    """
    test_file = tmp_path / "test_check_file_meta.txt"
    test_file.write_text("test check_file_meta")
    web_url = ssl_webserver.url("this.txt")
    ret = salt_call_cli.run(
        "--local",
        "file.check_file_meta",
        str(test_file),
        "",
        web_url,
        "{hash_type: 'sha256', 'hsum':"
        " 'f2ca1bb6c7e907d06dafe4687e579fce76b37e4e93b7605022da52e6ccc26fd2'}",
        "",
        "",
        "",
        "",
        "base",
        "verify_ssl={}".format(verify_ssl),
    )

    if not verify_ssl:
        assert (
            len([x for x in ["diff", "user", "group", "mode"] if x in ret.data.keys()])
            == 4
        )
    else:
        assert "SSL: CERTIFICATE_VERIFY_FAILED" in ret.stderr
