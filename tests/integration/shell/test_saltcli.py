# -*- coding: utf-8 -*-
'''
    :codeauthor: Thayne Harbaugh (tharbaug@adobe.com)

    tests.integration.shell.saltcli
    ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

    :NOTE: this was named ``saltcli`` rather than ``salt`` because ``salt`` conflates
           in the python importer with the expected ``salt`` namespace and breaks imports.
'''

# Import python libs
from __future__ import absolute_import
import logging

# Import Salt Testing libs
from tests.support.case import ShellCase
from tests.integration.utils import testprogram

log = logging.getLogger(__name__)


class SaltTest(testprogram.TestProgramCase):
    '''
    Various integration tests for the salt executable.
    '''

    # pylint: disable=invalid-name
    def test_exit_status_unknown_argument(self):
        '''
        Ensure correct exit status when an unknown argument is passed to salt-run.
        '''

        runner = testprogram.TestProgramSalt(
            name='run-unknown_argument',
            parent_dir=self._test_dir,
        )
        # Call setup here to ensure config and script exist
        runner.setup()
        stdout, stderr, status = runner.run(
            args=['--unknown-argument'],
            catch_stderr=True,
            with_retcode=True,
        )
        self.assert_exit_status(
            status, 'EX_USAGE',
            message='unknown argument',
            stdout=stdout, stderr=stderr
        )
        # runner.shutdown() should be unnecessary since the start-up should fail

    def test_exit_status_correct_usage(self):
        '''
        Ensure correct exit status when salt-run starts correctly.
        '''

        runner = testprogram.TestProgramSalt(
            name='run-correct_usage',
            parent_dir=self._test_dir,
        )
        # Call setup here to ensure config and script exist
        runner.setup()
        stdout, stderr, status = runner.run(
            args=['*', '-h'],
            catch_stderr=True,
            with_retcode=True,
        )
        self.assert_exit_status(
            status, 'EX_OK',
            message='correct usage',
            stdout=stdout, stderr=stderr
        )


class RetcodeTestCase(ShellCase):
    '''
    Tests to ensure that we set non-zero retcodes when execution fails
    '''
    salt_error_status = 11
    salt_call_error_status = 1

    def _run(self, command, salt_call=False):
        return (self.run_call if salt_call else self.run_salt)(
            '{0}{1}{2}'.format(
                'minion ' if not salt_call else '',
                '--retcode-passthrough ' if salt_call else '',
                command
            ),
            with_retcode=True)[1]

    def _test_error(self, salt_call=False):
        '''
        Tests retcode when various error conditions are triggered
        '''
        error_status = self.salt_call_error_status \
            if salt_call \
            else self.salt_error_status

        retcode = self._run('test.raise_exception TypeError', salt_call=salt_call)
        assert retcode == error_status, retcode

        retcode = self._run(
            'test.raise_exception salt.exceptions.CommandNotFoundError',
            salt_call=salt_call)
        assert retcode == error_status, retcode

        retcode = self._run(
            'test.raise_exception salt.exceptions.CommandExecutionError',
            salt_call=salt_call)
        assert retcode == error_status, retcode

        retcode = self._run(
            'test.raise_exception salt.exceptions.SaltInvocationError',
            salt_call=salt_call)
        assert retcode == error_status, retcode

        retcode = self._run(
            'test.raise_exception '
            'OSError 2 "No such file or directory" /tmp/foo.txt',
            salt_call=salt_call)
        assert retcode == error_status, retcode

        retcode = self._run(
            'test.echo "{foo: bar, result: False}"',
            salt_call=salt_call)
        assert retcode == error_status, retcode

        retcode = self._run(
            'test.echo "{foo: bar, success: False}"',
            salt_call=salt_call)
        assert retcode == error_status, retcode

    def test_zero_exit_code(self):
        '''
        Test that a zero exit code is set when there are no errors and there is
        no explicit False result set in the return data.
        '''
        retcode = self._run('test.ping')
        assert retcode == 0, retcode

        retcode = self._run('test.ping', salt_call=True)
        assert retcode == 0, retcode

    def test_context_retcode(self):
        '''
        Test that a nonzero retcode set in the context dunder will cause the
        salt CLI to set a nonzero retcode.
        '''
        retcode = self._run('test.retcode 0')
        assert retcode == 0, retcode

        retcode = self._run('test.retcode 42')
        assert retcode == self.salt_error_status, retcode

        retcode = self._run('test.retcode 0', salt_call=True)
        assert retcode == 0, retcode

        retcode = self._run('test.retcode 42', salt_call=True)
        assert retcode == 42, retcode

    def test_salt_error(self):
        '''
        Test that we return the expected retcode when a minion function raises
        an exception.
        '''
        self._test_error()
        self._test_error(salt_call=True)
