# -*- coding: utf-8 -*-
'''
tests for host state
'''

# Import python libs
from __future__ import absolute_import
import os
import shutil

# Import Salt Testing libs
from tests.support.case import ModuleCase
from tests.support.paths import FILES, TMP
from tests.support.mixins import SaltReturnAssertsMixin

# Import salt libs
import salt.utils

HFILE = os.path.join(TMP, 'hosts')


class HostTest(ModuleCase, SaltReturnAssertsMixin):
    '''
    Validate the host state
    '''

    def setUp(self):
        shutil.copyfile(os.path.join(FILES, 'hosts'), HFILE)
        super(HostTest, self).setUp()

    def tearDown(self):
        if os.path.exists(HFILE):
            os.remove(HFILE)
        super(HostTest, self).tearDown()

    def test_present(self):
        '''
        host.present
        '''
        name = 'spam.bacon'
        ip = '10.10.10.10'
        ret = self.run_state('host.present', name=name, ip=ip)
        self.assertSaltTrueReturn(ret)
        with salt.utils.fopen(HFILE) as fp_:
            output = fp_.read()
            self.assertIn('{0}\t\t{1}'.format(ip, name), output)
