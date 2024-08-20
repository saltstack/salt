"""
Tests for the file state
"""

import os

import pytest


@pytest.mark.parametrize("verify_ssl", [True, False])
@pytest.mark.slow_test
def test_get_source_sum_verify_ssl_false(
    salt_call_cli, tmp_path, ssl_webserver, verify_ssl, this_txt_file
):
    """
    test verify_ssl with get_source_sum
    """
    web_file = ssl_webserver.url("this.txt")
    if verify_ssl:
        # Clean the cached this.txt if it exists as it will fail the test
        # because it won't fetch it again
        ret = salt_call_cli.run("cp.is_cached", web_file, saltenv="base")
        assert ret.returncode == 0
        if ret.data:
            os.unlink(ret.data)
    ret = salt_call_cli.run(
        "--local",
        "file.get_source_sum",
        str(tmp_path / "test_source_sum.txt"),
        source=web_file,
        source_hash=web_file + ".sha256",
        verify_ssl=verify_ssl,
    )
    if not verify_ssl:
        assert ret.data["hsum"] == this_txt_file.sha256
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
    if verify_ssl:
        # Clean the cached this.txt if it exists as it will fail the test
        # because it won't fetch it again
        ret = salt_call_cli.run("cp.is_cached", web_file, saltenv="base")
        assert ret.returncode == 0
        if ret.data:
            os.unlink(ret.data)
    ret = salt_call_cli.run(
        "--local",
        "file.get_managed",
        str(tmp_path / "test_managed.txt"),
        template="",
        source=web_file,
        source_hash=web_file + ".sha256",
        source_hash_name="",
        user="",
        group="",
        mode="",
        attrs="",
        saltenv="base",
        context={},
        defaults="",
        skip_verify=True,
        verify_ssl=verify_ssl,
    )
    if not verify_ssl:
        assert "this.txt" in ret.data[0]
    else:
        assert "SSL: CERTIFICATE_VERIFY_FAILED" in ret.stdout


@pytest.mark.parametrize("verify_ssl", [True, False])
@pytest.mark.slow_test
def test_manage_file_verify_ssl(
    salt_call_cli, tmp_path, ssl_webserver, verify_ssl, this_txt_file
):
    """
    test verify_ssl with manage_file
    """
    test_file = tmp_path / "test_manage_file.txt"
    web_file = ssl_webserver.url("this.txt")
    if verify_ssl:
        # Clean the cached this.txt if it exists as it will fail the test
        # because it won't fetch it again
        ret = salt_call_cli.run("cp.is_cached", web_file, saltenv="base")
        assert ret.returncode == 0
        if ret.data:
            os.unlink(ret.data)
    ret = salt_call_cli.run(
        "--local",
        "file.manage_file",
        str(test_file),
        sfn="",
        ret="",
        source=web_file,
        source_sum={"hash_type": "sha256", "hsum": this_txt_file.sha256},
        user="",
        group="",
        mode="",
        attrs="",
        saltenv="base",
        backup="",
        verify_ssl=verify_ssl,
    )
    if not verify_ssl:
        assert ret.data["changes"] == {"diff": "New file", "mode": "0000"}
        assert ret.data["comment"] == f"File {test_file} updated"
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
    if verify_ssl:
        # Clean the cached this.txt if it exists as it will fail the test
        # because it won't fetch it again
        ret = salt_call_cli.run("cp.is_cached", web_url, saltenv="base")
        assert ret.returncode == 0
        if ret.data:
            os.unlink(ret.data)
    ret = salt_call_cli.run(
        "--local",
        "file.check_managed_changes",
        str(test_file),
        source=web_url,
        source_hash=web_url + ".sha256",
        source_hash_name="",
        user="",
        group="",
        mode="",
        attrs="",
        template="jinja",
        context="",
        defaults="",
        saltenv="base",
        verify_ssl=verify_ssl,
    )

    if not verify_ssl:
        assert ret.data["newfile"] == str(test_file)
    else:
        assert "SSL: CERTIFICATE_VERIFY_FAILED" in ret.stderr


@pytest.mark.parametrize("verify_ssl", [True, False])
@pytest.mark.slow_test
def test_check_file_meta_verify_ssl(
    salt_call_cli, tmp_path, ssl_webserver, verify_ssl, this_txt_file
):
    """
    test verify_ssl with check_file_meta
    """
    test_file = tmp_path / "test_check_file_meta.txt"
    test_file.write_text("test check_file_meta")
    web_url = ssl_webserver.url("this.txt")
    if verify_ssl:
        # Clean the cached this.txt if it exists as it will fail the test
        # because it won't fetch it again
        ret = salt_call_cli.run("cp.is_cached", web_url, saltenv="base")
        assert ret.returncode == 0
        if ret.data:
            os.unlink(ret.data)
    ret = salt_call_cli.run(
        "--local",
        "file.check_file_meta",
        str(test_file),
        sfn="",
        source=web_url,
        source_sum={"hash_type": "sha256", "hsum": this_txt_file.sha256},
        user="",
        mode="",
        group="",
        attrs="",
        saltenv="base",
        verify_ssl=verify_ssl,
    )

    if not verify_ssl:
        assert (
            len([x for x in ["diff", "user", "group", "mode"] if x in ret.data.keys()])
            == 4
        )
    else:
        assert "SSL: CERTIFICATE_VERIFY_FAILED" in ret.stderr
