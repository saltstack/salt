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
from salt.states import serverdensity_device

serverdensity_device.__salt__ = {}


@skipIf(NO_MOCK, NO_MOCK_REASON)
class ServerdensityDeviceTestCase(TestCase):
    '''
    Test cases for salt.states.serverdensity_device
    '''
    # 'monitored' function tests: 1

    def test_monitored(self):
        '''
        Test to device is monitored with Server Density.
        '''
        name = 'my_special_server'

        ret = {'name': name,
               'changes': {},
               'result': True,
               'comment': ''}

        mock_dict = MagicMock(return_value={'id': name})
        mock_t = MagicMock(side_effect=[True, {'agentKey': True},
                                        [{'agentKey': True}]])
        mock_sd = MagicMock(side_effect=[['sd-agent'], [], True])
        with patch.dict(serverdensity_device.__salt__,
                        {'status.all_status': mock_dict,
                         'grains.items': mock_dict,
                         'serverdensity_device.ls': mock_t,
                         'pkg.list_pkgs': mock_sd,
                         'serverdensity_device.install_agent': mock_sd}):
            comt = ('Such server name already exists in this'
                    ' Server Density account. And sd-agent is installed')
            ret.update({'comment': comt})
            self.assertDictEqual(serverdensity_device.monitored(name), ret)

            comt = ('Successfully installed agent and created'
                    ' device in Server Density db.')
            ret.update({'comment': comt, 'changes': {'created_device':
                                                     {'agentKey': True},
                                                     'installed_agent': True}})
            self.assertDictEqual(serverdensity_device.monitored(name), ret)


if __name__ == '__main__':
    from integration import run_tests
    run_tests(ServerdensityDeviceTestCase, needs_daemon=False)
