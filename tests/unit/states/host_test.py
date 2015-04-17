# -*- coding: utf-8 -*-
'''
    :codeauthor: :email:`Rahul Handay <rahulha@saltstack.com>`
'''
# Import Python libs
from __future__ import absolute_import

# Import Salt Libs
from salt.states import host

# Import Salt Testing Libs
from salttesting import skipIf, TestCase
from salttesting.helpers import ensure_in_syspath
from salttesting.mock import (
    NO_MOCK,
    NO_MOCK_REASON,
    MagicMock,
    patch
)

ensure_in_syspath('../../')

host.__salt__ = {}


@skipIf(NO_MOCK, NO_MOCK_REASON)
class HostTestCase(TestCase):
    '''
        Validate the host state
    '''
    def test_present(self):
        '''
            Test to ensures that the named host is present with the given ip
        '''
        ret = {'changes': {},
               'comment': 'Host salt (127.0.0.1) already present',
               'name': 'salt', 'result': True}

        mock = MagicMock(return_value=True)
        with patch.dict(host.__salt__, {'hosts.has_pair': mock}):
            self.assertDictEqual(host.present("salt", "127.0.0.1"), ret)

    def test_absent(self):
        '''
            Test to ensure that the named host is absent
        '''
        ret = {'changes': {},
               'comment': 'Host salt (127.0.0.1) already absent',
               'name': 'salt', 'result': True}

        mock = MagicMock(return_value=False)
        with patch.dict(host.__salt__, {'hosts.has_pair': mock}):
            self.assertDictEqual(host.absent("salt", "127.0.0.1"), ret)


if __name__ == '__main__':
    from integration import run_tests
    run_tests(HostTestCase, needs_daemon=False)
