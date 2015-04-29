# -*- coding: utf-8 -*-
'''
    :codeauthor: :email:`Rahul Handay <rahulha@saltstack.com>`
'''

# Import Python libs
from __future__ import absolute_import

# Import Salt Testing Libs
from salttesting import TestCase, skipIf
from salttesting.helpers import ensure_in_syspath
from salttesting.mock import (
    MagicMock,
    patch,
    NO_MOCK,
    NO_MOCK_REASON
)

ensure_in_syspath('../../')

# Import Salt Libs
from salt.modules import saltcloudmod


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

saltcloudmod.json = MockJson

# Globals
saltcloudmod.__salt__ = {}


@skipIf(NO_MOCK, NO_MOCK_REASON)
class SaltcloudmodTestCase(TestCase):
    '''
        Test cases for salt.modules.saltcloudmod
    '''
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


if __name__ == '__main__':
    from integration import run_tests
    run_tests(SaltcloudmodTestCase, needs_daemon=False)
