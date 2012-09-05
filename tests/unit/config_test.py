# -*- coding: utf-8 -*-
"""
    tests.unit.config
    ~~~~~~~~~~~~~~~~~

    :copyright: © 2012 UfSoft.org - :email:`Pedro Algarvio (pedro@algarvio.me)`
    :license: Apache 2.0, see LICENSE for more details.
"""

import os
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


if __name__ == "__main__":
    loader = TestLoader()
    tests = loader.loadTestsFromTestCase(ConfigTestCase)
    TextTestRunner(verbosity=1).run(tests)