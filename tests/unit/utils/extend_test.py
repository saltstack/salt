# -*- coding: utf-8 -*-
'''
    tests.unit.utils.extend_test
    ~~~~~~~~~~~~~~~~~~~~~~~~~~~~

    Test the salt extend script, leave templates/test alone to keep this working!
'''

# Import python libs
from __future__ import absolute_import

import os
import shutil
from datetime import date

# Import Salt Testing libs
from salttesting import TestCase
from salttesting.helpers import ensure_in_syspath
from salttesting.mock import MagicMock, patch

ensure_in_syspath('../../')

# Import salt libs
import salt.utils.extend
import integration
import salt.utils


class ExtendTestCase(TestCase):
    def setUp(self):
        self.out = None

    def tearDown(self):
        if self.out is not None:
            if os.path.exists(self.out):
                shutil.rmtree(self.out, True)

    @patch('sys.exit', MagicMock)
    def test_run(self):
        out = salt.utils.extend.run('test', 'test', 'this description', integration.CODE_DIR, False)
        self.out = out
        year = date.today().strftime('%Y')
        self.assertTrue(os.path.exists(out))
        self.assertFalse(os.path.exists(os.path.join(out, 'template.yml')))
        self.assertTrue(os.path.exists(os.path.join(out, 'directory')))
        self.assertTrue(os.path.exists(os.path.join(out, 'directory', 'test.py')))
        with salt.utils.fopen(os.path.join(out, 'directory', 'test.py'), 'r') as test_f:
            self.assertEqual(test_f.read(), year)

if __name__ == '__main__':
    from unit import run_tests
    run_tests(ExtendTestCase, needs_daemon=False)
