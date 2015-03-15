# -*- coding: utf-8 -*-
'''test for pillar git_pillar.py'''

# Import python libs
from __future__ import absolute_import

import os
import tempfile
import shutil
import subprocess
import yaml

# Import Salt Testing libs
from salttesting import TestCase, skipIf
from salttesting.mock import NO_MOCK, NO_MOCK_REASON

import integration

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
@skipIf(not git_pillar.HAS_GIT, 'no GitPython')
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
                'file_roots': {},
                'state_top': 'top.sls',
                'extension_modules': '',
                'renderer': 'yaml_jinja',
                'pillar_opts': False
                }
        git_pillar.__grains__ = {}

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
    def repo_url(self):
        return 'file://{0}'.format(self.repo_path)

    def test_base(self):
        'check git repo pillar data is imported correctly'
        mypillar = git_pillar.ext_pillar('*', None, self.repo_url)
        self.assertEqual(PILLAR_CONTENT, mypillar)

    def test_from_upper(self):
        '''Check whole calling stack from parent Pillar instance

        This test is closer to what happens in real life, and demonstrates
        how ``compile_pillar()`` is called twice.

        GR: this kind of test should become non-necessary, once git_pillar,
        hg_pillar and the like don't instantiate a pillar object themselves
        (and risk a loop condition)
        '''
        git_pillar.__opts__['ext_pillar'] = [
            dict(git='master {0}'.format(self.repo_url))]
        pil = Pillar(git_pillar.__opts__, git_pillar.__grains__,
                     'myminon', 'base')
        self.assertEqual(PILLAR_CONTENT, pil.compile_pillar())

    def xtest_loop(self):
        '''Check whole calling stack from parent Pillar instance

        This test is closer to what happens in real life, and demonstrates
        how ``compile_pillar()`` is called twice.

        GR: this kind of test should become non-necessary, once git_pillar,
        hg_pillar and the like don't instantiate a pillar object themselves
        (and risk a loop condition)
        '''
        hg_repo2 = os.path.join(self.tmpdir, 'repo_pillar2')
        hg_repo_url2 = 'file://{0}'.format(hg_repo2)
        subprocess.check_call(['hg', 'clone', self.hg_repo_path, hg_repo2])
        hg_pillar.__opts__['ext_pillar'] = [dict(hg=self.hg_repo_url),
                                            dict(hg=hg_repo_url2),
                                        ]
        pil = Pillar(hg_pillar.__opts__, hg_pillar.__grains__,
                     'myminon', 'base')
        self.assertEqual(PILLAR_CONTENT, pil.compile_pillar())
