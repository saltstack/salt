# -*- coding: utf-8 -*-
'''
tests for host state
'''

# Import python libs
from __future__ import absolute_import, print_function, unicode_literals
import os
import shutil

# Import Salt Testing libs
from tests.support.runtests import RUNTIME_VARS
from tests.support.case import ModuleCase
from tests.support.mixins import SaltReturnAssertsMixin

# Import salt libs
import salt.utils.files
import salt.utils.stringutils


class HostTest(ModuleCase, SaltReturnAssertsMixin):
    '''
    Validate the host state
    '''

    def setUp(self):
        self.hfpath = os.path.join(RUNTIME_VARS.TMP, 'hosts')
        shutil.copyfile(os.path.join(RUNTIME_VARS.FILES, 'hosts'), self.hfpath)
        self.addCleanup(self._delete_hosts_file)
        super(HostTest, self).setUp()

    def _delete_hosts_file(self):
        if os.path.exists(self.hfpath):
            os.remove(self.hfpath)

    def test_present(self):
        '''
        host.present
        '''
        name = 'spam.bacon'
        ip = '10.10.10.10'
        ret = self.run_state('host.present', name=name, ip=ip)
        self.assertSaltTrueReturn(ret)
        with salt.utils.files.fopen(self.hfpath) as fp_:
            output = salt.utils.stringutils.to_unicode(fp_.read())
            self.assertIn('{0}\t\t{1}'.format(ip, name), output)
