# -*- coding: utf-8 -*-
'''
    :codeauthor: :email:`Jayesh Kariya <jayeshk@saltstack.com>`
'''
# Import Python libs
from __future__ import absolute_import
import os

# Import Salt Testing Libs
from tests.support.unit import skipIf, TestCase
from tests.support.mock import (
    NO_MOCK,
    NO_MOCK_REASON,
    MagicMock,
    mock_open,
    patch)

# Import Salt Libs
import salt.states.virt as virt
import salt.utils

virt.__salt__ = {}
virt.__opts__ = {}


@skipIf(NO_MOCK, NO_MOCK_REASON)
class LibvirtTestCase(TestCase):
    '''
    Test cases for salt.states.libvirt
    '''
    # 'keys' function tests: 1

    @skipIf(os.geteuid() != 0, 'you must be root to run this test')
    @patch('os.path.isfile', MagicMock(return_value=False))
    def test_keys(self):
        '''
        Test to manage libvirt keys.
        '''
        name = 'sunrise'

        ret = {'name': name,
               'result': True,
               'comment': '',
               'changes': {}}

        mock = MagicMock(side_effect=[[], ['libvirt.servercert.pem'],
                                      {'libvirt.servercert.pem': 'A'}])
        with patch.dict(virt.__salt__, {'pillar.ext': mock}):
            comt = ('All keys are correct')
            ret.update({'comment': comt})
            self.assertDictEqual(virt.keys(name), ret)

            with patch.dict(virt.__opts__, {'test': True}):
                comt = ('Libvirt keys are set to be updated')
                ret.update({'comment': comt, 'result': None})
                self.assertDictEqual(virt.keys(name), ret)

            with patch.dict(virt.__opts__, {'test': False}):
                with patch.object(salt.utils, 'fopen', MagicMock(mock_open())):
                    comt = ('Updated libvirt certs and keys')
                    ret.update({'comment': comt, 'result': True,
                                'changes': {'servercert': 'new'}})
                    self.assertDictEqual(virt.keys(name), ret)
