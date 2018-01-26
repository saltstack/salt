# -*- coding: utf-8 -*-
'''
Tests man spm
'''
# Import python libs
from __future__ import absolute_import
import os
import shutil
import sys
import tempfile

# Import Salt Testing libs
from tests.support.case import ModuleCase
from tests.support.helpers import destructiveTest
from tests.support.paths import CODE_DIR


@destructiveTest
class SPMManTest(ModuleCase):
    '''
    Validate man spm
    '''

    def setUp(self):
        self.tmpdir = tempfile.mktemp()
        os.mkdir(self.tmpdir)
        self.run_function('cmd.run', ['{0} {1} install --root={2}'.format(
            sys.executable,
            os.path.join(CODE_DIR, 'setup.py'),
            self.tmpdir
        )])

    def tearDown(self):
        shutil.rmtree(self.tmpdir)

    def test_man_spm(self):
        '''
        test man spm
        '''
        manpath = self.run_function('cmd.run', ['find {0} -name spm.1'.format(self.tmpdir)])
        self.assertIn('/man1/', manpath)
        cmd = self.run_function('cmd.run', ['man {0}'.format(manpath)])
        self.assertIn('Salt Package Manager', cmd)
        self.assertIn('command for managing Salt packages', cmd)
