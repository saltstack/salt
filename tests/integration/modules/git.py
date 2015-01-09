# -*- coding: utf-8 -*-

# Import Python Libs
import shutil
import subprocess
import tempfile

# Import Salt Testing libs
from salttesting.helpers import ensure_in_syspath, skip_if_binaries_missing
ensure_in_syspath('../..')

# Import salt libs
import integration


@skip_if_binaries_missing('git')
class GitModuleTest(integration.ModuleCase):

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
