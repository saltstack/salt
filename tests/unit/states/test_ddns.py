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
from salt.states import ddns

ddns.__salt__ = {}
ddns.__opts__ = {}


@skipIf(NO_MOCK, NO_MOCK_REASON)
class DdnsTestCase(TestCase):
    '''
    Test cases for salt.states.ddns
    '''
    # 'present' function tests: 1

    def test_present(self):
        '''
        Test to ensures that the named DNS record is present with the given ttl.
        '''
        name = 'webserver'
        zone = 'example.com'
        ttl = '60'
        data = '111.222.333.444'

        ret = {'name': name, 'result': None, 'comment': '', 'changes': {}}

        with patch.dict(ddns.__opts__, {'test': True}):
            comt = ('A record "{0}" will be updated'.format(name))
            ret.update({'comment': comt})
            self.assertDictEqual(ddns.present(name, zone, ttl, data), ret)

            with patch.dict(ddns.__opts__, {'test': False}):
                mock = MagicMock(return_value=None)
                with patch.dict(ddns.__salt__, {'ddns.update': mock}):
                    comt = ('A record "{0}" already present with ttl of {1}'
                            .format(name, ttl))
                    ret.update({'comment': comt, 'result': True})
                    self.assertDictEqual(ddns.present(name, zone, ttl, data),
                                         ret)

    # 'absent' function tests: 1

    def test_absent(self):
        '''
        Test to ensures that the named DNS record is absent.
        '''
        name = 'webserver'
        zone = 'example.com'
        data = '111.222.333.444'

        ret = {'name': name, 'result': None, 'comment': '', 'changes': {}}

        with patch.dict(ddns.__opts__, {'test': True}):
            comt = ('None record "{0}" will be deleted'.format(name))
            ret.update({'comment': comt})
            self.assertDictEqual(ddns.absent(name, zone, data), ret)

            with patch.dict(ddns.__opts__, {'test': False}):
                mock = MagicMock(return_value=None)
                with patch.dict(ddns.__salt__, {'ddns.delete': mock}):
                    comt = ('No matching DNS record(s) present')
                    ret.update({'comment': comt, 'result': True})
                    self.assertDictEqual(ddns.absent(name, zone, data), ret)
