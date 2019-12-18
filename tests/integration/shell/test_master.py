# -*- coding: utf-8 -*-
'''
    :codeauthor: Pedro Algarvio (pedro@algarvio.me)


    tests.integration.shell.master
    ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
'''

# Import python libs
from __future__ import absolute_import

# Import salt test libs
import tests.integration.utils
from tests.support.case import ShellCase
from tests.support.mixins import ShellCaseCommonTestsMixin
from tests.support.unit import skipIf
from tests.integration.utils import testprogram


@skipIf(True, 'This test file should be in an isolated test space.')
class MasterTest(ShellCase, testprogram.TestProgramCase, ShellCaseCommonTestsMixin):

    _call_binary_ = 'salt-master'

    def test_exit_status_unknown_user(self):
        '''
        Ensure correct exit status when the master is configured to run as an unknown user.
        '''

        master = testprogram.TestDaemonSaltMaster(
            name='unknown_user',
            configs={'master': {'map': {'user': 'some_unknown_user_xyz'}}},
            parent_dir=self._test_dir,
        )
        # Call setup here to ensure config and script exist
        master.setup()
        stdout, stderr, status = master.run(
            args=['-d'],
            catch_stderr=True,
            with_retcode=True,
        )
        try:
            self.assert_exit_status(
                status, 'EX_NOUSER',
                message='unknown user not on system',
                stdout=stdout,
                stderr=tests.integration.utils.decode_byte_list(stderr)
            )
        finally:
            # Although the start-up should fail, call shutdown() to set the
            # internal _shutdown flag and avoid the registered atexit calls to
            # cause timeout exceptions and respective traceback
            master.shutdown()

    # pylint: disable=invalid-name
    def test_exit_status_unknown_argument(self):
        '''
        Ensure correct exit status when an unknown argument is passed to salt-master.
        '''

        master = testprogram.TestDaemonSaltMaster(
            name='unknown_argument',
            parent_dir=self._test_dir,
        )
        # Call setup here to ensure config and script exist
        master.setup()
        stdout, stderr, status = master.run(
            args=['-d', '--unknown-argument'],
            catch_stderr=True,
            with_retcode=True,
        )
        try:
            self.assert_exit_status(
                status, 'EX_USAGE',
                message='unknown argument',
                stdout=stdout,
                stderr=tests.integration.utils.decode_byte_list(stderr)
            )
        finally:
            # Although the start-up should fail, call shutdown() to set the
            # internal _shutdown flag and avoid the registered atexit calls to
            # cause timeout exceptions and respective traceback
            master.shutdown()

    def test_exit_status_correct_usage(self):
        '''
        Ensure correct exit status when salt-master starts correctly.
        '''

        master = testprogram.TestDaemonSaltMaster(
            name='correct_usage',
            parent_dir=self._test_dir,
        )
        # Call setup here to ensure config and script exist
        master.setup()
        stdout, stderr, status = master.run(
            args=['-d'],
            catch_stderr=True,
            with_retcode=True,
        )
        try:
            self.assert_exit_status(
                status, 'EX_OK',
                message='correct usage',
                stdout=stdout,
                stderr=tests.integration.utils.decode_byte_list(stderr)
            )
        finally:
            master.shutdown(wait_for_orphans=3)

        # Do the test again to check does master shut down correctly
        # **Due to some underlying subprocessing issues with Minion._thread_return, this
        # part of the test has been commented out. Once these underlying issues have
        # been addressed, this part of the test should be uncommented. Work for this
        # issue is being tracked in https://github.com/saltstack/salt-jenkins/issues/378
        # stdout, stderr, status = master.run(
        #     args=['-d'],
        #     catch_stderr=True,
        #     with_retcode=True,
        # )
        # try:
        #     self.assert_exit_status(
        #         status, 'EX_OK',
        #         message='correct usage',
        #         stdout=stdout,
        #         stderr=tests.integration.utils.decode_byte_list(stderr)
        #     )
        # finally:
        #     master.shutdown(wait_for_orphans=3)
