# -*- coding: utf-8 -*-
'''
These only test the provider selection and verification logic, they do not init
any remotes.
'''

# Import python libs
from __future__ import absolute_import, unicode_literals, print_function

# Import Salt Testing libs
import shutil

from tests.support.unit import skipIf, TestCase
from tests.support.mock import MagicMock, patch, NO_MOCK, NO_MOCK_REASON

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
                    args = [OPTS, {}]
                    kwargs = {'init_remotes': False}
                    if role_name == 'winrepo':
                        kwargs['cache_root'] = '/tmp/winrepo-dir'
                    with patch.dict(OPTS, {key: provider}):
                        # Try to create an instance with uppercase letters in
                        # provider name. If it fails then a
                        # FileserverConfigError will be raised, so no assert is
                        # necessary.
                        role_class(*args, **kwargs)
                    # Now try to instantiate an instance with all lowercase
                    # letters. Again, no need for an assert here.
                    role_class(*args, **kwargs)

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
            for provider in salt.utils.gitfs.GIT_PROVIDERS:
                verify = 'verify_gitpython'
                mock1 = _get_mock(verify, provider)
                with patch.object(role_class, verify, mock1):
                    verify = 'verify_pygit2'
                    mock2 = _get_mock(verify, provider)
                    with patch.object(role_class, verify, mock2):
                        args = [OPTS, {}]
                        kwargs = {'init_remotes': False}
                        if role_name == 'winrepo':
                            kwargs['cache_root'] = '/tmp/winrepo-dir'

                        with patch.dict(OPTS, {key: provider}):
                            role_class(*args, **kwargs)

                        with patch.dict(OPTS, {key: 'foo'}):
                            # Set the provider name to a known invalid provider
                            # and make sure it raises an exception.
                            self.assertRaises(
                                FileserverConfigError,
                                role_class,
                                *args,
                                **kwargs)

    class _cleaner(object):
        def __init__(self, directory):
            self.dir = directory

        def __enter__(self):
            try:
                shutil.rmtree(self.dir)
            except OSError:
                pass

        def __exit__(self, exc_type, exc_val, exc_tb):
            self.__enter__()

    def test_pygit2_fetch_to_cache(self):
        opts = {}
        cache_root = '/tmp/git_repo'
        remote = cache_root  # We'll sync empty repo from itself for simplisity
        per_remote_defaults = {'ssl_verify': False}
        per_remote_only = ()
        override_params = ()
        role = 'gitfs'

        with self._cleaner(cache_root):
            # Do things as it's done by GitBase.init_remotes
            repo_obj = salt.utils.gitfs.GIT_PROVIDERS['pygit2'](
                opts,
                remote,
                per_remote_defaults,
                per_remote_only,
                override_params,
                cache_root,
                role
            )
            self.assertTrue(hasattr(repo_obj, 'repo'))
            self.assertTrue(repo_obj.new)
            repo_obj.verify_auth()
            repo_obj.setup_callbacks()
            try:
                repo_obj.fetch()
            except IndexError:
                self.fail('PyGit2 raised an IndexError on fetch')
