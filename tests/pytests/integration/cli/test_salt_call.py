"""
    :codeauthor: Pedro Algarvio (pedro@algarvio.me)


    tests.integration.shell.call
    ~~~~~~~~~~~~~~~~~~~~~~~~~~~~
"""

import copy
import logging
import os
import pprint
import re
import shutil
import sys

import pytest
import salt.utils.files
import salt.utils.json
import salt.utils.platform
import salt.utils.yaml
from tests.support.helpers import PRE_PYTEST_SKIP, PRE_PYTEST_SKIP_REASON, slowTest
from tests.support.runtests import RUNTIME_VARS

log = logging.getLogger(__name__)
pytestmark = pytest.mark.windows_whitelisted


@slowTest
def test_fib(salt_call_cli):
    ret = salt_call_cli.run("test.fib", "3")
    assert ret.exitcode == 0
    assert ret.json[0] == 2


@slowTest
def test_fib_txt_output(salt_call_cli):
    ret = salt_call_cli.run("--output=txt", "test.fib", "3")
    assert ret.exitcode == 0
    assert ret.json is None
    assert (
        re.match(r"local: \(2, [0-9]{1}\.(([0-9]+)(e-([0-9]+))?)\)\s", ret.stdout)
        is not None
    )


@slowTest
@pytest.mark.parametrize("indent", [-1, 0, 1])
def test_json_out_indent(salt_call_cli, indent):
    ret = salt_call_cli.run("--out=json", "--out-indent={}".format(indent), "test.ping")
    assert ret.exitcode == 0
    assert ret.json is True
    if indent == -1:
        expected_output = '{"local": true}\n'
    elif indent == 0:
        expected_output = '{\n"local": true\n}\n'
    else:
        expected_output = '{\n "local": true\n}\n'
    stdout = ret.stdout
    assert ret.stdout == expected_output


@slowTest
def test_local_sls_call(salt_call_cli):
    fileroot = os.path.join(RUNTIME_VARS.FILES, "file", "base")
    ret = salt_call_cli.run(
        "--local", "--file-root", fileroot, "state.sls", "saltcalllocal"
    )
    assert ret.exitcode == 0
    state_run_dict = next(iter(ret.json.values()))
    assert state_run_dict["name"] == "test.echo"
    assert state_run_dict["result"] is True
    assert state_run_dict["changes"]["ret"] == "hello"


@slowTest
def test_local_salt_call(salt_call_cli):
    """
    This tests to make sure that salt-call does not execute the
    function twice, see https://github.com/saltstack/salt/pull/49552
    """
    with pytest.helpers.temp_file() as filename:

        ret = salt_call_cli.run(
            "--local", "state.single", "file.append", name=filename, text="foo"
        )
        assert ret.exitcode == 0

        state_run_dict = next(iter(ret.json.values()))
        assert state_run_dict["changes"]

        # 2nd sanity check: make sure that "foo" only exists once in the file
        with salt.utils.files.fopen(filename) as fp_:
            contents = fp_.read()
        assert contents.count("foo") == 1, contents


@slowTest
@pytest.mark.skip_on_windows(reason=PRE_PYTEST_SKIP_REASON)
def test_user_delete_kw_output(salt_call_cli):
    ret = salt_call_cli.run("-d", "user.delete", _timeout=120)
    assert ret.exitcode == 0
    expected_output = "salt '*' user.delete name"
    if not salt.utils.platform.is_windows():
        expected_output += " remove=True force=True"
    assert expected_output in ret.stdout


@slowTest
def test_salt_documentation_too_many_arguments(salt_call_cli):
    """
    Test to see if passing additional arguments shows an error
    """
    ret = salt_call_cli.run("-d", "virtualenv.create", "/tmp/ve")
    assert ret.exitcode != 0
    assert "You can only get documentation for one method at one time" in ret.stderr


@slowTest
def test_issue_6973_state_highstate_exit_code(salt_call_cli):
    """
    If there is no tops/master_tops or state file matches
    for this minion, salt-call should exit non-zero if invoked with
    option --retcode-passthrough
    """
    src = os.path.join(RUNTIME_VARS.BASE_FILES, "top.sls")
    dst = os.path.join(RUNTIME_VARS.BASE_FILES, "top.sls.bak")
    shutil.move(src, dst)
    expected_comment = "No states found for this minion"
    try:
        ret = salt_call_cli.run("--retcode-passthrough", "state.highstate")
    finally:
        shutil.move(dst, src)
    assert ret.exitcode != 0
    assert expected_comment in ret.stdout


@slowTest
@PRE_PYTEST_SKIP
def test_issue_15074_output_file_append(salt_call_cli):

    with pytest.helpers.temp_file(name="issue-15074") as output_file_append:
        ret = salt_call_cli.run("--output-file", output_file_append, "test.versions")
        assert ret.exitcode == 0

        with salt.utils.files.fopen(output_file_append) as ofa:
            first_run_output = ofa.read()

        assert first_run_output

        ret = salt_call_cli.run(
            "--output-file",
            output_file_append,
            "--output-file-append",
            "test.versions",
        )
        assert ret.exitcode == 0

        with salt.utils.files.fopen(output_file_append) as ofa:
            second_run_output = ofa.read()

        assert second_run_output

        assert second_run_output == first_run_output + first_run_output


@slowTest
@PRE_PYTEST_SKIP
def test_issue_14979_output_file_permissions(salt_call_cli):
    with pytest.helpers.temp_file(name="issue-14979") as output_file:
        with salt.utils.files.set_umask(0o077):
            # Let's create an initial output file with some data
            ret = salt_call_cli.run("--output-file", output_file, "--grains")
            assert ret.exitcode == 0
            try:
                stat1 = os.stat(output_file)
            except OSError:
                pytest.fail("Failed to generate output file {}".format(output_file))

            # Let's change umask
            os.umask(0o777)  # pylint: disable=blacklisted-function

            ret = salt_call_cli.run(
                "--output-file", output_file, "--output-file-append", "--grains"
            )
            assert ret.exitcode == 0
            stat2 = os.stat(output_file)
            assert stat1.st_mode == stat2.st_mode
            # Data was appeneded to file
            assert stat1.st_size < stat2.st_size

            # Let's remove the output file
            os.unlink(output_file)

            # Not appending data
            ret = salt_call_cli.run("--output-file", output_file, "--grains")
            assert ret.exitcode == 0
            try:
                stat3 = os.stat(output_file)
            except OSError:
                pytest.fail("Failed to generate output file {}".format(output_file))
            # Mode must have changed since we're creating a new log file
            assert stat1.st_mode != stat3.st_mode


@slowTest
@pytest.mark.skip_on_windows(reason="This test does not apply on Win")
def test_42116_cli_pillar_override(salt_call_cli):
    ret = salt_call_cli.run(
        "state.apply",
        "issue-42116-cli-pillar-override",
        pillar={"myhost": "localhost"},
    )
    state_run_dict = next(iter(ret.json.values()))
    assert state_run_dict["changes"]
    assert (
        state_run_dict["comment"] == 'Command "ping -c 2 localhost" run'
    ), "CLI pillar override not found in pillar data. State Run Dictionary:\n{}".format(
        pprint.pformat(state_run_dict)
    )


@slowTest
def test_pillar_items_masterless(salt_minion, salt_call_cli):
    """
    Test to ensure we get expected output
    from pillar.items with salt-call
    """
    TOP = """
    base:
      '{}':
        - generic
    """.format(
        salt_minion.id
    )
    with pytest.helpers.temp_pillar_file("top.sls", TOP):
        ret = salt_call_cli.run("--local", "pillar.items")
        assert ret.exitcode == 0
        assert "knights" in ret.json
        assert sorted(ret.json["knights"]) == sorted(
            ["Lancelot", "Galahad", "Bedevere", "Robin"]
        )
        assert "monty" in ret.json
        assert ret.json["monty"] == "python"


@slowTest
def test_masterless_highstate(salt_call_cli):
    """
    test state.highstate in masterless mode
    """
    destpath = os.path.join(RUNTIME_VARS.TMP, "testfile")
    ret = salt_call_cli.run("--local", "state.highstate")
    assert ret.exitcode == 0
    state_run_dict = next(iter(ret.json.values()))
    assert state_run_dict["result"] is True
    assert state_run_dict["__id__"] == destpath


@slowTest
@pytest.mark.skip_on_windows
def test_syslog_file_not_found(salt_minion, salt_call_cli):
    """
    test when log_file is set to a syslog file that does not exist
    """
    old_cwd = os.getcwd()
    with pytest.helpers.temp_directory("log_file_incorrect") as config_dir:

        try:
            os.chdir(config_dir)
            minion_config = copy.deepcopy(salt_minion.config)
            minion_config["log_file"] = "file:///dev/doesnotexist"
            with salt.utils.files.fopen(os.path.join(config_dir, "minion"), "w") as fh_:
                fh_.write(salt.utils.yaml.dump(minion_config, default_flow_style=False))
            ret = salt_call_cli.run(
                "--config-dir", config_dir, "--log-level=debug", "cmd.run", "echo foo",
            )
            if sys.version_info >= (3, 5, 4):
                assert ret.exitcode == 0
                assert (
                    "[WARNING ] The log_file does not exist. Logging not setup correctly or syslog service not started."
                    in ret.stderr
                )
                assert ret.json == "foo", ret
            else:
                assert ret.exitcode == 2
                assert "Failed to setup the Syslog logging handler" in ret.stderr
        finally:
            os.chdir(old_cwd)


@slowTest
@PRE_PYTEST_SKIP
@pytest.mark.skip_on_windows
def test_return(salt_call_cli, salt_run_cli):
    command = "echo returnTOmaster"
    ret = salt_call_cli.run("cmd.run", command)
    assert ret.exitcode == 0
    assert ret.json == "returnTOmaster"

    ret = salt_run_cli.run("jobs.list_jobs")
    assert ret.exitcode == 0
    jid = target = None
    for jid, details in ret.json.items():
        if command in details["Arguments"]:
            target = details["Target"]
            break

    ret = salt_run_cli.run("jobs.lookup_jid", jid, _timeout=60)
    assert ret.exitcode == 0
    assert target in ret.json
    assert ret.json[target] == "returnTOmaster"


@slowTest
def test_exit_status_unknown_argument(salt_call_cli):
    """
    Ensure correct exit status when an unknown argument is passed to salt CLI.
    """
    ret = salt_call_cli.run("--unknown-argument")
    assert ret.exitcode == salt.defaults.exitcodes.EX_USAGE, ret
    assert "Usage" in ret.stderr
    assert "no such option: --unknown-argument" in ret.stderr


@slowTest
def test_exit_status_correct_usage(salt_call_cli):
    """
    Ensure correct exit status when salt CLI starts correctly.

    """
    ret = salt_call_cli.run("test.true")
    assert ret.exitcode == salt.defaults.exitcodes.EX_OK, ret


@slowTest
def test_context_retcode_salt_call(salt_call_cli):
    """
    Test that a nonzero retcode set in the context dunder will cause the
    salt CLI to set a nonzero retcode.
    """
    # Test salt-call, making sure to also confirm the behavior of
    # retcode_passthrough.
    ret = salt_call_cli.run("test.retcode", "0")
    assert ret.exitcode == 0, ret
    ret = salt_call_cli.run("test.retcode", "42")
    assert ret.exitcode == salt.defaults.exitcodes.EX_GENERIC, ret
    ret = salt_call_cli.run("--retcode-passthrough", "test.retcode", "42")
    assert ret.exitcode == 42, ret

    # Test a state run that exits with one or more failures
    ret = salt_call_cli.run("state.single", "test.fail_without_changes", "foo")
    assert ret.exitcode == salt.defaults.exitcodes.EX_GENERIC, ret
    ret = salt_call_cli.run(
        "--retcode-passthrough", "state.single", "test.fail_without_changes", "foo"
    )
    assert ret.exitcode == salt.defaults.exitcodes.EX_STATE_FAILURE, ret

    # Test a state compiler error
    ret = salt_call_cli.run("state.apply", "thisslsfiledoesnotexist")
    assert ret.exitcode == salt.defaults.exitcodes.EX_GENERIC, ret
    ret = salt_call_cli.run(
        "--retcode-passthrough", "state.apply", "thisslsfiledoesnotexist"
    )
    assert ret.exitcode == salt.defaults.exitcodes.EX_STATE_COMPILER_ERROR, ret


@slowTest
def test_salt_call_error(salt_call_cli):
    """
    Test that we return the expected retcode when a minion function raises
    an exception.
    """
    ret = salt_call_cli.run("test.raise_exception", "TypeError")
    assert ret.exitcode == salt.defaults.exitcodes.EX_GENERIC, ret

    ret = salt_call_cli.run(
        "test.raise_exception", "salt.exceptions.CommandNotFoundError"
    )
    assert ret.exitcode == salt.defaults.exitcodes.EX_GENERIC, ret

    ret = salt_call_cli.run(
        "test.raise_exception", "salt.exceptions.CommandExecutionError"
    )
    assert ret.exitcode == salt.defaults.exitcodes.EX_GENERIC, ret

    ret = salt_call_cli.run(
        "test.raise_exception", "salt.exceptions.SaltInvocationError"
    )
    assert ret.exitcode == salt.defaults.exitcodes.EX_GENERIC, ret

    ret = salt_call_cli.run(
        "test.raise_exception",
        "OSError",
        "2",
        "No such file or directory",
        "/tmp/foo.txt",
    )
    assert ret.exitcode == salt.defaults.exitcodes.EX_GENERIC, ret

    ret = salt_call_cli.run("test.echo", "{foo: bar, result: False}")
    assert ret.exitcode == salt.defaults.exitcodes.EX_GENERIC, ret
