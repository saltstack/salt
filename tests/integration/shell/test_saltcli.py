# -*- coding: utf-8 -*-
"""
    :codeauthor: Thayne Harbaugh (tharbaug@adobe.com)

    tests.integration.shell.saltcli
    ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

    :NOTE: this was named ``saltcli`` rather than ``salt`` because ``salt`` conflates
           in the python importer with the expected ``salt`` namespace and breaks imports.
"""

# Import python libs
from __future__ import absolute_import

import logging
import os

# Import Salt libs
import salt.defaults.exitcodes
import salt.utils.files
import salt.utils.path
from tests.integration.utils import testprogram

# Import Salt Testing libs
from tests.support.case import ShellCase

log = logging.getLogger(__name__)


class SaltTest(testprogram.TestProgramCase):
    """
    Various integration tests for the salt executable.
    """

    # pylint: disable=invalid-name
    def test_exit_status_unknown_argument(self):
        """
        Ensure correct exit status when an unknown argument is passed to salt-run.
        """

        runner = testprogram.TestProgramSalt(
            name="run-unknown_argument", parent_dir=self._test_dir,
        )
        # Call setup here to ensure config and script exist
        runner.setup()
        stdout, stderr, status = runner.run(
            args=["--unknown-argument"], catch_stderr=True, with_retcode=True,
        )
        self.assert_exit_status(
            status, "EX_USAGE", message="unknown argument", stdout=stdout, stderr=stderr
        )
        # runner.shutdown() should be unnecessary since the start-up should fail

    def test_exit_status_correct_usage(self):
        """
        Ensure correct exit status when salt-run starts correctly.
        """

        runner = testprogram.TestProgramSalt(
            name="run-correct_usage", parent_dir=self._test_dir,
        )
        # Call setup here to ensure config and script exist
        runner.setup()
        stdout, stderr, status = runner.run(
            args=["*", "-h"], catch_stderr=True, with_retcode=True,
        )
        self.assert_exit_status(
            status, "EX_OK", message="correct usage", stdout=stdout, stderr=stderr
        )


class RetcodeTestCase(ShellCase):
    """
    Tests to ensure that we set non-zero retcodes when execution fails
    """

    # Hard-coding these instead of substituting values from
    # salt.defaults.exitcodes will give us a heads-up in the event that someone
    # tries to do something daft like change these values.
    error_status = salt.defaults.exitcodes.EX_GENERIC
    state_compiler_error = salt.defaults.exitcodes.EX_STATE_COMPILER_ERROR
    state_failure = salt.defaults.exitcodes.EX_STATE_FAILURE

    def _salt(self, command):
        cmdline = "minion " + command
        return self.run_salt(cmdline, with_retcode=True)[1]

    def _salt_call(self, command, retcode_passthrough=False):
        cmdline = "--retcode-passthrough " if retcode_passthrough else ""
        cmdline += command
        return self.run_call(cmdline, with_retcode=True)[1]

    def _test_error(self, salt_call=False):
        """
        Tests retcode when various error conditions are triggered
        """
        _run = self._salt_call if salt_call else self._salt

        retcode = _run("test.raise_exception TypeError")
        assert retcode == self.error_status, retcode

        retcode = _run("test.raise_exception salt.exceptions.CommandNotFoundError")
        assert retcode == self.error_status, retcode

        retcode = _run("test.raise_exception salt.exceptions.CommandExecutionError")
        assert retcode == self.error_status, retcode

        retcode = _run("test.raise_exception salt.exceptions.SaltInvocationError")
        assert retcode == self.error_status, retcode

        retcode = _run(
            "test.raise_exception " 'OSError 2 "No such file or directory" /tmp/foo.txt'
        )
        assert retcode == self.error_status, retcode

        retcode = _run('test.echo "{foo: bar, result: False}"')
        assert retcode == self.error_status, retcode

        retcode = _run('test.echo "{foo: bar, success: False}"')
        assert retcode == self.error_status, retcode

    def test_zero_exit_code(self):
        """
        Test that a zero exit code is set when there are no errors and there is
        no explicit False result set in the return data.
        """
        retcode = self._salt("test.ping")
        assert retcode == 0, retcode

        retcode = self._salt_call("test.ping")
        assert retcode == 0, retcode

    def test_context_retcode(self):
        """
        Test that a nonzero retcode set in the context dunder will cause the
        salt CLI to set a nonzero retcode.
        """
        # test.retcode will set the retcode in the context dunder
        retcode = self._salt("test.retcode 0")
        assert retcode == 0, retcode
        retcode = self._salt("test.retcode 42")
        assert retcode == self.error_status, retcode

        # Test salt-call, making sure to also confirm the behavior of
        # retcode_passthrough.
        retcode = self._salt_call("test.retcode 0")
        assert retcode == 0, retcode
        retcode = self._salt_call("test.retcode 42")
        assert retcode == self.error_status, retcode
        retcode = self._salt_call("test.retcode 42", retcode_passthrough=True)
        assert retcode == 42, retcode

        # Test a state run that exits with one or more failures
        retcode = self._salt_call("state.single test.fail_without_changes foo")
        assert retcode == self.error_status, retcode
        retcode = self._salt_call(
            "state.single test.fail_without_changes foo", retcode_passthrough=True
        )
        assert retcode == self.state_failure, retcode

        # Test a state compiler error
        retcode = self._salt_call("state.apply thisslsfiledoesnotexist")
        assert retcode == self.error_status, retcode
        retcode = self._salt_call(
            "state.apply thisslsfiledoesnotexist", retcode_passthrough=True
        )
        assert retcode == self.state_compiler_error, retcode

    def test_salt_error(self):
        """
        Test that we return the expected retcode when a minion function raises
        an exception.
        """
        self._test_error()
        self._test_error(salt_call=True)

    def test_missing_minion(self):
        """
        Test that a minion which doesn't respond results in a nonzeo exit code
        """
        good = salt.utils.path.join(self.master_opts["pki_dir"], "minions", "minion")
        bad = salt.utils.path.join(self.master_opts["pki_dir"], "minions", "minion2")
        try:
            # Copy the key
            with salt.utils.files.fopen(good, "rb") as fhr, salt.utils.files.fopen(
                bad, "wb"
            ) as fhw:
                fhw.write(fhr.read())
            retcode = self.run_script(
                "salt",
                "-c {0} -t 5 minion2 test.ping".format(self.config_dir),
                with_retcode=True,
                timeout=60,
            )[1]
            assert retcode == salt.defaults.exitcodes.EX_GENERIC, retcode
        finally:
            # Now get rid of it
            try:
                os.remove(bad)
            except OSError as exc:
                if exc.errno != os.errno.ENOENT:
                    log.error(
                        "Failed to remove %s, this may affect other tests: %s", bad, exc
                    )
