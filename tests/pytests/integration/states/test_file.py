"""
Tests for the file state
"""

import pytest
from tests.support.helpers import slowTest


@slowTest
def test_verify_ssl_skip_verify_false(
    salt_call_cli, tmpdir, integration_files_dir, ssl_webserver
):
    """
    test verify_ssl when its False and True when managing
    a file with an https source and skip_verify is false.
    """
    web_file = ssl_webserver.url("this.txt")
    true_content = """
    test_verify_ssl:
      file.managed:
        - name: {}
        - source: {}
        - source_hash: {}
    """.format(
        tmpdir.join("test_verify_ssl_true.txt"), web_file, web_file + ".sha256"
    )

    false_content = true_content + "    - verify_ssl: False"

    # test when verify_ssl is True
    with pytest.helpers.temp_state_file("verify_ssl.sls", true_content) as sfpath:
        ret = salt_call_cli.run("--local", "state.apply", "verify_ssl")
        assert ret.exitcode == 1
        assert (
            "SSL: CERTIFICATE_VERIFY_FAILED"
            in ret.json[next(iter(ret.json))]["comment"]
        )

    # test when verify_ssl is False
    with pytest.helpers.temp_state_file("verify_ssl.sls", false_content) as sfpath:
        ret = salt_call_cli.run("--local", "state.apply", "verify_ssl")
        assert ret.exitcode == 0
        assert ret.json[next(iter(ret.json))]["changes"] == {
            "diff": "New file",
            "mode": "0644",
        }
