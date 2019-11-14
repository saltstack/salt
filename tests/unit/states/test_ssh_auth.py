# -*- coding: utf-8 -*-
'''
    :codeauthor: Jayesh Kariya <jayeshk@saltstack.com>
'''
# Import Python libs
from __future__ import absolute_import, unicode_literals, print_function

# Import Salt Testing Libs
from tests.support.mixins import LoaderModuleMockMixin
from tests.support.unit import skipIf, TestCase
from tests.support.mock import (
    NO_MOCK,
    NO_MOCK_REASON,
    MagicMock,
    patch
)

# Import Salt Libs
import salt.states.ssh_auth as ssh_auth


@skipIf(NO_MOCK, NO_MOCK_REASON)
class SshAuthTestCase(TestCase, LoaderModuleMockMixin):
    '''
    Test cases for salt.states.ssh_auth
    '''
    def setup_loader_modules(self):
        return {ssh_auth: {}}

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

    def test_manage(self):
        '''
        Test to verifies that the specified SSH key is absent.
        '''
        user = 'root'
        ret = {'name': '',
               'changes': {},
               'result': None,
               'comment': ''}

        mock_rm = MagicMock(side_effect=['User authorized keys file not present',
                                      'Key removed'])
        mock_up = MagicMock(side_effect=['update', 'updated'])
        mock_set = MagicMock(side_effect=['replace', 'new'])
        mock_keys = MagicMock(return_value={'somekey': {
                        "enc": "ssh-rsa",
                        "comment": "user@host",
                        "options": [],
                        "fingerprint": "b7"}})
        with patch.dict(ssh_auth.__salt__, {'ssh.rm_auth_key': mock_rm,
                                            'ssh.set_auth_key': mock_set,
                                            'ssh.check_key': mock_up,
                                            'ssh.auth_keys': mock_keys}):
            with patch('salt.states.ssh_auth.present') as call_mocked_present:
                mock_present = {'comment': '',
                                'changes': {},
                                'result': None
                               }
                call_mocked_present.return_value = mock_present
                with patch.dict(ssh_auth.__opts__, {'test': True}):
                    # test: expected keys found. No chanages
                    self.assertDictEqual(ssh_auth.manage('sshid', ['somekey'], user), ret)

                    comt = ('somekey Key set for removal')
                    ret.update({'comment': comt})
                    # test: unexpected sshkey found. Should be removed.
                    self.assertDictEqual(ssh_auth.manage('sshid', [], user), ret)

            with patch('salt.states.ssh_auth.present') as call_mocked_present:
                mock_present = {'comment': '',
                                'changes': {},
                                'result': True
                               }
                call_mocked_present.return_value = mock_present
                with patch.dict(ssh_auth.__opts__, {'test': False}):
                    # expected keys found. No changes
                    ret = {'name': '',
                           'changes': {},
                           'result': True,
                           'comment': ''}
                    self.assertDictEqual(ssh_auth.manage('sshid', ['somekey'], user), ret)

                    with patch('salt.states.ssh_auth.absent') as call_mocked_absent:
                        mock_absent = {'comment': 'Key removed'}
                        call_mocked_absent.return_value = mock_absent
                        ret.update({'comment': '', 'result': True,
                                    'changes': {'somekey': 'Key removed'}})
                        # unexpected sshkey found. Was removed.
                        self.assertDictEqual(ssh_auth.manage('sshid', ['addkey'], user), ret)

            # add a key
            with patch('salt.states.ssh_auth.present') as call_mocked_present:
                mock_present = {'comment': 'The authorized host key newkey for user {} was added'.format(user),
                                'changes': {'newkey': 'New'},
                                'result': True
                               }
                call_mocked_present.return_value = mock_present
                with patch.dict(ssh_auth.__opts__, {'test': False}):
                    # added key newkey
                    ret = {'name': '',
                           'changes': {'newkey': 'New'},
                           'result': True,
                           'comment': ''}
                    self.assertDictEqual(ssh_auth.manage('sshid', ['newkey', 'somekey'], user), ret)
