# -*- coding: utf-8 -*-

'''
Tests for the salt-run command
'''
# Import python libs
import os

# Import Salt Testing libs
from salttesting.helpers import ensure_in_syspath
ensure_in_syspath('../../')

# Import salt libs
import integration


class ManageTest(integration.ShellCase):
    '''
    Test the manage runner
    '''
    def test_over_req_fail(self):
        '''
        state.over
        '''
        os_fn = os.path.join(integration.FILES, 'over', 'req_fail.sls')
        ret = '\n'.join(self.run_run('state.over os_fn={0}'.format(os_fn)))
        items = (
                'Requisite fail_stage failed for stage',
                'Executing the following Over State:',
                )
        self.assertTrue(any(item in ret for item in items))

    def test_over_parse_req_fail(self):
        '''
        state.over
        '''
        os_fn = os.path.join(integration.FILES, 'over', 'parse_req_fail.sls')
        ret = '\n'.join(self.run_run('state.over os_fn={0}'.format(os_fn)))
        items = (
                'Requisite fail_stage failed for stage',
                'Executing the following Over State:',
                )
        self.assertTrue(any(item in ret for item in items))


if __name__ == '__main__':
    from integration import run_tests
    run_tests(ManageTest)
