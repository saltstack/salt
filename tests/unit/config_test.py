# -*- coding: utf-8 -*-
'''
    tests.unit.config_test
    ~~~~~~~~~~~~~~~~~~~~~~

    :codeauthor: :email:`Pedro Algarvio (pedro@algarvio.me)`
    :copyright: © 2012-2013 by the SaltStack Team, see AUTHORS for more details
    :license: Apache 2.0, see LICENSE for more details.
'''

# Import python libs
import os
import shutil
import tempfile

# Import salt libs
try:
    import integration
except ImportError:
    if __name__ == '__main__':
        import sys
        sys.path.insert(
            0, os.path.abspath(
                os.path.join(
                    os.path.dirname(__file__), '../'
                )
            )
        )
    import integration
import salt.utils
from salt import config as sconfig

# Import Salt Testing libs
from salttesting import TestCase


class ConfigTestCase(TestCase):
    def test_proper_path_joining(self):
        fpath = tempfile.mktemp()
        salt.utils.fopen(fpath, 'w').write(
            "root_dir: /\n"
            "key_logfile: key\n"
        )
        config = sconfig.master_config(fpath)
        # os.path.join behaviour
        self.assertEqual(config['key_logfile'], os.path.join('/', 'key'))
        # os.sep.join behaviour
        self.assertNotEqual(config['key_logfile'], '//key')

    def test_common_prefix_stripping(self):
        tempdir = tempfile.mkdtemp()
        root_dir = os.path.join(tempdir, 'foo', 'bar')
        os.makedirs(root_dir)
        fpath = os.path.join(root_dir, 'config')
        salt.utils.fopen(fpath, 'w').write(
            'root_dir: {0}\n'
            'log_file: {1}\n'.format(root_dir, fpath)
        )
        config = sconfig.master_config(fpath)
        self.assertEqual(config['log_file'], fpath)
        shutil.rmtree(tempdir)


if __name__ == '__main__':
    from integration import run_tests
    run_tests(ConfigTestCase, needs_daemon=False)
