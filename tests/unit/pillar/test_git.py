# -*- coding: utf-8 -*-
'''test for pillar git_pillar.py


  :codeauthor: :email:`Georges Racinet (gracinet@anybox.fr)`

Based on joint work with Paul Tonelli about hg_pillar integration.

'''

# Import python libs
from __future__ import absolute_import

import os
import tempfile
import shutil
import subprocess
import yaml

# Import Salt Testing libs
from tests.support.unit import TestCase, skipIf
from tests.support.mock import NO_MOCK, NO_MOCK_REASON

import tests.integration as integration

COMMIT_USER_NAME = 'test_user'
COMMIT_USER_EMAIL = 'someone@git.test'
# file contents
PILLAR_CONTENT = {'gna': 'hello'}
FILE_DATA = {
             'top.sls': {'base': {'*': ['user']}},
             'user.sls': PILLAR_CONTENT
             }

# Import Salt Libs
from salt.pillar import Pillar, git_pillar


@skipIf(NO_MOCK, NO_MOCK_REASON)
@skipIf(not git_pillar.HAS_GITPYTHON, 'no GitPython')
class GitPillarTestCase(TestCase, integration.AdaptedConfigurationTestCaseMixIn):
    'test git_pillar pillar'
    maxDiff = None

    def setUp(self):
        super(GitPillarTestCase, self).setUp()
        self.tmpdir = tempfile.mkdtemp(dir=integration.SYS_TMP_DIR)
        cachedir = os.path.join(self.tmpdir, 'cachedir')
        os.makedirs(os.path.join(cachedir, 'pillar_gitfs'))
        self.repo_path = self._create_repo()
        git_pillar.__opts__ = {
                'cachedir': cachedir,
                'pillar_roots': {},
                'hash_type': 'sha256',
                'file_roots': {},
                'state_top': 'top.sls',
                'extension_modules': '',
                'renderer': 'yaml_jinja',
                'renderer_blacklist': [],
                'renderer_whitelist': [],
                'pillar_opts': False
                }
        git_pillar.__grains__ = {}
        git_pillar._update('master', 'file://{0}'.format(self.repo_path))

    def tearDown(self):
        shutil.rmtree(self.tmpdir)
        super(GitPillarTestCase, self).tearDown()

    def _create_repo(self):
        'create source Git repo in temp directory'
        repo = os.path.join(self.tmpdir, 'repo_pillar')
        os.makedirs(repo)
        subprocess.check_call(["git", "init", repo])
        for filename in FILE_DATA:
            with open(os.path.join(repo, filename), 'w') as data_file:
                yaml.dump(FILE_DATA[filename], data_file)

        subprocess.check_call(['git', 'add', '.'], cwd=repo)
        subprocess.call(['git', 'config', 'user.email', COMMIT_USER_EMAIL],
                        cwd=repo)
        subprocess.call(['git', 'config', 'user.name', COMMIT_USER_NAME],
                        cwd=repo)
        subprocess.check_call(['git', 'commit', '-m', 'first commit'],
                              cwd=repo)
        return repo

    @property
    def conf_line(self):
        return 'master file://{0}'.format(self.repo_path)

    def test_base(self):
        'check direct call ``ext_pillar()`` interface'
        git_pillar.__opts__['environment'] = None
        mypillar = git_pillar.ext_pillar('myminion',
                                         self.conf_line,
                                         {})
        self.assertEqual(PILLAR_CONTENT, mypillar)

    def test_from_upper(self):
        '''Check whole calling stack from parent Pillar instance

        This test is closer to what happens in real life, and demonstrates
        how ``compile_pillar()`` is called twice.

        This kind of test should/would become non-necessary, once git_pillar,
        all these pillar are called exactly in the same way (git is an
        exception for now), and don't recurse.
        '''
        git_pillar.__opts__['ext_pillar'] = [
            dict(git=self.conf_line)
        ]
        pil = Pillar(git_pillar.__opts__,
                     git_pillar.__grains__,
                     'myminion', None)
        self.assertEqual(PILLAR_CONTENT, pil.compile_pillar(pillar_dirs={}))

    def test_no_loop(self):
        '''Check that the reinstantiation of a pillar object does recurse.

        This test goes in great details of patching that the dedicated
        utilities might do in a simpler way.
        Namely, we replace the main ``ext_pillar`` entry function by one
        that keeps count of its calls.

        Otherwise, the fact that the :class:`MaximumRecursion` error is caught
        can go in the way on the testing.

        On the current code base, this test fails if the two first lines of
        :func:``git_pillar.ext_pillar`::

            if pillar_dirs is None:
                return

        are replaced by::

            if pillar_dirs is None:
                pillar_dirs = {}

        .. note:: the explicit anti-recursion protection does not prevent
                  looping between two different Git pillars.

        This test will help subsequent refactors, and also as a base for other
        external pillars of the same kind.
        '''
        repo2 = os.path.join(self.tmpdir, 'repo_pillar2')
        conf_line2 = 'master file://{0}'.format(repo2)
        subprocess.check_call(['git', 'clone', self.repo_path, repo2])
        git_pillar.__opts__['ext_pillar'] = [
            dict(git=self.conf_line),
            dict(git=conf_line2),
        ]
        git_pillar._update(*conf_line2.split(None, 1))

        pil = Pillar(git_pillar.__opts__,
                     git_pillar.__grains__,
                     'myminion', 'base')

        orig_ext_pillar = pil.ext_pillars['git']
        orig_ext_pillar.count = 0

        def ext_pillar_count_calls(minion_id, repo_string, pillar_dirs):
            orig_ext_pillar.count += 1
            if orig_ext_pillar.count > 6:
                # going all the way to an infinite loop is harsh on the
                # test machine
                raise RuntimeError("Infinite loop detected")
            return orig_ext_pillar(minion_id, repo_string, pillar_dirs)

        from salt.loader import LazyLoader
        orig_getitem = LazyLoader.__getitem__

        def __getitem__(self, key):
            if key == 'git.ext_pillar':
                return ext_pillar_count_calls
            return orig_getitem(self, key)

        try:
            LazyLoader.__getitem__ = __getitem__
            self.assertEqual(PILLAR_CONTENT, pil.compile_pillar(pillar_dirs={}))
            self.assertTrue(orig_ext_pillar.count < 7)
        finally:
            LazyLoader.__getitem__ = orig_getitem
