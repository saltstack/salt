# -*- coding: utf-8 -*-

import shutil
import subprocess
import tempfile

# Import Salt Testing libs
from salttesting.helpers import ensure_in_syspath
ensure_in_syspath('../../')

# Import salt libs
import integration


class GitModuleTest(integration.ModuleCase):
    @classmethod
    def setUpClass(self):
        from salt.utils import which
        git = which('git')
        if not git:
            self.skipTest('The git binary is not available')


    def setUp(self):
        self.repos = tempfile.mkdtemp(dir=integration.TMP)
        self.addCleanup(shutil.rmtree, self.repos, ignore_errors=True)
        subprocess.check_call(['git', 'init', '--quiet', self.repos])


    def test_config_set_value_has_space_characters(self):
        '''
        git.config_set
        '''
        config_key = "user.name"
        config_value = "foo bar"

        ret = self.run_function(
            'git.config_set',
            cwd=self.repos,
            setting_name=config_key,
            setting_value=config_value,
        )
        self.assertEqual("", ret)

        output = subprocess.check_output(
            ['git', 'config', '--local', config_key],
            cwd=self.repos)

        self.assertEqual(config_value + "\n", output)
