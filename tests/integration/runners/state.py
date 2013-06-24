'''
Tests for the salt-run command
'''
# Import python libs
import os
import sys

# Import Salt Modules
try:
    import integration
except ImportError:
    if __name__ == '__main__':
        sys.path.insert(
            0, os.path.abspath(
                os.path.join(
                    os.path.dirname(__file__), '../../'
                )
            )
        )
    import integration


class ManageTest(integration.ShellCase):
    '''
    Test the manage runner
    '''
    def test_over_req_fail(self):
        '''
        state.over
        '''
        os_fn = os.path.join(integration.FILES, 'over/req_fail.sls')
        ret = '\n'.join(self.run_run('state.over os_fn={0}'.format(os_fn)))
        self.assertIn('Requisite fail_stage failed for stage', ret)

    def test_over_parse_req_fail(self):
        '''
        state.over
        '''
        os_fn = os.path.join(integration.FILES, 'over/parse_req_fail.sls')
        ret = '\n'.join(self.run_run('state.over os_fn={0}'.format(os_fn)))
        self.assertIn('Requisite fail_stage failed for stage', ret)


if __name__ == '__main__':
    from integration import run_tests
    run_tests(ManageTest)
