# -*- coding: utf-8 -*-

# Import Python Libs
import shutil
import subprocess
import tempfile

# Import Salt Testing libs
from salttesting.helpers import ensure_in_syspath
ensure_in_syspath('../../')

# Import salt libs
import integration


class GitModuleTest(integration.ModuleCase):
    '''
    Integration tests for the git module
    '''

    @classmethod
    def setUpClass(cls):
        '''
        Check if git is installed. If it isn't, skip everything in this class.
        '''
        from salt.utils import which
        git = which('git')
        if not git:
            cls.skipTest('The git binary is not available')

    def setUp(self):
        self.repos = tempfile.mkdtemp(dir=integration.TMP)
        self.addCleanup(shutil.rmtree, self.repos, ignore_errors=True)
        subprocess.check_call(['git', 'init', '--quiet', self.repos])

    def test_config_set_value_has_space_characters(self):
        '''
        Tests the git.config_set function
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
