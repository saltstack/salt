# -*- coding: utf-8 -*-
'''
    :codeauthor: :email:`Thayne Harbaugh (tharbaug@adobe.com)`

    tests.integration.shell.saltcli
    ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

    :NOTE: this was named ``saltcli`` rather than ``salt`` because ``salt`` conflates
           in the python importer with the expected ``salt`` namespace and breaks imports.
'''

# Import python libs
from __future__ import absolute_import
import logging

# Import Salt Testing libs
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
