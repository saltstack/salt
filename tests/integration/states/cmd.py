'''
Tests for the file state
'''
import tempfile

# Import salt libs
try:
    import integration
except ImportError:
    if __name__ == '__main__':
        import os
        import sys
        sys.path.insert(
            0, os.path.abspath(
                os.path.join(
                    os.path.dirname(__file__), '../../'
                )
            )
        )
    import integration


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
