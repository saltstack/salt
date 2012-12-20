'''
Tests for the Git state
'''
import os
import shutil
import integration


class GitTest(integration.ModuleCase, integration.SaltReturnAssertsMixIn):
    '''
    Validate the git state
    '''

    def test_latest(self):
        '''
        git.latest
        '''
        name = os.path.join(integration.TMP, 'salt_repo')
        try:
            ret = self.run_state(
                'git.latest',
                name='https://github.com/saltstack/salt.git',
                rev='develop',
                target=name,
                submodules=True
            )
            self.assertSaltTrueReturn(ret)
            self.assertTrue(os.path.isdir(os.path.join(name, '.git')))
        finally:
            shutil.rmtree(name, ignore_errors=True)

    def test_latest_failure(self):
        '''
        git.latest
        '''
        name = os.path.join(integration.TMP, 'salt_repo')
        try:
            ret = self.run_state(
                'git.latest',
                name='https://youSpelledGithubWrong.com/saltstack/salt.git',
                rev='develop',
                target=name,
                submodules=True
            )
            self.assertSaltFalseReturn(ret)
            self.assertFalse(os.path.isdir(os.path.join(name, '.git')))
        finally:
            shutil.rmtree(name, ignore_errors=True)

    def test_latest_empty_dir(self):
        '''
        git.latest
        '''
        name = os.path.join(integration.TMP, 'salt_repo')
        if not os.path.isdir(name):
            os.mkdir(name)
        try:
            ret = self.run_state(
                'git.latest',
                name='https://github.com/saltstack/salt.git',
                rev='develop',
                target=name,
                submodules=True
            )
            self.assertSaltTrueReturn(ret)
            self.assertTrue(os.path.isdir(os.path.join(name, '.git')))
        finally:
            shutil.rmtree(name, ignore_errors=True)

    def test_latest_recursive(self):
        '''
        git.latest
        '''
        name = os.path.join(integration.TMP, 'salt_repo')
        try:
            ret = self.run_state(
                'git.latest',
                name='https://github.com/mozilla/zamboni.git',
                target=name,
                submodules=True
            )
            self.assertSaltTrueReturn(ret)
            self.assertTrue(
                # with git 1.7.9.5, it's not a directory, it's a file with the
                # contents:
                #   gitdir: /tmp/salt-tests-tmpdir/salt_repo/.git/modules/vendor/modules/js/receiptverifier
                #
                # let's change it to exists!?!?!?
                #
                #os.path.isdir(
                os.path.exists(
                    os.path.join(
                        name, 'vendor', 'js', 'receiptverifier', '.git'
                    )
                )
            )
        finally:
            shutil.rmtree(name, ignore_errors=True)

    def test_present(self):
        '''
        git.present
        '''
        name = os.path.join(integration.TMP, 'salt_repo')
        try:
            ret = self.run_state(
                'git.present',
                name=name,
                bare=True
            )
            self.assertSaltTrueReturn(ret)
            self.assertTrue(os.path.isfile(os.path.join(name, 'HEAD')))
        finally:
            shutil.rmtree(name, ignore_errors=True)

    def test_present_failure(self):
        '''
        git.present
        '''
        name = os.path.join(integration.TMP, 'salt_repo')
        if not os.path.isdir(name):
            os.mkdir(name)
        try:
            fname = os.path.join(name, 'stoptheprocess')
            with file(fname, 'a'):
                pass
            ret = self.run_state(
                'git.present',
                name=name,
                bare=True
            )
            self.assertSaltFalseReturn(ret)
            self.assertFalse(os.path.isfile(os.path.join(name, 'HEAD')))
        finally:
            shutil.rmtree(name, ignore_errors=True)

    def test_present_empty_dir(self):
        '''
        git.present
        '''
        name = os.path.join(integration.TMP, 'salt_repo')
        if not os.path.isdir(name):
            os.mkdir(name)
        try:
            ret = self.run_state(
                'git.present',
                name=name,
                bare=True
            )
            self.assertSaltTrueReturn(ret)
            self.assertTrue(os.path.isfile(os.path.join(name, 'HEAD')))
        finally:
            shutil.rmtree(name, ignore_errors=True)


if __name__ == '__main__':
    from integration import run_tests
    run_tests(GitTest)
