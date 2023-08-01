import logging
import os

import salt.version

log = logging.getLogger(__name__)


def test_salt_run_exception_exit(salt_run_cli):
    """
    test that the exitcode is 1 when an exception is
    thrown in a salt runner
    """
    ret = salt_run_cli.run(
        "error.error", "name='Exception'", "message='This is an error.'"
    )
    assert ret.returncode == 1


def test_salt_run_non_exception_exit(salt_run_cli):
    """
    Test standard exitcode and output when runner works.
    """
    ret = salt_run_cli.run("test.stdout_print")
    assert ret.returncode == 0
    assert ret.stdout == 'foo\n"bar"\n'


def test_versions_report(salt_run_cli):
    """
    test salt-run --versions-report
    """
    expected = salt.version.versions_information()
    # sanitize expected of unnnecessary whitespace
    for _, section in expected.items():
        for key in section:
            if isinstance(section[key], str):
                section[key] = section[key].strip()

    ret = salt_run_cli.run("--versions-report")
    assert ret.returncode == 0
    assert ret.stdout
    ret_lines = ret.stdout.split("\n")

    assert ret_lines
    # sanitize lines
    ret_lines = [line.strip() for line in ret_lines]

    for header in expected:
        assert f"{header}:" in ret_lines

    ret_dict = {}
    expected_keys = set()
    for line in ret_lines:
        if not line:
            continue
        if line.endswith(":"):
            assert not expected_keys
            current_header = line.rstrip(":")
            assert current_header in expected
            ret_dict[current_header] = {}
            expected_keys = set(expected[current_header].keys())
        else:
            key, *value_list = line.split(":", 1)
            assert value_list
            assert len(value_list) == 1
            value = value_list[0].strip()
            if value == "Not Installed":
                value = None
            ret_dict[current_header][key] = value
            assert key in expected_keys
            expected_keys.remove(key)
    assert not expected_keys
    if os.environ.get("ONEDIR_TESTRUN", "0") == "0":
        # Stop any more testing
        return

    assert "relenv" in ret_dict["Dependency Versions"]
    assert "Salt Extensions" in ret_dict


def test_salt_run_version(salt_run_cli):
    expected = salt.version.__saltstack_version__.formatted_version
    ret = salt_run_cli.run("--version")
    assert f"cli_salt_run.py {expected}\n" == ret.stdout
