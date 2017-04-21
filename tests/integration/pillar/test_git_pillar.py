# -*- coding: utf-8 -*-
'''
Tests for the salt-run command
'''
# Import Python libs
from __future__ import absolute_import
import os
import tempfile
import tornado.web

from salt.utils.gitfs import GITPYTHON_MINVER, PYGIT2_MINVER

# Import Salt Testing libs
from tests.support.helpers import (
    destructiveTest,
    http_basic_auth,
    skip_if_not_root,
    Webserver,
)
from tests.support.git_pillar import HTTPTestBase, SSHTestBase
from tests.support.paths import TMP
from tests.support.unit import skipIf
from tests.support.mock import NO_MOCK, NO_MOCK_REASON

# Import Salt libs
import salt.utils
from salt.utils.versions import LooseVersion

try:
    import git
    HAS_GITPYTHON = \
        LooseVersion(git.__version__) >= LooseVersion(GITPYTHON_MINVER)
except ImportError:
    HAS_GITPYTHON = False

try:
    import pygit2
    HAS_PYGIT2 = \
        LooseVersion(pygit2.__version__) >= LooseVersion(PYGIT2_MINVER)
except ImportError:
    HAS_PYGIT2 = False

NOTSET = object()
USERNAME = 'gitpillaruser'
PASSWORD = 'saltrules'


@http_basic_auth(lambda u, p: u == USERNAME and p == PASSWORD)  # pylint: disable=W0223
class HTTPBasicAuthHandler(tornado.web.StaticFileHandler):
    pass


@destructiveTest
@skipIf(not salt.utils.which('sshd'), 'sshd not present')
@skipIf(not HAS_GITPYTHON, 'GitPython >= {0} required'.format(GITPYTHON_MINVER))
@skipIf(salt.utils.is_windows(), 'minion is windows')
@skip_if_not_root
@skipIf(NO_MOCK, NO_MOCK_REASON)
class TestGitPythonSSH(SSHTestBase):
    '''
    Test git_pillar with GitPython using SSH authentication

    NOTE: Any tests added to this test class should have equivalent tests (if
    possible) in the TestPygit2SSH class. Also, bear in mind that the pygit2
    versions of these tests need to be more complex in that they need to test
    both with passphraseless and passphrase-protecteed keys, both with global
    and per-remote configuration. So for every time we run a GitPython test, we
    need to run that same test four different ways for pygit2. This is because
    GitPython's ability to use git-over-SSH is limited to passphraseless keys.
    So, unlike pygit2, we don't need to test global or per-repo credential
    config params since GitPython doesn't use them.
    '''
    username = USERNAME
    passphrase = PASSWORD
    sshd_config_dir = tempfile.mkdtemp(dir=TMP)

    def get_pillar(self, ext_pillar_conf):
        '''
        Wrap the parent class' get_pillar() func in logic that temporarily
        changes the GIT_SSH to use our custom script, ensuring that the
        passphraselsess key is used to auth without needing to modify the root
        user's ssh config file.
        '''
        orig_git_ssh = os.environ.pop('GIT_SSH', NOTSET)
        os.environ['GIT_SSH'] = self.git_ssh
        try:
            return super(TestGitPythonSSH, self).get_pillar(ext_pillar_conf)
        finally:
            os.environ.pop('GIT_SSH', None)
            if orig_git_ssh is not NOTSET:
                os.environ['GIT_SSH'] = orig_git_ssh

    def test_git_pillar_single_source(self):
        '''
        Test using a single ext_pillar repo
        '''
        ret = self.get_pillar('''\
            git_pillar_provider: gitpython
            cachedir: {cachedir}
            extension_modules: {extmods}
            ext_pillar:
              - git:
                - master {url}
            ''')
        self.assertEqual(
            ret,
            {'branch': 'master',
             'mylist': ['master'],
             'mydict': {'master': True,
                        'nested_list': ['master'],
                        'nested_dict': {'master': True}}}
        )

    def test_git_pillar_multiple_sources_master_dev_no_merge_lists(self):
        '''
        Test using two ext_pillar dirs. Since all git_pillar repos are merged
        into a single dictionary, ordering matters.

        This tests with the master branch followed by dev, and with
        pillar_merge_lists disabled.
        '''
        ret = self.get_pillar('''\
            git_pillar_provider: gitpython
            cachedir: {cachedir}
            extension_modules: {extmods}
            pillar_merge_lists: False
            ext_pillar:
              - git:
                - master {url}
                - dev {url}
            ''')
        self.assertEqual(
            ret,
            {'branch': 'dev',
             'mylist': ['dev'],
             'mydict': {'master': True,
                        'dev': True,
                        'nested_list': ['dev'],
                        'nested_dict': {'master': True, 'dev': True}}}
        )

    def test_git_pillar_multiple_sources_dev_master_no_merge_lists(self):
        '''
        Test using two ext_pillar dirs. Since all git_pillar repos are merged
        into a single dictionary, ordering matters.

        This tests with the dev branch followed by master, and with
        pillar_merge_lists disabled.
        '''
        ret = self.get_pillar('''\
            git_pillar_provider: gitpython
            cachedir: {cachedir}
            extension_modules: {extmods}
            pillar_merge_lists: False
            ext_pillar:
              - git:
                - dev {url}
                - master {url}
            ''')
        self.assertEqual(
            ret,
            {'branch': 'master',
             'mylist': ['master'],
             'mydict': {'master': True,
                        'dev': True,
                        'nested_list': ['master'],
                        'nested_dict': {'master': True, 'dev': True}}}
        )

    def test_git_pillar_multiple_sources_master_dev_merge_lists(self):
        '''
        Test using two ext_pillar dirs. Since all git_pillar repos are merged
        into a single dictionary, ordering matters.

        This tests with the master branch followed by dev, and with
        pillar_merge_lists enabled.
        '''
        ret = self.get_pillar('''\
            git_pillar_provider: gitpython
            cachedir: {cachedir}
            extension_modules: {extmods}
            pillar_merge_lists: True
            ext_pillar:
              - git:
                - master {url}
                - dev {url}
            ''')
        self.assertEqual(
            ret,
            {'branch': 'dev',
             'mylist': ['master', 'dev'],
             'mydict': {'master': True,
                        'dev': True,
                        'nested_list': ['master', 'dev'],
                        'nested_dict': {'master': True, 'dev': True}}}
        )

    def test_git_pillar_multiple_sources_dev_master_merge_lists(self):
        '''
        Test using two ext_pillar dirs. Since all git_pillar repos are merged
        into a single dictionary, ordering matters.

        This tests with the dev branch followed by master, and with
        pillar_merge_lists enabled.
        '''
        ret = self.get_pillar('''\
            git_pillar_provider: gitpython
            cachedir: {cachedir}
            extension_modules: {extmods}
            pillar_merge_lists: True
            ext_pillar:
              - git:
                - dev {url}
                - master {url}
            ''')
        self.assertEqual(
            ret,
            {'branch': 'master',
             'mylist': ['dev', 'master'],
             'mydict': {'master': True,
                        'dev': True,
                        'nested_list': ['dev', 'master'],
                        'nested_dict': {'master': True, 'dev': True}}}
        )

    def test_git_pillar_multiple_sources_with_pillarenv(self):
        '''
        Test using pillarenv to restrict results to those from a single branch
        '''
        ret = self.get_pillar('''\
            git_pillar_provider: gitpython
            cachedir: {cachedir}
            extension_modules: {extmods}
            pillarenv: base
            ext_pillar:
              - git:
                - master {url}
                - dev {url}
            ''')
        self.assertEqual(
            ret,
            {'branch': 'master',
             'mylist': ['master'],
             'mydict': {'master': True,
                        'nested_list': ['master'],
                        'nested_dict': {'master': True}}}
        )

    def test_git_pillar_includes_enabled(self):
        '''
        Test with git_pillar_includes enabled. The top_only branch references
        an SLS file from the master branch, so we should see the key from that
        SLS file (included_pillar) in the compiled pillar data.
        '''
        ret = self.get_pillar('''\
            git_pillar_provider: gitpython
            cachedir: {cachedir}
            extension_modules: {extmods}
            ext_pillar:
              - git:
                - master {url}
                - top_only {url}:
                  - env: base
            ''')
        self.assertEqual(
            ret,
            {'branch': 'master',
             'mylist': ['master'],
             'mydict': {'master': True,
                        'nested_list': ['master'],
                        'nested_dict': {'master': True}},
             'included_pillar': True}
        )

    def test_git_pillar_includes_disabled(self):
        '''
        Test with git_pillar_includes enabled. The top_only branch references
        an SLS file from the master branch, but since includes are disabled it
        will not find the SLS file and the "included_pillar" key should not be
        present in the compiled pillar data. We should instead see an error
        message in the compiled data.
        '''
        ret = self.get_pillar('''\
            git_pillar_provider: gitpython
            git_pillar_includes: False
            cachedir: {cachedir}
            extension_modules: {extmods}
            ext_pillar:
              - git:
                - master {url}
                - top_only {url}:
                  - env: base
            ''')
        self.assertEqual(
            ret,
            {'branch': 'master',
             'mylist': ['master'],
             'mydict': {'master': True,
                        'nested_list': ['master'],
                        'nested_dict': {'master': True}},
             '_errors': ["Specified SLS 'bar' in environment 'base' is not "
                         "available on the salt master"]}
        )


@destructiveTest
@skipIf(not salt.utils.which('sshd'), 'sshd not present')
@skipIf(not HAS_PYGIT2, 'pygit2 >= {0} required'.format(PYGIT2_MINVER))
@skipIf(salt.utils.is_windows(), 'minion is windows')
@skip_if_not_root
@skipIf(NO_MOCK, NO_MOCK_REASON)
class TestPygit2SSH(SSHTestBase):
    '''
    Test git_pillar with pygit2 using SSH authentication

    NOTE: Any tests added to this test class should have equivalent tests (if
    possible) in the TestGitPythonSSH class.
    '''
    username = USERNAME
    passphrase = PASSWORD
    sshd_config_dir = tempfile.mkdtemp(dir=TMP)

    def test_git_pillar_single_source(self):
        '''
        Test using a single ext_pillar repo
        '''
        expected = {
            'branch': 'master',
            'mylist': ['master'],
            'mydict': {'master': True,
                       'nested_list': ['master'],
                       'nested_dict': {'master': True}}
        }

        # Test with passphraseless key and global credential options
        ret = self.get_pillar('''\
            git_pillar_provider: pygit2
            git_pillar_pubkey: {pubkey_nopass}
            git_pillar_privkey: {privkey_nopass}
            cachedir: {cachedir}
            extension_modules: {extmods}
            ext_pillar:
              - git:
                - master {url}
            ''')
        self.assertEqual(ret, expected)

        # Test with passphraseless key and per-repo credential options
        ret = self.get_pillar('''\
            git_pillar_provider: pygit2
            cachedir: {cachedir}
            extension_modules: {extmods}
            ext_pillar:
              - git:
                - master {url}:
                  - pubkey: {pubkey_nopass}
                  - privkey: {privkey_nopass}
            ''')
        self.assertEqual(ret, expected)

        # Test with passphrase-protected key and global credential options
        ret = self.get_pillar('''\
            git_pillar_provider: pygit2
            git_pillar_pubkey: {pubkey_withpass}
            git_pillar_privkey: {privkey_withpass}
            git_pillar_passphrase: {passphrase}
            cachedir: {cachedir}
            extension_modules: {extmods}
            ext_pillar:
              - git:
                - master {url}
            ''')
        self.assertEqual(ret, expected)

        # Test with passphrase-protected key and per-repo credential options
        ret = self.get_pillar('''\
            git_pillar_provider: pygit2
            cachedir: {cachedir}
            extension_modules: {extmods}
            ext_pillar:
              - git:
                - master {url}:
                  - pubkey: {pubkey_withpass}
                  - privkey: {privkey_withpass}
                  - passphrase: {passphrase}
            ''')
        self.assertEqual(ret, expected)

    def test_git_pillar_multiple_sources_master_dev_no_merge_lists(self):
        '''
        Test using two ext_pillar dirs. Since all git_pillar repos are merged
        into a single dictionary, ordering matters.

        This tests with the master branch followed by dev, and with
        pillar_merge_lists disabled.
        '''
        expected = {
            'branch': 'dev',
            'mylist': ['dev'],
            'mydict': {'master': True,
                       'dev': True,
                       'nested_list': ['dev'],
                       'nested_dict': {'master': True, 'dev': True}}
        }

        # passphraseless key, global credential options
        ret = self.get_pillar('''\
            git_pillar_provider: pygit2
            git_pillar_pubkey: {pubkey_nopass}
            git_pillar_privkey: {privkey_nopass}
            cachedir: {cachedir}
            extension_modules: {extmods}
            pillar_merge_lists: False
            ext_pillar:
              - git:
                - master {url}
                - dev {url}
            ''')
        self.assertEqual(ret, expected)

        # passphraseless key, per-repo credential options
        ret = self.get_pillar('''\
            git_pillar_provider: pygit2
            cachedir: {cachedir}
            extension_modules: {extmods}
            pillar_merge_lists: False
            ext_pillar:
              - git:
                - master {url}:
                  - pubkey: {pubkey_nopass}
                  - privkey: {privkey_nopass}
                - dev {url}:
                  - pubkey: {pubkey_nopass}
                  - privkey: {privkey_nopass}
            ''')
        self.assertEqual(ret, expected)

        # passphrase-protected key, global credential options
        ret = self.get_pillar('''\
            git_pillar_provider: pygit2
            git_pillar_pubkey: {pubkey_withpass}
            git_pillar_privkey: {privkey_withpass}
            git_pillar_passphrase: {passphrase}
            cachedir: {cachedir}
            extension_modules: {extmods}
            pillar_merge_lists: False
            ext_pillar:
              - git:
                - master {url}
                - dev {url}
            ''')
        self.assertEqual(ret, expected)

        # passphrase-protected key, per-repo credential options
        ret = self.get_pillar('''\
            git_pillar_provider: pygit2
            cachedir: {cachedir}
            extension_modules: {extmods}
            pillar_merge_lists: False
            ext_pillar:
              - git:
                - master {url}:
                  - pubkey: {pubkey_withpass}
                  - privkey: {privkey_withpass}
                  - passphrase: {passphrase}
                - dev {url}:
                  - pubkey: {pubkey_withpass}
                  - privkey: {privkey_withpass}
                  - passphrase: {passphrase}
            ''')
        self.assertEqual(ret, expected)

    def test_git_pillar_multiple_sources_dev_master_no_merge_lists(self):
        '''
        Test using two ext_pillar dirs. Since all git_pillar repos are merged
        into a single dictionary, ordering matters.

        This tests with the dev branch followed by master, and with
        pillar_merge_lists disabled.
        '''
        expected = {
            'branch': 'master',
            'mylist': ['master'],
            'mydict': {'master': True,
                       'dev': True,
                       'nested_list': ['master'],
                       'nested_dict': {'master': True, 'dev': True}}
        }

        # passphraseless key, global credential options
        ret = self.get_pillar('''\
            git_pillar_provider: pygit2
            git_pillar_pubkey: {pubkey_nopass}
            git_pillar_privkey: {privkey_nopass}
            cachedir: {cachedir}
            extension_modules: {extmods}
            pillar_merge_lists: False
            ext_pillar:
              - git:
                - dev {url}
                - master {url}
            ''')
        self.assertEqual(ret, expected)

        # passphraseless key, per-repo credential options
        ret = self.get_pillar('''\
            git_pillar_provider: pygit2
            cachedir: {cachedir}
            extension_modules: {extmods}
            pillar_merge_lists: False
            ext_pillar:
              - git:
                - dev {url}:
                  - pubkey: {pubkey_nopass}
                  - privkey: {privkey_nopass}
                - master {url}:
                  - pubkey: {pubkey_nopass}
                  - privkey: {privkey_nopass}
            ''')
        self.assertEqual(ret, expected)

        # passphrase-protected key, global credential options
        ret = self.get_pillar('''\
            git_pillar_provider: pygit2
            git_pillar_pubkey: {pubkey_withpass}
            git_pillar_privkey: {privkey_withpass}
            git_pillar_passphrase: {passphrase}
            cachedir: {cachedir}
            extension_modules: {extmods}
            pillar_merge_lists: False
            ext_pillar:
              - git:
                - dev {url}
                - master {url}
            ''')
        self.assertEqual(ret, expected)

        # passphrase-protected key, per-repo credential options
        ret = self.get_pillar('''\
            git_pillar_provider: pygit2
            cachedir: {cachedir}
            extension_modules: {extmods}
            pillar_merge_lists: False
            ext_pillar:
              - git:
                - dev {url}:
                  - pubkey: {pubkey_withpass}
                  - privkey: {privkey_withpass}
                  - passphrase: {passphrase}
                - master {url}:
                  - pubkey: {pubkey_withpass}
                  - privkey: {privkey_withpass}
                  - passphrase: {passphrase}
            ''')
        self.assertEqual(ret, expected)

    def test_git_pillar_multiple_sources_master_dev_merge_lists(self):
        '''
        Test using two ext_pillar dirs. Since all git_pillar repos are merged
        into a single dictionary, ordering matters.

        This tests with the master branch followed by dev, and with
        pillar_merge_lists enabled.
        '''
        expected = {
            'branch': 'dev',
            'mylist': ['master', 'dev'],
            'mydict': {'master': True,
                       'dev': True,
                       'nested_list': ['master', 'dev'],
                       'nested_dict': {'master': True, 'dev': True}}
        }

        # passphraseless key, global credential options
        ret = self.get_pillar('''\
            git_pillar_provider: pygit2
            git_pillar_pubkey: {pubkey_nopass}
            git_pillar_privkey: {privkey_nopass}
            cachedir: {cachedir}
            extension_modules: {extmods}
            pillar_merge_lists: True
            ext_pillar:
              - git:
                - master {url}
                - dev {url}
            ''')
        self.assertEqual(ret, expected)

        # passphraseless key, per-repo credential options
        ret = self.get_pillar('''\
            git_pillar_provider: pygit2
            cachedir: {cachedir}
            extension_modules: {extmods}
            pillar_merge_lists: True
            ext_pillar:
              - git:
                - master {url}:
                  - pubkey: {pubkey_nopass}
                  - privkey: {privkey_nopass}
                - dev {url}:
                  - pubkey: {pubkey_nopass}
                  - privkey: {privkey_nopass}
            ''')
        self.assertEqual(ret, expected)

        # passphrase-protected key, global credential options
        ret = self.get_pillar('''\
            git_pillar_provider: pygit2
            git_pillar_pubkey: {pubkey_withpass}
            git_pillar_privkey: {privkey_withpass}
            git_pillar_passphrase: {passphrase}
            cachedir: {cachedir}
            extension_modules: {extmods}
            pillar_merge_lists: True
            ext_pillar:
              - git:
                - master {url}
                - dev {url}
            ''')
        self.assertEqual(ret, expected)

        # passphrase-protected key, per-repo credential options
        ret = self.get_pillar('''\
            git_pillar_provider: pygit2
            cachedir: {cachedir}
            extension_modules: {extmods}
            pillar_merge_lists: True
            ext_pillar:
              - git:
                - master {url}:
                  - pubkey: {pubkey_withpass}
                  - privkey: {privkey_withpass}
                  - passphrase: {passphrase}
                - dev {url}:
                  - pubkey: {pubkey_withpass}
                  - privkey: {privkey_withpass}
                  - passphrase: {passphrase}
            ''')
        self.assertEqual(ret, expected)

    def test_git_pillar_multiple_sources_dev_master_merge_lists(self):
        '''
        Test using two ext_pillar dirs. Since all git_pillar repos are merged
        into a single dictionary, ordering matters.

        This tests with the dev branch followed by master, and with
        pillar_merge_lists enabled.
        '''
        expected = {
            'branch': 'master',
            'mylist': ['dev', 'master'],
            'mydict': {'master': True,
                       'dev': True,
                       'nested_list': ['dev', 'master'],
                       'nested_dict': {'master': True, 'dev': True}}
        }

        # passphraseless key, global credential options
        ret = self.get_pillar('''\
            git_pillar_provider: pygit2
            git_pillar_pubkey: {pubkey_nopass}
            git_pillar_privkey: {privkey_nopass}
            cachedir: {cachedir}
            extension_modules: {extmods}
            pillar_merge_lists: True
            ext_pillar:
              - git:
                - dev {url}
                - master {url}
            ''')
        self.assertEqual(ret, expected)

        # passphraseless key, per-repo credential options
        ret = self.get_pillar('''\
            git_pillar_provider: pygit2
            cachedir: {cachedir}
            extension_modules: {extmods}
            pillar_merge_lists: True
            ext_pillar:
              - git:
                - dev {url}:
                  - pubkey: {pubkey_nopass}
                  - privkey: {privkey_nopass}
                - master {url}:
                  - pubkey: {pubkey_nopass}
                  - privkey: {privkey_nopass}
            ''')
        self.assertEqual(ret, expected)

        # passphrase-protected key, global credential options
        ret = self.get_pillar('''\
            git_pillar_provider: pygit2
            git_pillar_pubkey: {pubkey_withpass}
            git_pillar_privkey: {privkey_withpass}
            git_pillar_passphrase: {passphrase}
            cachedir: {cachedir}
            extension_modules: {extmods}
            pillar_merge_lists: True
            ext_pillar:
              - git:
                - dev {url}
                - master {url}
            ''')
        self.assertEqual(ret, expected)

        # passphrase-protected key, per-repo credential options
        ret = self.get_pillar('''\
            git_pillar_provider: pygit2
            cachedir: {cachedir}
            extension_modules: {extmods}
            pillar_merge_lists: True
            ext_pillar:
              - git:
                - dev {url}:
                  - pubkey: {pubkey_withpass}
                  - privkey: {privkey_withpass}
                  - passphrase: {passphrase}
                - master {url}:
                  - pubkey: {pubkey_withpass}
                  - privkey: {privkey_withpass}
                  - passphrase: {passphrase}
            ''')
        self.assertEqual(ret, expected)

    def test_git_pillar_multiple_sources_with_pillarenv(self):
        '''
        Test using pillarenv to restrict results to those from a single branch
        '''
        expected = {
            'branch': 'master',
            'mylist': ['master'],
            'mydict': {'master': True,
                       'nested_list': ['master'],
                       'nested_dict': {'master': True}}
        }

        # Test with passphraseless key and global credential options
        ret = self.get_pillar('''\
            git_pillar_provider: pygit2
            git_pillar_pubkey: {pubkey_nopass}
            git_pillar_privkey: {privkey_nopass}
            cachedir: {cachedir}
            extension_modules: {extmods}
            pillarenv: base
            ext_pillar:
              - git:
                - master {url}
                - dev {url}
            ''')
        self.assertEqual(ret, expected)

        # Test with passphraseless key and per-repo credential options
        ret = self.get_pillar('''\
            git_pillar_provider: pygit2
            cachedir: {cachedir}
            extension_modules: {extmods}
            pillarenv: base
            ext_pillar:
              - git:
                - master {url}:
                  - pubkey: {pubkey_nopass}
                  - privkey: {privkey_nopass}
                - dev {url}:
                  - pubkey: {pubkey_nopass}
                  - privkey: {privkey_nopass}
            ''')
        self.assertEqual(ret, expected)

        # Test with passphrase-protected key and global credential options
        ret = self.get_pillar('''\
            git_pillar_provider: pygit2
            git_pillar_pubkey: {pubkey_withpass}
            git_pillar_privkey: {privkey_withpass}
            git_pillar_passphrase: {passphrase}
            cachedir: {cachedir}
            extension_modules: {extmods}
            pillarenv: base
            ext_pillar:
              - git:
                - master {url}
                - dev {url}
            ''')
        self.assertEqual(ret, expected)

        # Test with passphrase-protected key and per-repo credential options
        ret = self.get_pillar('''\
            git_pillar_provider: pygit2
            cachedir: {cachedir}
            extension_modules: {extmods}
            pillarenv: base
            ext_pillar:
              - git:
                - master {url}:
                  - pubkey: {pubkey_withpass}
                  - privkey: {privkey_withpass}
                  - passphrase: {passphrase}
                - dev {url}:
                  - pubkey: {pubkey_nopass}
                  - privkey: {privkey_nopass}
                  - passphrase: {passphrase}
            ''')
        self.assertEqual(ret, expected)

    def test_git_pillar_includes_enabled(self):
        '''
        Test with git_pillar_includes enabled. The top_only branch references
        an SLS file from the master branch, so we should see the
        "included_pillar" key from that SLS file in the compiled pillar data.
        '''
        expected = {
            'branch': 'master',
            'mylist': ['master'],
            'mydict': {'master': True,
                       'nested_list': ['master'],
                       'nested_dict': {'master': True}},
            'included_pillar': True
        }

        # passphraseless key, global credential options
        ret = self.get_pillar('''\
            git_pillar_provider: pygit2
            git_pillar_pubkey: {pubkey_nopass}
            git_pillar_privkey: {privkey_nopass}
            cachedir: {cachedir}
            extension_modules: {extmods}
            ext_pillar:
              - git:
                - master {url}
                - top_only {url}:
                  - env: base
            ''')
        self.assertEqual(ret, expected)

        # passphraseless key, per-repo credential options
        ret = self.get_pillar('''\
            git_pillar_provider: pygit2
            cachedir: {cachedir}
            extension_modules: {extmods}
            ext_pillar:
              - git:
                - master {url}:
                  - pubkey: {pubkey_nopass}
                  - privkey: {privkey_nopass}
                - top_only {url}:
                  - pubkey: {pubkey_nopass}
                  - privkey: {privkey_nopass}
                  - env: base
            ''')
        self.assertEqual(ret, expected)

        # passphrase-protected key, global credential options
        ret = self.get_pillar('''\
            git_pillar_provider: pygit2
            git_pillar_pubkey: {pubkey_withpass}
            git_pillar_privkey: {privkey_withpass}
            git_pillar_passphrase: {passphrase}
            cachedir: {cachedir}
            extension_modules: {extmods}
            ext_pillar:
              - git:
                - master {url}
                - top_only {url}:
                  - env: base
            ''')
        self.assertEqual(ret, expected)

        # passphrase-protected key, per-repo credential options
        ret = self.get_pillar('''\
            git_pillar_provider: pygit2
            cachedir: {cachedir}
            extension_modules: {extmods}
            ext_pillar:
              - git:
                - master {url}:
                  - pubkey: {pubkey_withpass}
                  - privkey: {privkey_withpass}
                  - passphrase: {passphrase}
                - top_only {url}:
                  - pubkey: {pubkey_withpass}
                  - privkey: {privkey_withpass}
                  - passphrase: {passphrase}
                  - env: base
            ''')
        self.assertEqual(ret, expected)

    def test_git_pillar_includes_disabled(self):
        '''
        Test with git_pillar_includes enabled. The top_only branch references
        an SLS file from the master branch, but since includes are disabled it
        will not find the SLS file and the "included_pillar" key should not be
        present in the compiled pillar data. We should instead see an error
        message in the compiled data.
        '''
        expected = {
            'branch': 'master',
            'mylist': ['master'],
            'mydict': {'master': True,
                       'nested_list': ['master'],
                       'nested_dict': {'master': True}},
            '_errors': ["Specified SLS 'bar' in environment 'base' is not "
                        "available on the salt master"]
        }

        # passphraseless key, global credential options
        ret = self.get_pillar('''\
            git_pillar_provider: pygit2
            git_pillar_includes: False
            git_pillar_pubkey: {pubkey_nopass}
            git_pillar_privkey: {privkey_nopass}
            cachedir: {cachedir}
            extension_modules: {extmods}
            ext_pillar:
              - git:
                - master {url}
                - top_only {url}:
                  - env: base
            ''')
        self.assertEqual(ret, expected)

        # passphraseless key, per-repo credential options
        ret = self.get_pillar('''\
            git_pillar_provider: pygit2
            git_pillar_includes: False
            cachedir: {cachedir}
            extension_modules: {extmods}
            ext_pillar:
              - git:
                - master {url}:
                  - pubkey: {pubkey_nopass}
                  - privkey: {privkey_nopass}
                - top_only {url}:
                  - pubkey: {pubkey_nopass}
                  - privkey: {privkey_nopass}
                  - env: base
            ''')
        self.assertEqual(ret, expected)

        # passphrase-protected key, global credential options
        ret = self.get_pillar('''\
            git_pillar_provider: pygit2
            git_pillar_includes: False
            git_pillar_pubkey: {pubkey_withpass}
            git_pillar_privkey: {privkey_withpass}
            git_pillar_passphrase: {passphrase}
            cachedir: {cachedir}
            extension_modules: {extmods}
            ext_pillar:
              - git:
                - master {url}
                - top_only {url}:
                  - env: base
            ''')
        self.assertEqual(ret, expected)

        # passphrase-protected key, per-repo credential options
        ret = self.get_pillar('''\
            git_pillar_provider: pygit2
            git_pillar_includes: False
            cachedir: {cachedir}
            extension_modules: {extmods}
            ext_pillar:
              - git:
                - master {url}:
                  - pubkey: {pubkey_withpass}
                  - privkey: {privkey_withpass}
                  - passphrase: {passphrase}
                - top_only {url}:
                  - pubkey: {pubkey_withpass}
                  - privkey: {privkey_withpass}
                  - passphrase: {passphrase}
                  - env: base
            ''')
        self.assertEqual(ret, expected)


@skipIf(not HAS_GITPYTHON, 'GitPython >= {0} required'.format(GITPYTHON_MINVER))
@skipIf(salt.utils.is_windows(), 'minion is windows')
@skip_if_not_root
@skipIf(NO_MOCK, NO_MOCK_REASON)
class TestGitPythonHTTP(HTTPTestBase):
    '''
    Test git_pillar with GitPython using unauthenticated HTTP

    NOTE: Tests will have to wait until later for this, as the current method
    set up in tests.support.git_pillar uses a tornado webserver, and to serve
    Git over HTTP the setup needs to be a bit more complicated as we need the
    webserver to forward the request to git on the "remote" server.
    '''
    username = USERNAME
    password = PASSWORD
    root_dir = tempfile.mkdtemp(dir=TMP)


class TestGitPythonAuthenticatedHTTP(TestGitPythonHTTP):
    '''
    Since GitPython doesn't support passing credentials, we can test
    authenticated GitPython by encoding the username:password pair into the
    repository's URL. The configuration will otherwise remain the same, so we
    can reuse all of the tests from TestGitPythonHTTP.

    The same cannot be done for pygit2 however, since using authentication
    requires that specific params are set in the YAML config, so the YAML we
    use to drive the tests will be significantly different for authenticated
    repositories.
    '''
    root_dir = tempfile.mkdtemp(dir=TMP)

    @classmethod
    def setUpClass(cls):
        '''
        Create start the webserver
        '''
        super(TestGitPythonAuthenticatedHTTP, cls).setUpClass()
        # Override the URL set up in the parent class
        cls.url = 'http://{username}:{password}@127.0.0.1:{port}/repo.git'.format(
            username=cls.username,
            password=cls.password,
            port=cls.port)
        cls.ext_opts['url'] = cls.url

    @classmethod
    def create_webserver(cls):
        '''
        Use HTTPBasicAuthHandler to force an auth prompt for these tests
        '''
        if cls.root_dir is None:
            raise Exception('root_dir not defined in test class')
        return Webserver(root=cls.root_dir, port=cls.port,
                         handler=HTTPBasicAuthHandler)
