# -*- coding: utf-8 -*-
#
# Author: Bo Maryniuk <bo@suse.de>
#
# Copyright 2018 SUSE LLC
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
# http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

from __future__ import absolute_import, print_function, unicode_literals

try:
    import pytest
except ImportError as import_error:
    pytest = None

from tests.support.mixins import LoaderModuleMockMixin
from tests.support.unit import TestCase, skipIf
from tests.support.mock import (
    patch,
    MagicMock,
    NO_MOCK,
    NO_MOCK_REASON
)

import salt.utils.subprocess as subprocess
import salt.utils.platform


@skipIf(NO_MOCK, NO_MOCK_REASON)
@skipIf(not bool(pytest), False)
@skipIf(salt.utils.platform.is_windows(), 'Not supported on Windows')
class SubprocessTestCase(TestCase, LoaderModuleMockMixin):
    '''
    Test case for the salt.utils.subprocess.FdPopen
    '''

    def setup_loader_modules(self):
        return {subprocess: {}}

    @patch('salt.utils.subprocess.log', MagicMock())
    @patch('sys.platform', 'linux2')
    @patch('salt.utils.subprocess.six.PY2', True)
    @patch('os.getpid', MagicMock(return_value=111))
    @patch('os.listdir', MagicMock(return_value=[0, 1, 2, 3, 4]))
    @patch('os.closerange', MagicMock())
    @patch('os.fdopen', MagicMock(return_value=''))
    @patch.object(salt.utils.subprocess.FdPopen, '_execute_child', MagicMock())
    @patch.object(salt.utils.subprocess.FdPopen, '_get_handles',
                  MagicMock(return_value=((None, None, None, None, None, None), None,)))
    def test_close_fds_active_on_linux(self):
        '''
        Should test if the close_fds is available on Linux
        :return:
        '''
        subprocess.FdPopen(None)._close_fds(0)
        salt.utils.subprocess.log.debug.assert_called()
        msg, val = salt.utils.subprocess.log.debug.call_args[0]
        assert (msg % val) == 'Closing 5 file descriptors'

    @patch('salt.utils.subprocess.log', MagicMock())
    @patch('salt.utils.subprocess.subprocess.MAXFD', 100)
    @patch('sys.platform', 'linux2')
    @patch('salt.utils.subprocess.six.PY2', True)
    @patch('os.getpid', MagicMock(return_value=111))
    @patch('os.listdir', MagicMock(side_effect=OSError))
    @patch('os.closerange', MagicMock())
    @patch('os.fdopen', MagicMock(return_value=''))
    @patch.object(salt.utils.subprocess.FdPopen, '_execute_child', MagicMock())
    @patch.object(salt.utils.subprocess.FdPopen, '_get_handles',
                  MagicMock(return_value=((None, None, None, None, None, None), None,)))
    def test_close_fds_proc_fallback(self):
        '''
        Should fall-back to the standard way, once /proc is not mounted.
        :return:
        '''
        subprocess.FdPopen(None)._close_fds(0)
        assert salt.utils.subprocess.log.debug.call_args[0][1] == 100

    @patch('salt.utils.subprocess.log', MagicMock())
    @patch('salt.utils.subprocess.subprocess.MAXFD', 100)
    @patch('sys.platform', 'linux2')
    @patch('salt.utils.subprocess.six.PY2', True)
    @patch('os.getpid', MagicMock(return_value=111))
    @patch('os.listdir', MagicMock(return_value=[0, 1, 2, 3, 4]))
    @patch('os.closerange', MagicMock())
    @patch('os.fdopen', MagicMock(return_value=''))
    @patch.object(salt.utils.subprocess.FdPopen, '_execute_child', MagicMock())
    @patch.object(salt.utils.subprocess.FdPopen, '_get_handles',
                  MagicMock(return_value=((None, None, None, None, None, None), None,)))
    def test_close_fds_proc_pathcheck(self):
        '''
        Should search for a /proc/<PID>/fd files.
        :return:
        '''
        subprocess.FdPopen(None)._close_fds(0)
        assert salt.utils.subprocess.os.listdir.call_args[0][0] == '/proc/111/fd'

    @patch('salt.utils.subprocess.log', MagicMock())
    @patch('salt.utils.subprocess.subprocess.MAXFD', 100)
    @patch('sys.platform', 'linux2')
    @patch('salt.utils.subprocess.six.PY2', True)
    @patch('os.getpid', MagicMock(return_value=111))
    @patch('os.listdir', MagicMock(return_value=[0, 1, 2, 3, 4]))
    @patch('os.closerange', MagicMock())
    @patch('os.fdopen', MagicMock(return_value=''))
    @patch.object(salt.utils.subprocess.FdPopen, '_execute_child', MagicMock())
    @patch.object(salt.utils.subprocess.FdPopen, '_get_handles',
                  MagicMock(return_value=((None, None, None, None, None, None), None,)))
    def test_close_fds_closerange_called_if_exists(self):
        '''
        Should call closerange, if around
        :return:
        '''
        subprocess.FdPopen(None)._close_fds(0)
        assert salt.utils.subprocess.os.closerange.call_args[0] == (1, 5)
