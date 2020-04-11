# -*- coding: utf-8 -*-
"""
These only test the provider selection and verification logic, they do not init
any remotes.
"""

# Import python libs
from __future__ import absolute_import, print_function, unicode_literals

# Import salt libs
import salt.utils.gitfs
from salt.exceptions import FileserverConfigError
from tests.support.mock import MagicMock, patch

# Import Salt Testing libs
from tests.support.unit import TestCase

# GLOBALS
OPTS = {"cachedir": "/tmp/gitfs-test-cache"}


class TestGitFSProvider(TestCase):
    def test_provider_case_insensitive(self):
        """
        Ensure that both lowercase and non-lowercase values are supported
        """
        provider = "GitPython"
        for role_name, role_class in (
            ("gitfs", salt.utils.gitfs.GitFS),
            ("git_pillar", salt.utils.gitfs.GitPillar),
            ("winrepo", salt.utils.gitfs.WinRepo),
        ):

            key = "{0}_provider".format(role_name)
            with patch.object(
                role_class, "verify_gitpython", MagicMock(return_value=True)
            ):
                with patch.object(
                    role_class, "verify_pygit2", MagicMock(return_value=False)
                ):
                    args = [OPTS, {}]
                    kwargs = {"init_remotes": False}
                    if role_name == "winrepo":
                        kwargs["cache_root"] = "/tmp/winrepo-dir"
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
        """
        Ensure that an invalid provider is not accepted, raising a
        FileserverConfigError.
        """

        def _get_mock(verify, provider):
            """
            Return a MagicMock with the desired return value
            """
            return MagicMock(return_value=verify.endswith(provider))

        for role_name, role_class in (
            ("gitfs", salt.utils.gitfs.GitFS),
            ("git_pillar", salt.utils.gitfs.GitPillar),
            ("winrepo", salt.utils.gitfs.WinRepo),
        ):
            key = "{0}_provider".format(role_name)
            for provider in salt.utils.gitfs.GIT_PROVIDERS:
                verify = "verify_gitpython"
                mock1 = _get_mock(verify, provider)
                with patch.object(role_class, verify, mock1):
                    verify = "verify_pygit2"
                    mock2 = _get_mock(verify, provider)
                    with patch.object(role_class, verify, mock2):
                        args = [OPTS, {}]
                        kwargs = {"init_remotes": False}
                        if role_name == "winrepo":
                            kwargs["cache_root"] = "/tmp/winrepo-dir"

                        with patch.dict(OPTS, {key: provider}):
                            role_class(*args, **kwargs)

                        with patch.dict(OPTS, {key: "foo"}):
                            # Set the provider name to a known invalid provider
                            # and make sure it raises an exception.
                            self.assertRaises(
                                FileserverConfigError, role_class, *args, **kwargs
                            )
