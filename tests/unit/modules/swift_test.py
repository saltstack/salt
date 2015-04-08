# -*- coding: utf-8 -*-
'''
    :codeauthor: :email:`Jayesh Kariya <jayeshk@saltstack.com>`
'''

# Import Python Libs
from __future__ import absolute_import

# Import Salt Testing Libs
from salttesting import TestCase, skipIf
from salttesting.mock import (
    MagicMock,
    patch,
    NO_MOCK,
    NO_MOCK_REASON
)

from salttesting.helpers import ensure_in_syspath

ensure_in_syspath('../../')

# Import Salt Libs
from salt.modules import swift


@skipIf(NO_MOCK, NO_MOCK_REASON)
class SwiftTestCase(TestCase):
    '''
    Test cases for salt.modules.swift
    '''
    # 'delete' function tests: 1

    def test_delete(self):
        '''
        Test for delete a container, or delete an object from a container.
        '''
        with patch.object(swift, '_auth', MagicMock()):
            self.assertTrue(swift.delete('mycontainer'))

            self.assertTrue(swift.delete('mycontainer', path='myfile.png'))

    # 'get' function tests: 1

    def test_get(self):
        '''
        Test for list the contents of a container,
        or return an object from a container.
        '''
        with patch.object(swift, '_auth', MagicMock()):
            self.assertTrue(swift.get())

            self.assertTrue(swift.get('mycontainer'))

            self.assertTrue(swift.get('mycontainer', path='myfile.png',
                                      return_bin=True))

            self.assertTrue(swift.get('mycontainer', path='myfile.png',
                                      local_file='/tmp/myfile.png'))

            self.assertFalse(swift.get('mycontainer', path='myfile.png'))

    # 'put' function tests: 1

    def test_put(self):
        '''
        Test for create a new container, or upload an object to a container.
        '''
        with patch.object(swift, '_auth', MagicMock()):
            self.assertTrue(swift.put('mycontainer'))

            self.assertTrue(swift.put('mycontainer', path='myfile.png',
                                      local_file='/tmp/myfile.png'))

            self.assertFalse(swift.put('mycontainer', path='myfile.png'))


if __name__ == '__main__':
    from integration import run_tests
    run_tests(SwiftTestCase, needs_daemon=False)
