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

# Import Salt Testing Libs
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

from salt.modules import x509


@skipIf(NO_MOCK, NO_MOCK_REASON)
@skipIf(not bool(pytest), False)
class X509TestCase(TestCase, LoaderModuleMockMixin):

    def setup_loader_modules(self):
        return {x509: {}}

    @patch('salt.modules.x509.log', MagicMock())
    def test_private_func__parse_subject(self):
        '''
        Test private function _parse_subject(subject) it handles a missing fields
        :return:
        '''
        class FakeSubject(object):
            '''
            Class for faking x509'th subject.
            '''
            def __init__(self):
                self.nid = {'Darth Vader': 1}

            def __getattr__(self, item):
                if item != 'nid':
                    raise TypeError('A star wars satellite accidentally blew up the WAN.')

        subj = FakeSubject()
        x509._parse_subject(subj)
        x509.log.trace.assert_called_once()
        assert x509.log.trace.call_args[0][0] == "Missing attribute '%s'. Error: %s"
        assert x509.log.trace.call_args[0][1] == list(subj.nid.keys())[0]
        assert isinstance(x509.log.trace.call_args[0][2], TypeError)
