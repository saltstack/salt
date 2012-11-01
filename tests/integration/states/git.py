'''
Tests for the Git state
'''
import os
import shutil
import integration


class GitTest(integration.ModuleCase):
    '''
    Validate the git state
    '''

    def test_latest(self):
        '''
        git.latest
        '''
        name = os.path.join(integration.TMP, 'salt_repo')
        ret = self.run_state(
            'git.latest',
            name='https://github.com/saltstack/salt.git',
            rev='develop',
            target=name,
            submodules=True
        )
        self.assertTrue(os.path.isdir(os.path.join(name, '.git')))
        result = self.state_result(ret)
        self.assertTrue(result)
        shutil.rmtree(name, ignore_errors=True)

    def test_latest_failure(self):
        '''
        git.latest
        '''
        name = os.path.join(integration.TMP, 'salt_repo')
        ret = self.run_state(
            'git.latest',
            name='https://youSpelledGithubWrong.com/saltstack/salt.git',
            rev='develop',
            target=name,
            submodules=True
        )
        self.assertFalse(os.path.isdir(os.path.join(name, '.git')))
        result = self.state_result(ret)
        self.assertFalse(result)
        shutil.rmtree(name, ignore_errors=True)

    def test_present(self):
        '''
        git.present
        '''
        name = os.path.join(integration.TMP, 'salt_repo')
        ret = self.run_state(
            'git.present',
            name=name,
            bare=True
        )
        self.assertTrue(os.path.isfile(os.path.join(name, 'HEAD')))
        result = self.state_result(ret)
        self.assertTrue(result)
        shutil.rmtree(name, ignore_errors=True)

    def test_present_failure(self):
        '''
        git.present
        '''
        name = os.path.join(integration.TMP, 'salt_repo')
        os.mkdir(name)
        fname = os.path.join(name, 'stoptheprocess')
        with file(fname, 'a'):
            pass
        ret = self.run_state(
            'git.present',
            name=name,
            bare=True
        )
        self.assertFalse(os.path.isfile(os.path.join(name, 'HEAD')))
        result = self.state_result(ret)
        self.assertFalse(result)
        shutil.rmtree(name, ignore_errors=True)


if __name__ == '__main__':
    from integration import run_tests
    run_tests(GitTest)
