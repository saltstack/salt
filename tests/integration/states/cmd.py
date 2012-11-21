'''
Tests for the file state
'''
# Import salt libs
import integration
import tempfile


class CMDTest(integration.ModuleCase,
              integration.SaltReturnAssertsMixIn):
    '''
    Validate the cmd state
    '''
    def test_run(self):
        '''
        cmd.run
        '''

        ret = self.run_state('cmd.run', name='ls', cwd=tempfile.gettempdir())
        self.assertSaltTrueReturn(ret)

    def test_test_run(self):
        '''
        cmd.run test interface
        '''
        ret = self.run_state('cmd.run', name='ls',
                             cwd=tempfile.gettempdir(), test=True)
        self.assertSaltNoneReturn(ret)


if __name__ == '__main__':
    from integration import run_tests
    run_tests(CMDTest)
