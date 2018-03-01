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

import os
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
    def test_close_fds_active_on_linux(self):
        '''
        Should test if the close_fds is available on Linux
        :return:
        '''
