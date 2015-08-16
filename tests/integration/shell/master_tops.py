# -*- coding: utf-8 -*-
'''
    tests.integration.shell.master_tops
    ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
'''

# Import Python libs
from __future__ import absolute_import

# Import Salt Testing libs
from salttesting.helpers import ensure_in_syspath
ensure_in_syspath('../../')

# Import salt libs
import integration


class MasterTopsTest(integration.ShellCase):

    _call_binary_ = 'salt'

    def test_custom_tops_gets_utilized(self):
        resp = self.run_call(
            'state.show_top'
        )
        self.assertTrue(
            any('master_tops_test' in _x for _x in resp)
        )

if __name__ == '__main__':
    from integration import run_tests
    run_tests(MasterTopsTest)
