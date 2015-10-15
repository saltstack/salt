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
host.__opts__ = {}


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

    def test_only_already(self):
        '''
        Test only() when the state hasn't changed
        '''
        expected = {
            'name': '127.0.1.1',
            'changes': {},
            'result': True,
            'comment': 'IP address 127.0.1.1 already set to "foo.bar"'}
        mock1 = MagicMock(return_value=['foo.bar'])
        with patch.dict(host.__salt__, {'hosts.get_alias': mock1}):
            mock2 = MagicMock(return_value=True)
            with patch.dict(host.__salt__, {'hosts.set_host': mock2}):
                with patch.dict(host.__opts__, {'test': False}):
                    self.assertDictEqual(
                        expected,
                        host.only("127.0.1.1", 'foo.bar'))

    def test_only_dryrun(self):
        '''
        Test only() when state would change, but it's a dry run
        '''
        expected = {
            'name': '127.0.1.1',
            'changes': {},
            'result': None,
            'comment': 'Would change 127.0.1.1 from "foo.bar" to "foo.bar foo"'}
        mock1 = MagicMock(return_value=['foo.bar'])
        with patch.dict(host.__salt__, {'hosts.get_alias': mock1}):
            mock2 = MagicMock(return_value=True)
            with patch.dict(host.__salt__, {'hosts.set_host': mock2}):
                with patch.dict(host.__opts__, {'test': True}):
                    self.assertDictEqual(
                        expected,
                        host.only("127.0.1.1", ['foo.bar', 'foo']))

    def test_only_fail(self):
        '''
        Test only() when state change fails
        '''
        expected = {
            'name': '127.0.1.1',
            'changes': {},
            'result': False,
            'comment': 'hosts.set_host failed to change 127.0.1.1'
                + ' from "foo.bar" to "foo.bar foo"'}
        mock = MagicMock(return_value=['foo.bar'])
        with patch.dict(host.__salt__, {'hosts.get_alias': mock}):
            mock = MagicMock(return_value=False)
            with patch.dict(host.__salt__, {'hosts.set_host': mock}):
                with patch.dict(host.__opts__, {'test': False}):
                    self.assertDictEqual(
                        expected,
                        host.only("127.0.1.1", ['foo.bar', 'foo']))

    def test_only_success(self):
        '''
        Test only() when state successfully changes
        '''
        expected = {
            'name': '127.0.1.1',
            'changes': {'127.0.1.1': {'old': 'foo.bar', 'new': 'foo.bar foo'}},
            'result': True,
            'comment': 'successfully changed 127.0.1.1'
                + ' from "foo.bar" to "foo.bar foo"'}
        mock = MagicMock(return_value=['foo.bar'])
        with patch.dict(host.__salt__, {'hosts.get_alias': mock}):
            mock = MagicMock(return_value=True)
            with patch.dict(host.__salt__, {'hosts.set_host': mock}):
                with patch.dict(host.__opts__, {'test': False}):
                    self.assertDictEqual(
                        expected,
                        host.only("127.0.1.1", ['foo.bar', 'foo']))


if __name__ == '__main__':
    from integration import run_tests
    run_tests(HostTestCase, needs_daemon=False)
