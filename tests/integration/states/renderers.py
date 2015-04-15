# coding: utf-8
'''
Integration tests for renderer functions
'''

# Import Salt Testing libs
from salttesting.helpers import ensure_in_syspath
ensure_in_syspath('../../')

# Import salt libs
import integration


class TestJinjaRenderer(integration.ModuleCase):
    '''
    Validate that ordering works correctly
    '''
    def test_dot_notation(self):
        '''
        Test the Jinja dot-notation syntax for calling execution modules
        '''
        ret = self.run_function('state.sls', ['jinja_dot_notation'])
        for state_ret in ret.values():
            self.assertTrue(state_ret['result'])


if __name__ == '__main__':
    from integration import run_tests
    run_tests(TestJinjaRenderer)
