# -*- coding: utf-8 -*-
'''
These only test the provider selection and verification logic, they do not init
any remotes.
'''

# Import python libs
from __future__ import absolute_import

# Import Salt Testing libs
from salttesting import skipIf, TestCase
from salttesting.mock import MagicMock, patch, NO_MOCK, NO_MOCK_REASON
from salttesting.helpers import ensure_in_syspath
ensure_in_syspath('../../')

# Import salt libs
import salt.utils.gitfs
from salt.exceptions import FileserverConfigError

# GLOBALS
OPTS = {'cachedir': '/tmp/gitfs-test-cache'}


@skipIf(NO_MOCK, NO_MOCK_REASON)
class TestGitFSProvider(TestCase):

    def test_provider_case_insensitive(self):
        '''
        Ensure that both lowercase and non-lowercase values are supported
        '''
        provider = 'GitPython'
        for role_name, role_class in (
                ('gitfs', salt.utils.gitfs.GitFS),
                ('git_pillar', salt.utils.gitfs.GitPillar),
                ('winrepo', salt.utils.gitfs.WinRepo)):

            key = '{0}_provider'.format(role_name)
            with patch.object(role_class, 'verify_gitpython',
                              MagicMock(return_value=True)):
                with patch.object(role_class, 'verify_pygit2',
                                  MagicMock(return_value=False)):
                    with patch.object(role_class, 'verify_dulwich',
                                      MagicMock(return_value=False)):
                        args = [OPTS]
                        if role_name == 'winrepo':
                            args.append('/tmp/winrepo-dir')
                        with patch.dict(OPTS, {key: provider}):
                            # Try to create an instance with uppercase letters in
                            # provider name. If it fails then a
                            # FileserverConfigError will be raised, so no assert is
                            # necessary.
                            role_class(*args)
                            # Now try to instantiate an instance with all lowercase
                            # letters. Again, no need for an assert here.
                            role_class(*args)

    def test_valid_provider(self):
        '''
        Ensure that an invalid provider is not accepted, raising a
        FileserverConfigError.
        '''
        def _get_mock(verify, provider):
            '''
            Return a MagicMock with the desired return value
            '''
            return MagicMock(return_value=verify.endswith(provider))

        for role_name, role_class in (
                ('gitfs', salt.utils.gitfs.GitFS),
                ('git_pillar', salt.utils.gitfs.GitPillar),
                ('winrepo', salt.utils.gitfs.WinRepo)):
            key = '{0}_provider'.format(role_name)
            for provider in salt.utils.gitfs.VALID_PROVIDERS:
                verify = 'verify_gitpython'
                mock1 = _get_mock(verify, provider)
                with patch.object(role_class, verify, mock1):
                    verify = 'verify_pygit2'
                    mock2 = _get_mock(verify, provider)
                    with patch.object(role_class, verify, mock2):
                        verify = 'verify_dulwich'
                        mock3 = _get_mock(verify, provider)
                        with patch.object(role_class, verify, mock3):
                            args = [OPTS]
                            if role_name == 'winrepo':
                                args.append('/tmp/winrepo-dir')
                            with patch.dict(OPTS, {key: provider}):
                                if role_name == 'gitfs' \
                                        or (role_name != 'gitfs'
                                            and provider != 'dulwich'):
                                    # This is a valid provider, so this should
                                    # pass without raising an exception.
                                    role_class(*args)
                                else:
                                    # Dulwich is not supported for git_pillar nor
                                    # winrepo, so trying to use it should raise an
                                    # exception.
                                    self.assertRaises(
                                        FileserverConfigError,
                                        role_class,
                                        *args
                                    )

                            with patch.dict(OPTS, {key: 'foo'}):
                                # Set the provider name to a known invalid provider
                                # and make sure it raises an exception.
                                self.assertRaises(
                                    FileserverConfigError,
                                    role_class,
                                    *args
                                )


if __name__ == '__main__':
    from integration import run_tests
    run_tests(TestGitFSProvider, needs_daemon=False)
