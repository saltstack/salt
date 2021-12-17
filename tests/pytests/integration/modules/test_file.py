"""
Tests for the file state
"""
import pytest
import salt.states.file


@pytest.mark.parametrize("verify_ssl", [True, False])
@pytest.mark.slow_test
def test_get_source_sum_verify_ssl_false(
    salt_call_cli, tmpdir, ssl_webserver, verify_ssl
):
    """
    test verify_ssl with get_source_sum
    """
    web_file = ssl_webserver.url("this.txt")
    ret = salt_call_cli.run(
        "--local",
        "file.get_source_sum",
        tmpdir.join("test_source_sum.txt").strpath,
        web_file,
        web_file + ".sha256",
        "verify_ssl={}".format(verify_ssl),
    )
    if not verify_ssl:
        assert (
            ret.json["hsum"]
            == "f2ca1bb6c7e907d06dafe4687e579fce76b37e4e93b7605022da52e6ccc26fd2"
        )
        assert ret.json["hash_type"] == "sha256"
    else:
        assert "SSL: CERTIFICATE_VERIFY_FAILED" in ret.stderr


@pytest.mark.parametrize("verify_ssl", [True, False])
@pytest.mark.slow_test
def test_get_managed_verify_ssl(salt_call_cli, tmpdir, ssl_webserver, verify_ssl):
    """
    test verify_ssl with get_managed
    """
    web_file = ssl_webserver.url("this.txt")
    ret = salt_call_cli.run(
        "--local",
        "file.get_managed",
        tmpdir.join("test_managed.txt").strpath,
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
        assert "this.txt" in ret.json[0]
    else:
        assert "SSL: CERTIFICATE_VERIFY_FAILED" in ret.stdout


@pytest.mark.parametrize("verify_ssl", [True, False])
@pytest.mark.slow_test
def test_manage_file_verify_ssl(salt_call_cli, tmpdir, ssl_webserver, verify_ssl):
    """
    test verify_ssl with manage_file
    """
    test_file = tmpdir.join("test_manage_file.txt").strpath
    ret = salt_call_cli.run(
        "--local",
        "file.manage_file",
        test_file,
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
        assert ret.json["changes"] == {"diff": "New file", "mode": "0000"}
        assert ret.json["comment"] == "File {} updated".format(test_file)
    else:
        assert "SSL: CERTIFICATE_VERIFY_FAILED" in ret.stderr


@pytest.mark.parametrize("verify_ssl", [True, False])
@pytest.mark.slow_test
def test_check_managed_changes_verify_ssl(
    salt_call_cli, tmpdir, ssl_webserver, verify_ssl
):
    """
    test verify_ssl with check_managed_changes
    """
    test_file = tmpdir.join("test_managed_changes.txt").strpath
    web_url = ssl_webserver.url("this.txt")
    ret = salt_call_cli.run(
        "--local",
        "file.check_managed_changes",
        test_file,
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
        assert ret.json["newfile"] == test_file
    else:
        assert "SSL: CERTIFICATE_VERIFY_FAILED" in ret.stderr


@pytest.mark.parametrize("verify_ssl", [True, False])
@pytest.mark.slow_test
def test_check_file_meta_verify_ssl(salt_call_cli, tmpdir, ssl_webserver, verify_ssl):
    """
    test verify_ssl with check_file_meta
    """
    test_file = tmpdir.join("test_check_file_meta.txt").strpath
    with salt.utils.files.fopen(test_file, "w") as fh_:
        fh_.write("test check_file_meta")
    web_url = ssl_webserver.url("this.txt")
    ret = salt_call_cli.run(
        "--local",
        "file.check_file_meta",
        test_file,
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
            len([x for x in ["diff", "user", "group", "mode"] if x in ret.json.keys()])
            == 4
        )
    else:
        assert "SSL: CERTIFICATE_VERIFY_FAILED" in ret.stderr
