# -*- coding: utf-8 -*-\
'''
    unit.config_test
    ~~~~~~~~~~~~~~~~

    Configuration related unit testing

    :codeauthor: :email:`Pedro Algarvio (pedro@algarvio.me)`
    :copyright: © 2013 by the SaltStack Team, see AUTHORS for more details.
    :license: Apache 2.0, see LICENSE for more details.
'''

# Import python libs
import os
import shutil
import tempfile

# Import salt libs
import salt.utils
import salt.version

# Import salt testing libs
from salttesting import TestCase
from salttesting.helpers import ensure_in_syspath
ensure_in_syspath('../')

# Import salt cloud libs
from saltcloud import config as cloudconfig


class CloudConfigTestCase(TestCase):

    def test_load_cloud_config_from_environ_var(self):
        if salt.version.__version_info__ < (0, 16, 0):
            self.skipTest(
                'This test will always fail if salt >= 0.16.0 is not available'
            )

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
            os.environ.clear()
            os.environ.update(original_environ)

        finally:
            if os.path.isdir(tempdir):
                shutil.rmtree(tempdir)


if __name__ == '__main__':
    from salttesting.parser import run_testcase
    run_testcase(CloudConfigTestCase)
