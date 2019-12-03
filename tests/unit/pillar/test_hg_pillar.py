# -*- coding: utf-8 -*-
'''test for pillar hg_pillar.py'''

# Import python libs
from __future__ import absolute_import, print_function, unicode_literals

import os
import tempfile
import shutil
import subprocess

# Import Salt Testing libs
from tests.support.mixins import AdaptedConfigurationTestCaseMixin, LoaderModuleMockMixin
from tests.support.unit import TestCase, skipIf
from tests.support.mock import NO_MOCK, NO_MOCK_REASON
from tests.support.paths import TMP


COMMIT_USER_NAME = 'test_user'
# file contents
PILLAR_CONTENT = {'gna': 'hello'}
FILE_DATA = {
    'top.sls': {'base': {'*': ['user']}},
    'user.sls': PILLAR_CONTENT
}

# Import Salt Libs
import salt.utils.files
import salt.utils.yaml
import salt.pillar.hg_pillar as hg_pillar
HGLIB = hg_pillar.hglib


@skipIf(NO_MOCK, NO_MOCK_REASON)
@skipIf(HGLIB is None, 'python-hglib library not installed')
class HgPillarTestCase(TestCase, AdaptedConfigurationTestCaseMixin, LoaderModuleMockMixin):
    'test hg_pillar pillar'
    maxDiff = None

    def setup_loader_modules(self):
        self.tmpdir = tempfile.mkdtemp(dir=TMP)
        self.addCleanup(shutil.rmtree, self.tmpdir)
        cachedir = os.path.join(self.tmpdir, 'cachedir')
        os.makedirs(os.path.join(cachedir, 'hg_pillar'))
        self.hg_repo_path = self._create_hg_repo()
        return {
            hg_pillar: {
                '__opts__':  {
                    'cachedir': cachedir,
                    'pillar_roots': {},
                    'file_roots': {},
                    'state_top': 'top.sls',
                    'extension_modules': '',
                    'renderer': 'yaml_jinja',
                    'pillar_opts': False,
                    'renderer_blacklist': [],
                    'renderer_whitelist': [],
                    'file_ignore_glob': [],
                    'file_ignore_regex': [],
                }
            }
        }

    def _create_hg_repo(self):
        'create repo in tempdir'
        hg_repo = os.path.join(self.tmpdir, 'repo_pillar')
        os.makedirs(hg_repo)
        subprocess.check_call(['hg', 'init', hg_repo])
        for filename in FILE_DATA:
            with salt.utils.files.fopen(os.path.join(hg_repo, filename), 'w') as data_file:
                salt.utils.yaml.safe_dump(FILE_DATA[filename], data_file)
        subprocess.check_call(['hg', 'ci', '-A', '-R', hg_repo, '-m', 'first commit', '-u', COMMIT_USER_NAME])
        return hg_repo

    def test_base(self):
        'check hg repo is imported correctly'
        mypillar = hg_pillar.ext_pillar('*', None, 'file://{0}'.format(self.hg_repo_path))
        self.assertEqual(PILLAR_CONTENT, mypillar)
