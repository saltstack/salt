# -*- coding: utf-8 -*-
'''
    :codeauthor: Pedro Algarvio (pedro@algarvio.me)


    tests.integration.shell.syndic
    ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
'''

# Import python libs
from __future__ import absolute_import
import logging

# Import Salt Testing libs
from tests.support.case import ShellCase
from tests.support.mixins import ShellCaseCommonTestsMixin
from tests.support.unit import skipIf
from tests.integration.utils import testprogram

# Import salt libs
import salt.utils.files
import salt.utils.yaml
import salt.utils.platform

log = logging.getLogger(__name__)


SIGKILL = 9


class SyndicTest(ShellCase, testprogram.TestProgramCase, ShellCaseCommonTestsMixin):
    '''
    Test the salt-syndic command
    '''

    _call_binary_ = 'salt-syndic'

    @skipIf(salt.utils.platform.is_windows(), 'Skip on Windows OS')
    def test_exit_status_unknown_user(self):
        '''
        Ensure correct exit status when the syndic is configured to run as an unknown user.

        Skipped on windows because daemonization not supported
        '''

        syndic = testprogram.TestDaemonSaltSyndic(
            name='unknown_user',
            config_base={'user': 'some_unknown_user_xyz'},
            parent_dir=self._test_dir,
        )
        # Call setup here to ensure config and script exist
        syndic.setup()
        stdout, stderr, status = syndic.run(
            args=['-d'],
            catch_stderr=True,
            with_retcode=True,
        )
        try:
            self.assert_exit_status(
                status, 'EX_NOUSER',
                message='unknown user not on system',
                stdout=stdout, stderr=stderr
            )
        finally:
            # Although the start-up should fail, call shutdown() to set the
            # internal _shutdown flag and avoid the registered atexit calls to
            # cause timeout exceptions and respective traceback
            syndic.shutdown()

    # pylint: disable=invalid-name
    @skipIf(salt.utils.platform.is_windows(), 'Skip on Windows OS')
    def test_exit_status_unknown_argument(self):
        '''
        Ensure correct exit status when an unknown argument is passed to salt-syndic.

        Skipped on windows because daemonization not supported
        '''

        syndic = testprogram.TestDaemonSaltSyndic(
            name='unknown_argument',
            parent_dir=self._test_dir,
        )
        # Syndic setup here to ensure config and script exist
        syndic.setup()
        stdout, stderr, status = syndic.run(
            args=['-d', '--unknown-argument'],
            catch_stderr=True,
            with_retcode=True,
        )
        try:
            self.assert_exit_status(
                status, 'EX_USAGE',
                message='unknown argument',
                stdout=stdout, stderr=stderr
            )
        finally:
            # Although the start-up should fail, call shutdown() to set the
            # internal _shutdown flag and avoid the registered atexit calls to
            # cause timeout exceptions and respective traceback
            syndic.shutdown()

    @skipIf(salt.utils.platform.is_windows(), 'Skip on Windows OS')
    def test_exit_status_correct_usage(self):
        '''
        Ensure correct exit status when salt-syndic starts correctly.

        Skipped on windows because daemonization not supported
        '''

        syndic = testprogram.TestDaemonSaltSyndic(
            name='correct_usage',
            parent_dir=self._test_dir,
        )
        # Syndic setup here to ensure config and script exist
        syndic.setup()
        stdout, stderr, status = syndic.run(
            args=['-d', '-l', 'debug'],
            catch_stderr=True,
            with_retcode=True,
        )
        try:
            self.assert_exit_status(
                status, 'EX_OK',
                message='correct usage',
                stdout=stdout, stderr=stderr
            )
        finally:
            syndic.shutdown(wait_for_orphans=3)
