# -*- coding: utf-8 -*-
'''
    :codeauthor: :email:`Erik Johnson <erik@saltstack.com>`
'''

# Import Python libs
from __future__ import absolute_import
import shutil
import tempfile
import textwrap
import yaml

try:
    import git  # pylint: disable=unused-import
    HAS_GITPYTHON = True
except ImportError:
    HAS_GITPYTHON = False

# Import Salt Testing Libs
from tests.support.unit import TestCase, skipIf

import tests.integration as integration

# Import salt libs
import salt.utils.gitfs
from salt.fileserver.gitfs import PER_REMOTE_OVERRIDES, PER_REMOTE_ONLY


@skipIf(not HAS_GITPYTHON, 'GitPython is not installed')
class GitfsConfigTestCase(TestCase):

    def setUp(self):
        self.tmp_cachedir = tempfile.mkdtemp(dir=integration.TMP)
        self.opts = {
            '__role': 'master',
            'cachedir': self.tmp_cachedir,
            'fileserver_backend': ['git'],
            'gitfs_provider': 'gitpython',
            'gitfs_mountpoint': '',
            'gitfs_root': 'salt',
            'gitfs_base': 'master',
            'gitfs_user': '',
            'gitfs_password': '',
            'gitfs_insecure_auth': False,
            'gitfs_privkey': '',
            'gitfs_pubkey': '',
            'gitfs_passphrase': '',
            'gitfs_env_whitelist': [],
            'gitfs_env_blacklist': [],
            'gitfs_global_lock': True,
            'gitfs_ssl_verify': True,
            'gitfs_saltenv': [],
            'gitfs_refspecs': ['+refs/heads/*:refs/remotes/origin/*',
                               '+refs/tags/*:refs/tags/*'],
        }

    def tearDown(self):
        shutil.rmtree(self.tmp_cachedir)

    def test_per_saltenv_config(self):
        opts = textwrap.dedent('''
            gitfs_saltenv:
              - baz:
                # when loaded, the "salt://" prefix will be removed
                - mountpoint: salt://baz_mountpoint
                - ref: baz_branch
                - root: baz_root

            gitfs_remotes:

              - file://tmp/repo1:
                - saltenv:
                  - foo:
                    - ref: foo_branch
                    - root: foo_root

              - file://tmp/repo2:
                - mountpoint: repo2
                - saltenv:
                  - baz:
                    - mountpoint: abc
        ''')
        self.opts.update(yaml.safe_load(opts))
        gitfs = salt.utils.gitfs.GitFS(self.opts)
        gitfs.init_remotes(self.opts['gitfs_remotes'],
                           PER_REMOTE_OVERRIDES, PER_REMOTE_ONLY)

        # repo1 (branch: foo)
        # The mountpoint should take the default (from gitfs_mountpoint), while
        # ref and root should take the per-saltenv params.
        self.assertEqual(gitfs.remotes[0].mountpoint('foo'), '')
        self.assertEqual(gitfs.remotes[0].ref('foo'), 'foo_branch')
        self.assertEqual(gitfs.remotes[0].root('foo'), 'foo_root')

        # repo1 (branch: bar)
        # The 'bar' branch does not have a per-saltenv configuration set, so
        # each of the below values should fall back to global values.
        self.assertEqual(gitfs.remotes[0].mountpoint('bar'), '')
        self.assertEqual(gitfs.remotes[0].ref('bar'), 'bar')
        self.assertEqual(gitfs.remotes[0].root('bar'), 'salt')

        # repo1 (branch: baz)
        # The 'baz' branch does not have a per-saltenv configuration set, but
        # it is defined in the gitfs_saltenv parameter, so the values
        # from that parameter should be returned.
        self.assertEqual(gitfs.remotes[0].mountpoint('baz'), 'baz_mountpoint')
        self.assertEqual(gitfs.remotes[0].ref('baz'), 'baz_branch')
        self.assertEqual(gitfs.remotes[0].root('baz'), 'baz_root')

        # repo2 (branch: foo)
        # The mountpoint should take the per-remote mountpoint value of
        # 'repo2', while ref and root should fall back to global values.
        self.assertEqual(gitfs.remotes[1].mountpoint('foo'), 'repo2')
        self.assertEqual(gitfs.remotes[1].ref('foo'), 'foo')
        self.assertEqual(gitfs.remotes[1].root('foo'), 'salt')

        # repo2 (branch: bar)
        # The 'bar' branch does not have a per-saltenv configuration set, so
        # the mountpoint should take the per-remote mountpoint value of
        # 'repo2', while ref and root should fall back to global values.
        self.assertEqual(gitfs.remotes[1].mountpoint('bar'), 'repo2')
        self.assertEqual(gitfs.remotes[1].ref('bar'), 'bar')
        self.assertEqual(gitfs.remotes[1].root('bar'), 'salt')

        # repo2 (branch: baz)
        # The 'baz' branch has the mountpoint configured as a per-saltenv
        # parameter. The other two should take the values defined in
        # gitfs_saltenv.
        self.assertEqual(gitfs.remotes[1].mountpoint('baz'), 'abc')
        self.assertEqual(gitfs.remotes[1].ref('baz'), 'baz_branch')
        self.assertEqual(gitfs.remotes[1].root('baz'), 'baz_root')
