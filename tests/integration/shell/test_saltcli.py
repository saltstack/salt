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

    def __test_exception(self, salt_call=False):
        '''
        Tests retcode when various exceptions are raised
        '''
        if salt_call:
            run_func = self.run_call
            error_status = self.salt_call_error_status
        else:
            run_func = self.run_salt
            error_status = self.salt_error_status

        def _run(command):
            return run_func(
                '{0}{1}'.format(
                    'minion ' if not salt_call else '',
                    command),
                with_retcode=True)[1]

        retcode = _run('test.raise_exception TypeError')
        assert retcode == error_status, retcode

        retcode = _run(
            'test.raise_exception salt.exceptions.CommandNotFoundError')
        assert retcode == error_status, retcode

        retcode = _run(
            'test.raise_exception salt.exceptions.CommandExecutionError')
        assert retcode == error_status, retcode

        retcode = _run(
            'test.raise_exception salt.exceptions.SaltInvocationError')
        assert retcode == error_status, retcode

        retcode = _run(
            'test.raise_exception '
            'OSError 2 "No such file or directory" /tmp/foo.txt')
        assert retcode == error_status, retcode

    def test_salt_zero_exit_code(self):
        '''
        Test that a zero exit code is set when there are no errors and there is
        no explicit False result set in the return data.
        '''
        retcode = self.run_salt(
            'minion test.ping',
            with_retcode=True)[1]
        assert retcode == 0, retcode

    def test_salt_context_retcode(self):
        '''
        Test that a nonzero retcode set in the context dunder will cause the
        salt CLI to set a nonzero retcode.
        '''
        retcode = self.run_salt(
            'minion test.retcode 0',
            with_retcode=True)[1]
        assert retcode == 0, retcode

        retcode = self.run_salt(
            'minion test.retcode 42',
            with_retcode=True)[1]
        assert retcode == self.salt_error_status, retcode

    def test_salt_exception(self):
        '''
        Test that we return the expected retcode when a minion function raises
        an exception.
        '''
        self.__test_exception()

    def test_salt_call_zero_exit_code(self):
        '''
        Test that a zero exit code is set when there are no errors and there is
        no explicit False result set in the return data.
        '''
        retcode = self.run_call(
            'minion test.ping',
            with_retcode=True)[1]
        assert retcode == 0, retcode

    def test_salt_call_context_retcode(self):
        '''
        Test that a nonzero retcode set in the context dunder will cause the
        salt CLI to set a nonzero retcode.
        '''
        retcode = self.run_call(
            '--retcode-passthrough test.retcode 0',
            with_retcode=True)[1]
        assert retcode == 0, retcode

        retcode = self.run_call(
            '--retcode-passthrough test.retcode 42',
            with_retcode=True)[1]
        assert retcode == 42, retcode

    def test_salt_call_exception(self):
        '''
        Test that we return the expected retcode when a minion function raises
        an exception.
        '''
        self.__test_exception(salt_call=True)
