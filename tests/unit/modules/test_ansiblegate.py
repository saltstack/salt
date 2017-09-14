# -*- coding: utf-8 -*-
#
# Author: Bo Maryniuk <bo@suse.de>
#
# Copyright 2017 SUSE LLC
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

# Import Salt Testing Libs
from tests.support.mixins import LoaderModuleMockMixin
from tests.support.unit import TestCase, skipIf
from tests.support.mock import (
    Mock,
    MagicMock,
    call,
    patch,
    NO_MOCK,
    NO_MOCK_REASON
)

import salt.modules.ansiblegate as ansible


@skipIf(NO_MOCK, NO_MOCK_REASON)
class AnsiblegateTestCase(TestCase, LoaderModuleMockMixin):
    def setup_loader_modules(self):
        return {ansible: {}}

    def test_ansible_modules_listing(self):
        pass

    def test_ansible_module_help(self):
        pass
