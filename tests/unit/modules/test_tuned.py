# -*- coding: utf-8 -*-
from __future__ import absolute_import

from salt.modules import tuned

from tests.support.mixins import LoaderModuleMockMixin
from tests.support.unit import skipIf, TestCase
from tests.support.mock import (
    MagicMock,
    NO_MOCK,
    NO_MOCK_REASON,
    patch,
)


@skipIf(NO_MOCK, NO_MOCK_REASON)
class TunedListTestCase(TestCase, LoaderModuleMockMixin):
    '''
    Test the tuned.list_() method for different versions of tuned-adm
    '''
    def setup_loader_modules(self):
        return {tuned: {}}

    def test_v_241(self):
        '''
        Test the list_ function for older tuned-adm (v2.4.1)
        as shipped with CentOS-6
        '''
        tuned_list = '''Available profiles:
- throughput-performance
- virtual-guest
- latency-performance
- laptop-battery-powersave
- laptop-ac-powersave
- virtual-host
- desktop-powersave
- server-powersave
- spindown-disk
- sap
- enterprise-storage
- default
Current active profile: throughput-performance'''
        mock_cmd = MagicMock(return_value=tuned_list)
        with patch.dict(tuned.__salt__, {'cmd.run': mock_cmd}):
            self.assertEqual(
                tuned.list_(),
                ['throughput-performance', 'virtual-guest',
                 'latency-performance', 'laptop-battery-powersave',
                 'laptop-ac-powersave', 'virtual-host',
                 'desktop-powersave', 'server-powersave',
                 'spindown-disk', 'sap', 'enterprise-storage', 'default'])

    def test_v_271(self):
        '''
        Test the list_ function for newer tuned-adm (v2.7.1)
        as shipped with CentOS-7
        '''
        tuned_list = '''Available profiles:
- balanced                    - General non-specialized tuned profile
- desktop                     - Optmize for the desktop use-case
- latency-performance         - Optimize for deterministic performance
- network-latency             - Optimize for deterministic performance
- network-throughput          - Optimize for streaming network throughput.
- powersave                   - Optimize for low power-consumption
- throughput-performance      - Broadly applicable tuning that provides--
- virtual-guest               - Optimize for running inside a virtual-guest.
- virtual-host                - Optimize for running KVM guests
Current active profile: virtual-guest
'''
        mock_cmd = MagicMock(return_value=tuned_list)
        with patch.dict(tuned.__salt__, {'cmd.run': mock_cmd}):
            self.assertEqual(
                tuned.list_(),
                ['balanced', 'desktop', 'latency-performance',
                 'network-latency', 'network-throughput', 'powersave',
                 'throughput-performance', 'virtual-guest',
                 'virtual-host'])
