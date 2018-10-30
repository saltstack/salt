# -*- coding: utf-8 -*-
'''
    :codeauthor: Anthony Shaw <anthonyshaw@apache.org>
'''
# Import Python libs
from __future__ import absolute_import, print_function, unicode_literals
import os

# Import Salt Libs
import salt.states.netyang as netyang

# Import Salt Testing Libs
from tests.support.mixins import LoaderModuleMockMixin
from tests.support.unit import skipIf, TestCase
from tests.support.mock import (
    NO_MOCK,
    NO_MOCK_REASON,
    MagicMock,
    patch
)

TEST_DATA = {
    'foo': 'bar'
}

@skipIf(NO_MOCK, NO_MOCK_REASON)
class NetyangTestCase(TestCase, LoaderModuleMockMixin):
    def setup_loader_modules(self):
        return {netyang: {}}


    def test_managed(self):
        ret = {'changes': {}, 'comment': '',
               'name': 'salt', 'result': True}
        revision_mock = MagicMock(return_value='abcdef')

        with patch.dict(netyang.__salt__,
                        {'hg.revision': revision_mock,}):
            with patch.dict(netyang.__opts__, {'test': False}):
                self.assertDictEqual(netyang.managed('test', ('model1',)), ret)
                assert revision_mock.called
