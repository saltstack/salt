# -*- coding: utf-8 -*-
'''
    :codeauthor: :email:`Rahul Handay <rahulha@saltstack.com>`
'''

# Import Python libs
from __future__ import absolute_import

# Import Salt Testing Libs
from tests.support.mixins import LoaderModuleMockMixin
from tests.support.unit import TestCase, skipIf
from tests.support.mock import (
    MagicMock,
    patch,
    NO_MOCK,
    NO_MOCK_REASON
)

# Import Salt Libs
import salt.modules.saltcloudmod as saltcloudmod


class MockJson(object):
    '''
        Mock json class
    '''
    flag = None

    def __init__(self):
        pass

    @staticmethod
    def loads(data, object_hook):
        '''
            Mock load method
        '''
        if MockJson.flag:
            return data, object_hook
        else:
            raise ValueError


@skipIf(NO_MOCK, NO_MOCK_REASON)
class SaltcloudmodTestCase(TestCase, LoaderModuleMockMixin):
    '''
        Test cases for salt.modules.saltcloudmod
    '''
    def setup_loader_modules(self):
        return {saltcloudmod: {'json': MockJson}}

    def test_create(self):
        '''
            Test if create the named vm
        '''
        MockJson.flag = True
        mock = MagicMock(return_value=True)
        with patch.dict(saltcloudmod.__salt__, {'cmd.run_stdout': mock}):
            self.assertTrue(saltcloudmod.create("webserver",
                                                "rackspace_centos_512"
                                                )
                            )

            MockJson.flag = False
            self.assertDictEqual(saltcloudmod.create("webserver",
                                                     "rackspace_centos_512"
                                                     ),
                                 {}
                                 )
