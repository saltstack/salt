'''
Tests for the salt-run command
'''
# Import python libs
import sys

# Import Salt Modules
try:
    import integration
except ImportError:
    if __name__ == '__main__':
        import os
        sys.path.insert(
            0, os.path.abspath(
                os.path.join(
                    os.path.dirname(__file__), '../../'
                )
            )
        )
    import integration


class RunTest(integration.ShellCase, integration.ShellCaseCommonTestsMixIn):
    '''
    Test the salt-run command
    '''

    _call_binary_ = 'salt-run'

    def test_in_docs(self):
        '''
        test the salt-run docs system
        '''
        data = self.run_run('-d')
        data = '\n'.join(data)
        self.assertIn('jobs.active:', data)
        self.assertIn('jobs.list_jobs:', data)
        self.assertIn('jobs.lookup_jid:', data)
        self.assertIn('manage.down:', data)
        self.assertIn('manage.up:', data)
        self.assertIn('network.wol:', data)
        self.assertIn('network.wollist:', data)

    def test_notin_docs(self):
        '''
        Verify that hidden methods are not in run docs
        '''
        data = self.run_run('-d')
        data = '\n'.join(data)
        self.assertNotIn('jobs.SaltException:', data)


if __name__ == '__main__':
    from integration import run_tests
    run_tests(RunTest)
