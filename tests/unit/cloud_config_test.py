# -*- coding: utf-8 -*-\
'''
    unit.cloud_config_test
    ~~~~~~~~~~~~~~~~~~~~~~

    Configuration related unit testing

    :codeauthor: :email:`Pedro Algarvio (pedro@algarvio.me)`
    :copyright: © 2013 by the SaltStack Team, see AUTHORS for more details.
    :license: Apache 2.0, see LICENSE for more details.
'''

# Import python libs
import os
import shutil
import tempfile

# Import 3rd-party libs
import yaml

# Import salt testing libs
from salttesting import TestCase
from salttesting.helpers import ensure_in_syspath
ensure_in_syspath('../')

# Import salt libs
import salt.utils
import integration
from salt import config as cloudconfig


class CloudConfigTestCase(TestCase):

    def test_load_cloud_config_from_environ_var(self):
        original_environ = os.environ.copy()

        tempdir = tempfile.mkdtemp()
        try:
            env_root_dir = os.path.join(tempdir, 'foo', 'env')
            os.makedirs(env_root_dir)
            env_fpath = os.path.join(env_root_dir, 'config-env')

            salt.utils.fopen(env_fpath, 'w').write(
                'root_dir: {0}\n'
                'log_file: {1}\n'.format(env_root_dir, env_fpath)
            )

            os.environ['SALT_CLOUD_CONFIG'] = env_fpath
            # Should load from env variable, not the default configuration file
            config = cloudconfig.cloud_config('/etc/salt/cloud')
            self.assertEqual(config['log_file'], env_fpath)
            os.environ.clear()
            os.environ.update(original_environ)

            root_dir = os.path.join(tempdir, 'foo', 'bar')
            os.makedirs(root_dir)
            fpath = os.path.join(root_dir, 'config')
            salt.utils.fopen(fpath, 'w').write(
                'root_dir: {0}\n'
                'log_file: {1}\n'.format(root_dir, fpath)
            )
            # Let's set the environment variable, yet, since the configuration
            # file path is not the default one, ie, the user has passed an
            # alternative configuration file form the CLI parser, the
            # environment variable will be ignored.
            os.environ['SALT_CLOUD_CONFIG'] = env_fpath
            config = cloudconfig.cloud_config(fpath)
            self.assertEqual(config['log_file'], fpath)
        finally:
            # Reset the environ
            os.environ.clear()
            os.environ.update(original_environ)

            if os.path.isdir(tempdir):
                shutil.rmtree(tempdir)

    def test_deploy_search_path_as_string(self):
        temp_conf_dir = os.path.join(integration.TMP, 'issue-8863')
        config_file_path = os.path.join(temp_conf_dir, 'cloud')
        deploy_dir_path = os.path.join(temp_conf_dir, 'test-deploy.d')
        try:
            for directory in (temp_conf_dir, deploy_dir_path):
                if not os.path.isdir(directory):
                    os.makedirs(directory)

            default_config = cloudconfig.cloud_config(config_file_path)
            default_config['deploy_scripts_search_path'] = deploy_dir_path
            with salt.utils.fopen(config_file_path, 'w') as cfd:
                cfd.write(yaml.dump(default_config))

            default_config = cloudconfig.cloud_config(config_file_path)

            # Our custom deploy scripts path was correctly added to the list
            self.assertIn(
                deploy_dir_path,
                default_config['deploy_scripts_search_path']
            )

            # And it's even the first occurrence as it should
            self.assertEqual(
                deploy_dir_path,
                default_config['deploy_scripts_search_path'][0]
            )
        finally:
            if os.path.isdir(temp_conf_dir):
                shutil.rmtree(temp_conf_dir)

    def test_includes_load(self):
        '''cloud.{providers,profiles}.d directories are loaded even if not directly passed'''
        config_path = os.path.join(integration.FILES, 'conf', 'cloud')
        config = cloudconfig.cloud_config(config_path)
        self.assertIn('ec2-config', config['providers'])
        self.assertIn('Ubuntu-13.04-AMD64', config['profiles'])


if __name__ == '__main__':
    from salttesting.parser import run_testcase
    run_testcase(CloudConfigTestCase)
