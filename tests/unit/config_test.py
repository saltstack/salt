# -*- coding: utf-8 -*-
"""
    tests.unit.config
    ~~~~~~~~~~~~~~~~~

    :copyright: © 2012 UfSoft.org - :email:`Pedro Algarvio (pedro@algarvio.me)`
    :license: Apache 2.0, see LICENSE for more details.
"""

import os
import shutil
import tempfile
from saltunittest import TestCase, TestLoader, TextTestRunner
from salt import config as sconfig


class ConfigTestCase(TestCase):
    def test_proper_path_joining(self):
        fpath = tempfile.mktemp()
        open(fpath, 'w').write(
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
        open(fpath, 'w').write(
            'root_dir: {0}\n'
            'log_file: {1}\n'.format(root_dir, fpath)
        )
        config = sconfig.master_config(fpath)
        self.assertEqual(config['log_file'], fpath)
        shutil.rmtree(tempdir)


if __name__ == "__main__":
    loader = TestLoader()
    tests = loader.loadTestsFromTestCase(ConfigTestCase)
    TextTestRunner(verbosity=1).run(tests)
