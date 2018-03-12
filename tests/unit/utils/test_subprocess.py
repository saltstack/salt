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
import salt.ext.six


@skipIf(NO_MOCK, NO_MOCK_REASON)
@skipIf(not bool(pytest), 'No PyTest available')
@skipIf(not salt.utils.platform.is_linux(), 'Linux only')
@skipIf(not salt.ext.six.PY2, 'Python-2 only')
class SubprocessTestCase(TestCase, LoaderModuleMockMixin):
    '''
    Test case for the salt.utils.subprocess.FdPopen
    '''

    def setup_loader_modules(self):
        return {subprocess: {}}

    @patch('sys.platform', 'linux2')
    @patch('salt.utils.subprocess.six.PY2', True)
    @patch('os.getpid', MagicMock(return_value=111))
    @patch('os.listdir', MagicMock(return_value=[0, 1, 2, 3, 4]))
    @patch('os.close', MagicMock())
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
        subprocess.os.close.assert_called()
        assert subprocess.os.close.call_count == 2

    @patch('salt.utils.subprocess.subprocess.MAXFD', 103)
    @patch('sys.platform', 'linux2')
    @patch('salt.utils.subprocess.six.PY2', True)
    @patch('os.getpid', MagicMock(return_value=111))
    @patch('os.listdir', MagicMock(side_effect=OSError))
    @patch('os.close', MagicMock())
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
        subprocess.os.close.assert_called()
        assert subprocess.os.close.call_count == 100


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
    @patch('salt.utils.subprocess.sys.platform', 'linux2')
    @patch('salt.utils.subprocess.six.PY2', True)
    @patch('salt.utils.subprocess.os.getpid', MagicMock(return_value=111))
    @patch('salt.utils.subprocess.os.listdir', MagicMock(return_value=[0, 1, 2, 3, 4]))
    @patch('salt.utils.subprocess.os.close', MagicMock())
    @patch('salt.utils.subprocess.os.fdopen', MagicMock(return_value=''))
    @patch.object(salt.utils.subprocess.FdPopen, '_execute_child', MagicMock())
    @patch.object(salt.utils.subprocess.FdPopen, '_get_handles',
                  MagicMock(return_value=((None, None, None, None, None, None), None,)))
    def test_close_fds_does_not_closes_std(self):
        '''
        Should not close std[in/out/err].
        :return:
        '''
        subprocess.FdPopen(None)._close_fds(0)
        salt.utils.subprocess.os.close.assert_called()
        assert salt.utils.subprocess.os.close.call_count == 2
