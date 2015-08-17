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
    patch)

from salttesting.helpers import ensure_in_syspath
from salt.exceptions import CommandExecutionError

ensure_in_syspath('../../')

# Import Salt Libs
from salt.states import openstack_config

openstack_config.__salt__ = {}
openstack_config.__opts__ = {}


@skipIf(NO_MOCK, NO_MOCK_REASON)
class OpenstackConfigTestCase(TestCase):
    '''
    Test cases for salt.states.openstack_config
    '''
    # 'present' function tests: 1

    def test_present(self):
        '''
        Test to ensure a value is set in an OpenStack configuration file.
        '''
        name = 'salt'
        filename = '/tmp/salt'
        section = 'A'
        value = 'SALT'

        ret = {'name': name,
               'result': False,
               'comment': '',
               'changes': {}}

        mock_lst = MagicMock(side_effect=[value, CommandExecutionError, 'A'])
        mock_t = MagicMock(return_value=True)
        with patch.dict(openstack_config.__salt__,
                        {'openstack_config.get': mock_lst,
                         'openstack_config.set': mock_t}):
            comt = ('The value is already set to the correct value')
            ret.update({'comment': comt, 'result': True})
            self.assertDictEqual(openstack_config.present(name, filename,
                                                          section, value), ret)

            self.assertRaises(CommandExecutionError, openstack_config.present,
                              name, filename, section, value)

            comt = ('The value has been updated')
            ret.update({'comment': comt, 'changes': {'Value': 'Updated'}})
            self.assertDictEqual(openstack_config.present(name, filename,
                                                          section, value), ret)

    # 'absent' function tests: 1

    def test_absent(self):
        '''
        Test to ensure a value is not set in an OpenStack configuration file.
        '''
        name = 'salt'
        filename = '/tmp/salt'
        section = 'A'

        ret = {'name': name,
               'result': False,
               'comment': '',
               'changes': {}}

        mock_lst = MagicMock(side_effect=[CommandExecutionError
                                          ('parameter not found:'),
                                          CommandExecutionError, 'A'])
        mock_t = MagicMock(return_value=True)
        with patch.dict(openstack_config.__salt__,
                        {'openstack_config.get': mock_lst,
                         'openstack_config.delete': mock_t}):
            comt = ('The value is already absent')
            ret.update({'comment': comt, 'result': True})
            self.assertDictEqual(openstack_config.absent(name, filename,
                                                         section), ret)

            self.assertRaises(CommandExecutionError, openstack_config.absent,
                              name, filename, section)

            comt = ('The value has been deleted')
            ret.update({'comment': comt, 'changes': {'Value': 'Deleted'}})
            self.assertDictEqual(openstack_config.absent(name, filename,
                                                         section), ret)


if __name__ == '__main__':
    from integration import run_tests
    run_tests(OpenstackConfigTestCase, needs_daemon=False)
