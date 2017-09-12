# -*- coding: utf-8 -*-
'''
Test the core grains
'''

# Import python libs
from __future__ import absolute_import

# Import Salt Testing libs
from tests.support.case import ModuleCase
from tests.support.unit import skipIf

# Import Salt libs
import salt.utils.platform
if salt.utils.platform.is_windows():
    try:
        import salt.modules.reg
    except ImportError:
        pass


class TestGrainsCore(ModuleCase):
    '''
    Test the core grains grains
    '''
    @skipIf(not salt.utils.platform.is_windows(), 'Only run on Windows')
    def test_win_cpu_model(self):
        '''
        test grains['cpu_model']
        '''
        opts = self.minion_opts
        cpu_model_text = salt.modules.reg.read_value(
                'HKEY_LOCAL_MACHINE',
                'HARDWARE\\DESCRIPTION\\System\\CentralProcessor\\0',
                'ProcessorNameString').get('vdata')
        self.assertEqual(
            self.run_function('grains.items')['cpu_model'],
            cpu_model_text
        )
