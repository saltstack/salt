# -*- coding: utf-8 -*-
'''
    :codeauthor: :email:`Jayesh Kariya <jayeshk@saltstack.com>`
'''
# Import Python libs
from __future__ import absolute_import

# Import Salt Testing Libs
from salttesting import skipIf, TestCase
from salttesting.mock import (
    NO_MOCK,
    NO_MOCK_REASON,
    MagicMock,
    patch
)

from salttesting.helpers import ensure_in_syspath

ensure_in_syspath('../../')

# Import Salt Libs
from salt.states import ssh_auth

ssh_auth.__salt__ = {}
ssh_auth.__opts__ = {}


@skipIf(NO_MOCK, NO_MOCK_REASON)
class SshAuthTestCase(TestCase):
    '''
    Test cases for salt.states.ssh_auth
    '''
    # 'present' function tests: 1

    def test_present(self):
        '''
        Test to verifies that the specified SSH key
        is present for the specified user.
        '''
        name = 'sshkeys'
        user = 'root'
        source = 'salt://ssh_keys/id_rsa.pub'

        ret = {'name': name,
               'changes': {},
               'result': True,
               'comment': ''}

        mock = MagicMock(return_value='exists')
        mock_data = MagicMock(side_effect=['replace', 'new'])
        with patch.dict(ssh_auth.__salt__, {'ssh.check_key': mock,
                                            'ssh.set_auth_key': mock_data}):
            with patch.dict(ssh_auth.__opts__, {'test': True}):
                comt = ('The authorized host key sshkeys is already '
                        'present for user root')
                ret.update({'comment': comt})
                self.assertDictEqual(ssh_auth.present(name, user, source), ret)

            with patch.dict(ssh_auth.__opts__, {'test': False}):
                comt = ('The authorized host key sshkeys '
                        'for user root was updated')
                ret.update({'comment': comt, 'changes': {name: 'Updated'}})
                self.assertDictEqual(ssh_auth.present(name, user, source), ret)

                comt = ('The authorized host key sshkeys '
                        'for user root was added')
                ret.update({'comment': comt, 'changes': {name: 'New'}})
                self.assertDictEqual(ssh_auth.present(name, user, source), ret)

    # 'absent' function tests: 1

    def test_absent(self):
        '''
        Test to verifies that the specified SSH key is absent.
        '''
        name = 'sshkeys'
        user = 'root'
        source = 'salt://ssh_keys/id_rsa.pub'

        ret = {'name': name,
               'changes': {},
               'result': None,
               'comment': ''}

        mock = MagicMock(side_effect=['User authorized keys file not present',
                                      'User authorized keys file not present',
                                      'User authorized keys file not present',
                                      'Key removed'])
        mock_up = MagicMock(side_effect=['update', 'updated'])
        with patch.dict(ssh_auth.__salt__, {'ssh.rm_auth_key': mock,
                                            'ssh.check_key': mock_up}):
            with patch.dict(ssh_auth.__opts__, {'test': True}):
                comt = ('Key sshkeys for user root is set for removal')
                ret.update({'comment': comt})
                self.assertDictEqual(ssh_auth.absent(name, user, source), ret)

                comt = ('Key is already absent')
                ret.update({'comment': comt, 'result': True})
                self.assertDictEqual(ssh_auth.absent(name, user, source), ret)

            with patch.dict(ssh_auth.__opts__, {'test': False}):
                comt = ('User authorized keys file not present')
                ret.update({'comment': comt, 'result': False})
                self.assertDictEqual(ssh_auth.absent(name, user, source), ret)

                comt = ('Key removed')
                ret.update({'comment': comt, 'result': True,
                            'changes': {name: 'Removed'}})
                self.assertDictEqual(ssh_auth.absent(name, user, source), ret)


if __name__ == '__main__':
    from integration import run_tests
    run_tests(SshAuthTestCase, needs_daemon=False)
