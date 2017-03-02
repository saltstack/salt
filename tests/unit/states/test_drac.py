# -*- coding: utf-8 -*-
'''
    :codeauthor: :email:`Jayesh Kariya <jayeshk@saltstack.com>`
'''
# Import Python libs
from __future__ import absolute_import

# Import Salt Testing Libs
from tests.support.unit import skipIf, TestCase
from tests.support.mock import (
    NO_MOCK,
    NO_MOCK_REASON,
    MagicMock,
    patch)

# Import Salt Libs
from salt.states import drac

drac.__salt__ = {}
drac.__opts__ = {}


@skipIf(NO_MOCK, NO_MOCK_REASON)
class DracTestCase(TestCase):
    '''
    Test cases for salt.states.drac
    '''
    # 'present' function tests: 1

    def test_present(self):
        '''
        Test to ensure the user exists on the Dell DRAC
        '''
        name = 'damian'
        password = 'secret'
        permission = 'login,test_alerts,clear_logs'

        ret = {'name': name,
               'result': True,
               'comment': '',
               'changes': {}}

        mock = MagicMock(return_value=[name])
        with patch.dict(drac.__salt__, {'drac.list_users': mock}):
            with patch.dict(drac.__opts__, {'test': True}):
                comt = ('`{0}` already exists'.format(name))
                ret.update({'comment': comt})
                self.assertDictEqual(drac.present(name, password, permission),
                                     ret)

            with patch.dict(drac.__opts__, {'test': False}):
                comt = ('`{0}` already exists'.format(name))
                ret.update({'comment': comt})
                self.assertDictEqual(drac.present(name, password, permission),
                                     ret)

    # 'absent' function tests: 1

    def test_absent(self):
        '''
        Test to ensure a user does not exist on the Dell DRAC
        '''
        name = 'damian'

        ret = {'name': name,
               'result': True,
               'comment': '',
               'changes': {}}

        mock = MagicMock(return_value=[])
        with patch.dict(drac.__salt__, {'drac.list_users': mock}):
            with patch.dict(drac.__opts__, {'test': True}):
                comt = ('`{0}` does not exist'.format(name))
                ret.update({'comment': comt})
                self.assertDictEqual(drac.absent(name), ret)

            with patch.dict(drac.__opts__, {'test': False}):
                comt = ('`{0}` does not exist'.format(name))
                ret.update({'comment': comt})
                self.assertDictEqual(drac.absent(name), ret)

    # 'network' function tests: 1

    def test_network(self):
        '''
        Test to ensure the DRAC network settings are consistent
        '''
        ip_ = '10.225.108.29'
        netmask = '255.255.255.224'
        gateway = '10.225.108.1'

        ret = {'name': ip_,
               'result': None,
               'comment': '',
               'changes': {}}

        net_info = {'IPv4 settings': {'IP Address': ip_, 'Subnet Mask': netmask,
                                      'Gateway': gateway}}

        mock_info = MagicMock(return_value=net_info)
        mock_bool = MagicMock(side_effect=[True, False])
        with patch.dict(drac.__salt__, {'drac.network_info': mock_info,
                                        'drac.set_network': mock_bool}):
            with patch.dict(drac.__opts__, {'test': True}):
                self.assertDictEqual(drac.network(ip_, netmask, gateway), ret)

            with patch.dict(drac.__opts__, {'test': False}):
                comt = ('Network is in the desired state')
                ret.update({'comment': comt, 'result': True})
                self.assertDictEqual(drac.network(ip_, netmask, gateway), ret)

                comt = ('unable to configure network')
                ret.update({'comment': comt, 'result': False})
                self.assertDictEqual(drac.network(ip_, netmask, gateway), ret)
