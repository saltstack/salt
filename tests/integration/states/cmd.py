'''
Tests for the file state
'''
# Import python libs

# Import salt libs
import integration
import tempfile


class CMDTest(integration.ModuleCase):
    '''
    Validate the cmd state
    '''
    def test_run(self):
        '''
        cmd.run
        '''

        ret = self.run_state('cmd.run', name='ls', cwd=tempfile.gettempdir())
        result = ret[next(iter(ret))]['result']
        self.assertTrue(result)

    def test_test_run(self):
        '''
        cmd.run test interface
        '''
        ret = self.run_state('cmd.run', name='ls',
                             cwd=tempfile.gettempdir(), test=True)
        result = ret[next(iter(ret))]['result']
        self.assertIsNone(result)
