'''
Tests for the salt-run command
'''

# Import Salt Testing libs
from salttesting.helpers import ensure_in_syspath
ensure_in_syspath('../../')

# Import salt libs
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
