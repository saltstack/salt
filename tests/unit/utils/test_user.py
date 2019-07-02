# -*- coding: utf-8 -*-

# Import python libs
from __future__ import absolute_import, print_function, unicode_literals
import os
import grp
import pwd
import sys
import time
import signal
import multiprocessing
import functools

# Import Salt Testing libs
from tests.support.unit import TestCase, skipIf
from tests.support.helpers import (this_user) 
from tests.support.mock import (
    patch,
    NO_MOCK,
    NO_MOCK_REASON
)

# Import salt libs
import salt.utils.platform
import salt.utils.user

class TestUser(TestCase):
    @skipIf(NO_MOCK, NO_MOCK_REASON)
    @skipIf(salt.utils.platform.is_windows(), "Module not available on Windows")
    def test_chugid_and_umask(self):

        #with patch('grp.getgrnam', MagicMock(return_value=getgrnam)):

        running_user = this_user()
        running_group = grp.getgrgid(os.getgid()).gr_name

        gids = {30: 'expectedgroup', 20: running_group}
        getgrnams = {'expectedgroup': grp.struct_group(('expectedgroup', '*', 30, ['expecteduser'])),
                     running_group: grp.struct_group((running_group, '*', 20, [running_user]))}
        getpwnams = {'expecteduser': pwd.struct_passwd(('expecteduser', 'x', 30, 30, '-', '-', '-')), 
                running_user: pwd.struct_passwd((running_user, 'x', 20, 20, '-', '-', '-'))}

        def getgrnam(group):
            return getgrnams[group]

        def getpwnam(user):
            return getpwnams[user]

        def getgrgid(gid):
            return getgrnams[gids[gid]]

        with patch('grp.getgrgid', getgrgid):
            with patch('grp.getgrnam', getgrnam):
                with patch('pwd.getpwnam', getpwnam): 
                    with patch('salt.utils.user.chugid') as chugid_mock:
                        salt.utils.user.chugid_and_umask('expecteduser', umask=None, group=running_group)
                        chugid_mock.assert_called_with('expecteduser', running_group)
                        print('-------------------------------------------------------------')
                        print('test2 start')
                        salt.utils.user.chugid_and_umask('expecteduser', umask=None, group=None)
                        chugid_mock.assert_called_with('expecteduser', 'expectedgroup')
