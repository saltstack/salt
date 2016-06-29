# -*- coding: utf-8 -*-
'''
    :codeauthor: :email:`Thayne Harbaugh (tharbaug@adobe.com)`

    tests.integration.shell.test_proxy
    ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
'''

# Import python libs
from __future__ import absolute_import
import logging

# Import salt libs
from integration.utils import testprogram

log = logging.getLogger(__name__)


class ProxyTest(testprogram.TestProgramCase):
    '''
    Various integration tests for the salt-proxy executable.
    '''

    def test_exit_status_no_proxyid(self):
        '''
        Ensure correct exit status when --proxyid argument is missing.
        '''

        proxy = testprogram.TestDaemonSaltProxy(
            name='proxy-no_proxyid',
            parent_dir=self._test_dir,
        )
        # Call setup here to ensure config and script exist
        proxy.setup()
        stdout, stderr, status = proxy.run(
            args=['-d'],
            verbatim_args=True,   # prevents --proxyid from being added automatically
            catch_stderr=True,
            with_retcode=True,
        )
        self.assert_exit_status(
            status, 'EX_USAGE',
            message='no --proxyid specified',
            stdout=stdout, stderr=stderr
        )
        # proxy.shutdown() should be unnecessary since the start-up should fail

    def test_exit_status_unknown_user(self):
        '''
        Ensure correct exit status when the proxy is configured to run as an unknown user.
        '''

        proxy = testprogram.TestDaemonSaltProxy(
            name='proxy-unknown_user',
            config={'user': 'unknown'},
            parent_dir=self._test_dir,
        )
        # Call setup here to ensure config and script exist
        proxy.setup()
        stdout, stderr, status = proxy.run(
            args=['-d'],
            catch_stderr=True,
            with_retcode=True,
        )
        self.assert_exit_status(
            status, 'EX_NOUSER',
            message='unknown user not on system',
            stdout=stdout, stderr=stderr
        )
        # proxy.shutdown() should be unnecessary since the start-up should fail

    # pylint: disable=invalid-name
    def test_exit_status_unknown_argument(self):
        '''
        Ensure correct exit status when an unknown argument is passed to salt-proxy.
        '''

        proxy = testprogram.TestDaemonSaltProxy(
            name='proxy-unknown_argument',
            parent_dir=self._test_dir,
        )
        # Call setup here to ensure config and script exist
        proxy.setup()
        stdout, stderr, status = proxy.run(
            args=['-d', '--unknown-argument'],
            catch_stderr=True,
            with_retcode=True,
        )
        self.assert_exit_status(
            status, 'EX_USAGE',
            message='unknown argument',
            stdout=stdout, stderr=stderr
        )
        # proxy.shutdown() should be unnecessary since the start-up should fail

    def test_exit_status_correct_usage(self):
        '''
        Ensure correct exit status when salt-proxy starts correctly.
        '''

        proxy = testprogram.TestDaemonSaltProxy(
            name='proxy-correct_usage',
            parent_dir=self._test_dir,
        )
        # Call setup here to ensure config and script exist
        proxy.setup()
        stdout, stderr, status = proxy.run(
            args=['-d'],
            catch_stderr=True,
            with_retcode=True,
        )
        self.assert_exit_status(
            status, 'EX_OK',
            message='correct usage',
            stdout=stdout, stderr=stderr
        )
        proxy.shutdown()
