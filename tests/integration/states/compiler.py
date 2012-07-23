'''
tests for host state
'''
import integration


class CompileTest(integration.ModuleCase):
    '''
    Validate the state compiler
    '''
    def test_multi_state(self):
        '''
        Test the error with multiple states of the same type
        '''
        ret = self.run_function('state.sls', mods='fuzz.multi_state')
        # Verify that the return is a list, aka, an error
        self.assertIsInstance(ret, list)


if __name__ == '__main__':
    from integration import run_tests
    run_tests(CompileTest)
