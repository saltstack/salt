# -*- coding: utf-8 -*-
'''
Test the core grains
'''

# Import python libs
from __future__ import absolute_import

# Import Salt Testing libs
import tests.integration as integration
from tests.support.unit import skipIf

# Import salt libs
import salt.utils
if salt.utils.is_windows():
    try:
        import salt.modules.reg
    except ImportError:
        pass


class TestGrainsCore(integration.ModuleCase):
    '''
    Test the core grains grains
    '''
    @skipIf(not salt.utils.is_windows(), 'Only run on Windows')
    def test_win_cpu_model(self):
        '''
        test grains['cpu_model']
        '''
        opts = self.minion_opts
        cpu_model_text = salt.modules.reg.read_value(
                "HKEY_LOCAL_MACHINE",
                "HARDWARE\\DESCRIPTION\\System\\CentralProcessor\\0",
                "ProcessorNameString").get('vdata')
        self.assertEqual(
            self.run_function('grains.items')['cpu_model'],
            cpu_model_text
        )
