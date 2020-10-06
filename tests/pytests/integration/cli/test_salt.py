"""
    :codeauthor: Thayne Harbaugh (tharbaug@adobe.com)

    tests.integration.shell.saltcli
    ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

    :NOTE: this was named ``saltcli`` rather than ``salt`` because ``salt`` conflates
           in the python importer with the expected ``salt`` namespace and breaks imports.
"""


import logging
import os
import shutil

import pytest
import salt.defaults.exitcodes
import salt.utils.path
from tests.support.helpers import slowTest

log = logging.getLogger(__name__)

pytestmark = pytest.mark.windows_whitelisted


@slowTest
def test_context_retcode_salt(salt_cli, salt_minion):
    """
    Test that a nonzero retcode set in the context dunder will cause the
    salt CLI to set a nonzero retcode.
    """
    # test.retcode will set the retcode in the context dunder
    ret = salt_cli.run("test.retcode", "0", minion_tgt=salt_minion.id)
    assert ret.exitcode == 0, ret
    ret = salt_cli.run("test.retcode", "42", minion_tgt=salt_minion.id)
    assert ret.exitcode == salt.defaults.exitcodes.EX_GENERIC, ret


@slowTest
def test_salt_error(salt_cli, salt_minion):
    """
    Test that we return the expected retcode when a minion function raises
    an exception.
    """
    ret = salt_cli.run("test.raise_exception", "TypeError", minion_tgt=salt_minion.id)
    assert ret.exitcode == salt.defaults.exitcodes.EX_GENERIC, ret

    ret = salt_cli.run(
        "test.raise_exception",
        "salt.exceptions.CommandNotFoundError",
        minion_tgt=salt_minion.id,
    )
    assert ret.exitcode == salt.defaults.exitcodes.EX_GENERIC, ret

    ret = salt_cli.run(
        "test.raise_exception",
        "salt.exceptions.CommandExecutionError",
        minion_tgt=salt_minion.id,
    )
    assert ret.exitcode == salt.defaults.exitcodes.EX_GENERIC, ret

    ret = salt_cli.run(
        "test.raise_exception",
        "salt.exceptions.SaltInvocationError",
        minion_tgt=salt_minion.id,
    )
    assert ret.exitcode == salt.defaults.exitcodes.EX_GENERIC, ret

    ret = salt_cli.run(
        "test.raise_exception",
        "OSError",
        "2",
        '"No such file or directory" /tmp/foo.txt',
        minion_tgt=salt_minion.id,
    )
    assert ret.exitcode == salt.defaults.exitcodes.EX_GENERIC, ret

    ret = salt_cli.run(
        "test.echo", "{foo: bar, result: False}", minion_tgt=salt_minion.id
    )
    assert ret.exitcode == salt.defaults.exitcodes.EX_GENERIC, ret

    ret = salt_cli.run(
        "test.echo", "{foo: bar, success: False}", minion_tgt=salt_minion.id
    )
    assert ret.exitcode == salt.defaults.exitcodes.EX_GENERIC, ret


@slowTest
def test_missing_minion(salt_cli, salt_master, salt_minion):
    """
    Test that a minion which doesn't respond results in a nonzeo exit code
    """
    good = salt.utils.path.join(
        salt_master.config["pki_dir"], "minions", salt_minion.id
    )
    bad = salt.utils.path.join(salt_master.config["pki_dir"], "minions", "minion2")
    try:
        # Copy the key
        shutil.copyfile(good, bad)
        ret = salt_cli.run(
            "--timeout=5", "test.ping", minion_tgt="minion2", _timeout=120
        )
        assert ret.exitcode == salt.defaults.exitcodes.EX_GENERIC, ret
    finally:
        # Now get rid of it
        try:
            os.remove(bad)
        except OSError as exc:
            if exc.errno != os.errno.ENOENT:
                log.error(
                    "Failed to remove %s, this may affect other tests: %s", bad, exc
                )


@slowTest
def test_exit_status_unknown_argument(salt_cli):
    """
    Ensure correct exit status when an unknown argument is passed to salt CLI.
    """
    ret = salt_cli.run("--unknown-argument")
    assert ret.exitcode == salt.defaults.exitcodes.EX_USAGE, ret
    assert "Usage" in ret.stderr
    assert "no such option: --unknown-argument" in ret.stderr


@slowTest
def test_exit_status_correct_usage(salt_cli, salt_minion):
    """
    Ensure correct exit status when salt CLI starts correctly.

    """
    ret = salt_cli.run("test.ping", minion_tgt=salt_minion.id)
    assert ret.exitcode == salt.defaults.exitcodes.EX_OK, ret
