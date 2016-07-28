# -*- coding: utf-8 -*-
'''
    tests.unit.utils.extend_test
    ~~~~~~~~~~~~~~~~~~~~~~~~~~~~

    Test the salt extend script
'''

# Import python libs
from __future__ import absolute_import

import os
import shutil

# Import salt libs
import salt.utils.extend

# Import Salt Testing libs
from salttesting import TestCase
from salttesting.helpers import ensure_in_syspath
ensure_in_syspath('../../')


class ExtendTestCase(TestCase):
    def setUp(self):
        self.out = None

    def tearDown(self):
        if self.out is not None:
            if os.path.exists(self.out):
                shutil.rmtree(self.out, True)

    def test_run(self):
        out = salt.utils.extend.run('test', 'test', 'this description', '.', False)
        self.out = out
        self.assertTrue(os.path.exists(out))
        self.assertFalse(os.path.exists(os.path.join(out, 'template.yml')))


if __name__ == '__main__':
    from unit import run_tests
    run_tests(ExtendTestCase, needs_daemon=False)