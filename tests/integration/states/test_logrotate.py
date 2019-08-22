# -*- coding: utf-8 -*-

# Import Python Libs
from __future__ import absolute_import, print_function, unicode_literals
import os
import os.path

# Import Salt Libs
import salt.utils.platform

# Import Salt Testing Libs
from tests.support.unit import skipIf
from tests.support.case import ModuleCase


@skipIf(salt.utils.platform.is_windows(), 'Only works on POSIX-like systems')
class LogrotateTestMakeFile(ModuleCase):
    '''
    Test cases for salt.states.logrotate
    '''

    def test_make_file(self):
        file_name = '/etc/logrotate.d/defaults_test_test_test'
        try:
            if os.path.isfile(file_name):
                os.remove(file_name)

            ret = self.run_state('logrotate.set',
                                 name='logrotate-wtmp-rotate',
                                 key='/var/log/wtmp',
                                 value='rotate',
                                 setting='2',
                                 conf_file=file_name,
                                 make_file=True)['logrotate_|-logrotate-wtmp-rotate_|-logrotate-wtmp-rotate_|-set']
        finally:
            if os.path.isfile(file_name):
                os.remove(file_name)
            else:
                raise FileExistsError('%s should exist' % file_name)

        self.assertEqual(ret['name'], 'logrotate-wtmp-rotate')
        self.assertEquals(ret['changes'], {'old': False, 'new': 2})
        self.assertEquals(ret['comment'], 'Set block \'/var/log/wtmp\' command \'rotate\' value: 2')
        self.assertTrue(ret['result'])
