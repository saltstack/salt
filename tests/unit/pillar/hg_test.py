# -*- coding: utf-8 -*-
'''test for pillar hg_pillar.py'''

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
# file contents
PILLAR_CONTENT = {'gna': 'hello'}
FILE_DATA = {
             'top.sls': {'base': {'*': ['user']}},
             'user.sls': PILLAR_CONTENT
             }

# Import Salt Libs
from salt.pillar import hg_pillar
HGLIB = hg_pillar.hglib


@skipIf(NO_MOCK, NO_MOCK_REASON)
@skipIf(HGLIB is None, 'python-hglib no')
class HgPillarTestCase(TestCase, integration.AdaptedConfigurationTestCaseMixIn):
    'test hg_pillar pillar'
    maxDiff = None

    def setUp(self):
        super(HgPillarTestCase, self).setUp()
        self.tmpdir = tempfile.mkdtemp(dir=integration.SYS_TMP_DIR)
        cachedir = os.path.join(self.tmpdir, 'cachedir')
        os.makedirs(os.path.join(cachedir, 'hg_pillar'))
        self.hg_repo_path = self._create_hg_repo()
        hg_pillar.__opts__ = {
                'cachedir': cachedir,
                'pillar_roots': {},
                'file_roots': {},
                'state_top': 'top.sls',
                'extension_modules': '',
                'renderer': 'yaml_jinja',
                'pillar_opts': False
                }
        hg_pillar.__grains__ = {}

    def tearDown(self):
        shutil.rmtree(self.tmpdir)
        super(HgPillarTestCase, self).tearDown()

    def _create_hg_repo(self):
        'create repo in tempdir'
        hg_repo = os.path.join(self.tmpdir, 'repo_pillar')
        os.makedirs(hg_repo)
        subprocess.check_call(["hg", "init", hg_repo])
        for filename in FILE_DATA:
            with open(os.path.join(hg_repo, filename), 'w') as data_file:
                yaml.dump(FILE_DATA[filename], data_file)
        subprocess.check_call(['hg', 'ci', '-A', '-R', hg_repo, '-m', 'first commit', '-u', COMMIT_USER_NAME])
        return hg_repo

    def test_base(self):
        'check hg repo is imported correctly'
        mypillar = hg_pillar.ext_pillar('*', None, 'file://{0}'.format(self.hg_repo_path))
        self.assertEqual(PILLAR_CONTENT, mypillar)
