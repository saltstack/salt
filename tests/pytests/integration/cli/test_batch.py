"""
    :codeauthor: Nicole Thomas <nicole@saltstack.com>
"""

import pytest

import salt.utils.platform

pytestmark = [
    pytest.mark.windows_whitelisted,
    pytest.mark.core_test,
]


@pytest.fixture(scope="module")
def run_timeout():
    if salt.utils.platform.is_windows():
        return 180
    else:
        return 30


def test_batch_run(salt_cli, run_timeout, salt_sub_minion):
    """
    Tests executing a simple batch command to help catch regressions
    """
    ret = f"Executing run on [{repr(salt_sub_minion.id)}]"
    cmd = salt_cli.run(
        "test.echo",
        "batch testing",
        "-b 50%",
        minion_tgt="*minion*",
        _timeout=run_timeout,
    )
    assert ret in cmd.stdout


def test_batch_run_number(salt_cli, salt_minion, salt_sub_minion, run_timeout):
    """
    Tests executing a simple batch command using a number division instead of
    a percentage with full batch CLI call.
    """
    ret = "Executing run on [{}, {}]".format(
        repr(salt_minion.id), repr(salt_sub_minion.id)
    )
    cmd = salt_cli.run(
        "--batch-size=2",
        "test.ping",
        minion_tgt="*minion*",
        _timeout=run_timeout,
    )
    assert ret in cmd.stdout


def test_batch_run_grains_targeting(
    grains, salt_cli, salt_minion, salt_sub_minion, run_timeout
):
    """
    Tests executing a batch command using a percentage divisor as well as grains
    targeting.
    """
    sub_min_ret = f"Executing run on [{repr(salt_sub_minion.id)}]"
    min_ret = f"Executing run on [{repr(salt_minion.id)}]"
    cmd = salt_cli.run(
        "-C",
        "-b 25%",
        "test.ping",
        minion_tgt="G@os:{} and not localhost".format(grains["os"].replace(" ", "?")),
        _timeout=run_timeout,
    )
    assert sub_min_ret in cmd.stdout
    assert min_ret in cmd.stdout


def test_batch_exit_code(salt_cli, salt_minion, salt_sub_minion, run_timeout):
    """
    Test that a failed state returns a non-zero exit code in batch mode
    """
    cmd = salt_cli.run(
        "state.single",
        "test.fail_without_changes",
        "name=test_me",
        "-b 25%",
        minion_tgt="*minion*",
        _timeout=run_timeout,
    )
    assert cmd.returncode == 2


# Test for failhard + batch. The best possible solution here was to do something like that:
# assertRaises(StopIteration)
# But it's impossible due to nature of the tests execution via fork()


def test_batch_module_stopping_after_error(
    salt_cli, salt_minion, salt_sub_minion, run_timeout
):
    """
    Test that a failed command stops the batch run
    """

    minions_list = []
    retcode = None

    # Executing salt with batch: 1 and with failhard. It should stop after the first error.
    cmd = salt_cli.run(
        "test.retcode",
        42,
        "-b 1",
        "--out=yaml",
        "--failhard",
        minion_tgt="*minion*",
        _timeout=run_timeout,
    )

    # Parsing the output. Idea is to fetch number on minions and retcode of the execution.
    # retcode var could be overwritten in case of broken failhard but number of minions check should still fail.
    for line in cmd.stdout.splitlines():
        line = line.strip()
        if line.startswith("Executing run on"):
            minions_list.append(line)
        if line.startswith("retcode"):
            retcode = int(line.split(" ")[-1])
    # We expect to have only one minion to be run
    assert 1 == len(minions_list)
    # We expect to find a retcode in the output
    assert None is not retcode
    # We expect retcode to be non-zero
    assert 0 != retcode


def test_batch_state_stopping_after_error(
    salt_cli, salt_minion, salt_sub_minion, run_timeout
):
    """
    Test that a failed state stops the batch run
    """

    minions_list = []
    retcode = None

    # Executing salt with batch: 1 and with failhard. It should stop after the first error.
    cmd = salt_cli.run(
        "state.single",
        "test.fail_without_changes",
        "name=test_me",
        "-b 1",
        "--out=yaml",
        "--failhard",
        minion_tgt="*minion*",
        _timeout=run_timeout,
    )

    # Parsing the output. Idea is to fetch number on minions and retcode of the execution.
    # retcode var could be overwritten in case of broken failhard but number of minions check should still fail.
    for line in cmd.stdout.splitlines():
        if line.startswith("Executing run on"):
            minions_list.append(line)
        if line.startswith("retcode"):
            retcode = int(line.split(" ")[-1])
    # We expect to have only one minion to be run
    assert 1 == len(minions_list)
    # We expect to find a retcode in the output
    assert None is not retcode
    # We expect retcode to be non-zero
    assert 0 != retcode


def test_batch_retcode(salt_cli, salt_minion, salt_sub_minion, run_timeout):
    """
    Ensure that the correct retcode is given in batch runs.

    See issue #60361
    """
    cmd = salt_cli.run(
        "test.retcode",
        "23",
        "-b 1",
        minion_tgt="*minion*",
        _timeout=run_timeout,
    )

    assert cmd.returncode == 23
    # TODO: Certain platforms will have a warning related to jinja. But
    # that's an issue with dependency versions that may be due to the versions
    # installed on the test images. When those issues are sorted, this can
    # simply `not cmd.stderr`.
    assert not cmd.stderr
    assert "true" in cmd.stdout


def test_multiple_modules_in_batch(salt_cli, salt_minion, salt_sub_minion, run_timeout):
    """
    Ensure that running multiple modules at the same time works in batch.

    See issue #60361
    """
    cmd = salt_cli.run(
        "test.ping,test.retcode",
        ",23",
        "-b 1",
        minion_tgt="*minion*",
        _timeout=run_timeout,
    )

    assert cmd.returncode == 23
    # TODO: Certain platforms will have a warning related to setproctitle. But
    # that's an issue with dependency versions that may be due to the versions
    # installed on the test images. When those issues are sorted, this can
    # simply `not cmd.stderr`.
    assert not cmd.stderr


def test_batch_module_stopping_failed_respond(
    salt_cli, salt_minion, salt_sub_minion, run_timeout
):
    """
    Test that minion failed to respond to job sent and stops the batch run
    """

    minions_list = []
    retcode = None
    test_data_failed = {"failed": True}

    # Executing salt with batch: 1 and with failhard. It should stop after the first error.
    cmd = salt_cli.run(
        "test.outputter",
        test_data_failed,
        "-b 1",
        "--out=yaml",
        "--failhard",
        minion_tgt="*minion*",
        _timeout=run_timeout,
    )

    # Parsing the output. Idea is to fetch number on minions and retcode of the execution, but not 'ret' key.
    # data dictionary should be overwritten, should fail regardless of failhard
    # number of minions check should still fail.
    for line in cmd.stdout.splitlines():
        line = line.strip()
        if line.startswith("Executing run on"):
            minions_list.append(line)
        if line.startswith("retcode"):
            retcode = int(line.split(" ")[-1])
        if line.startswith("failed"):
            failure = line.split(" ")[-1]
    # We expect to have only one minion to be run
    assert 2 == len(minions_list)
    # We expect to find a retcode in the output
    assert None is not retcode
    # We expect failure to be True
    assert failure == "true"
