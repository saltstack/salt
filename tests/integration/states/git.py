# -*- coding: utf-8 -*-
'''
Tests for the Git state
'''

# Import python libs
from __future__ import absolute_import
import os
import shutil
import socket
import subprocess
import tempfile

# Import Salt Testing libs
from salttesting.helpers import ensure_in_syspath, skip_if_binaries_missing
ensure_in_syspath('../../')

# Import salt libs
import integration
import salt.utils


class GitTest(integration.ModuleCase, integration.SaltReturnAssertsMixIn):
    '''
    Validate the git state
    '''

    def setUp(self):
        super(GitTest, self).setUp()
        self.__domain = 'github.com'
        try:
            if hasattr(socket, 'setdefaulttimeout'):
                # 10 second dns timeout
                socket.setdefaulttimeout(10)
            socket.gethostbyname(self.__domain)
        except socket.error:
            msg = 'error resolving {0}, possible network issue?'
            self.skipTest(msg.format(self.__domain))

    def test_latest(self):
        '''
        git.latest
        '''
        name = os.path.join(integration.TMP, 'salt_repo')
        try:
            ret = self.run_state(
                'git.latest',
                name='https://{0}/saltstack/salt-test-repo.git'.format(self.__domain),
                target=name
            )
            self.assertSaltTrueReturn(ret)
            self.assertTrue(os.path.isdir(os.path.join(name, '.git')))
        finally:
            shutil.rmtree(name, ignore_errors=True)

    def test_latest_with_rev_and_submodules(self):
        '''
        git.latest
        '''
        name = os.path.join(integration.TMP, 'salt_repo')
        try:
            ret = self.run_state(
                'git.latest',
                name='https://{0}/saltstack/salt-test-repo.git'.format(self.__domain),
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
                name='https://youSpelledGitHubWrong.com/saltstack/salt-test-repo.git',
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
                name='https://{0}/saltstack/salt-test-repo.git'.format(self.__domain),
                rev='develop',
                target=name,
                submodules=True
            )
            self.assertSaltTrueReturn(ret)
            self.assertTrue(os.path.isdir(os.path.join(name, '.git')))
        finally:
            shutil.rmtree(name, ignore_errors=True)

    def test_latest_unless_no_cwd_issue_6800(self):
        '''
        cwd=target was being passed to _run_check which blew up if
        target dir did not already exist.
        '''
        name = os.path.join(integration.TMP, 'salt_repo')
        if os.path.isdir(name):
            shutil.rmtree(name)
        try:
            ret = self.run_state(
                'git.latest',
                name='https://{0}/saltstack/salt-test-repo.git'.format(self.__domain),
                rev='develop',
                target=name,
                unless='test -e {0}'.format(name),
                submodules=True
            )
            self.assertSaltTrueReturn(ret)
            self.assertTrue(os.path.isdir(os.path.join(name, '.git')))
        finally:
            shutil.rmtree(name, ignore_errors=True)

    def test_numeric_rev(self):
        '''
        git.latest with numeric revision
        '''
        name = os.path.join(integration.TMP, 'salt_repo')
        try:
            ret = self.run_state(
                'git.latest',
                name='https://{0}/saltstack/salt-test-repo.git'.format(self.__domain),
                rev=0.11,
                target=name,
                submodules=True,
                timeout=120
            )
            self.assertSaltTrueReturn(ret)
            self.assertTrue(os.path.isdir(os.path.join(name, '.git')))
        finally:
            shutil.rmtree(name, ignore_errors=True)

    def test_latest_with_local_changes(self):
        '''
        Ensure that we fail the state when there are local changes and succeed
        when force_reset is True.
        '''
        name = os.path.join(integration.TMP, 'salt_repo')
        try:
            # Clone repo
            ret = self.run_state(
                'git.latest',
                name='https://{0}/saltstack/salt-test-repo.git'.format(self.__domain),
                target=name
            )
            self.assertSaltTrueReturn(ret)
            self.assertTrue(os.path.isdir(os.path.join(name, '.git')))

            # Make change to LICENSE file.
            with salt.utils.fopen(os.path.join(name, 'LICENSE'), 'a') as fp_:
                fp_.write('Lorem ipsum dolor blah blah blah....\n')

            # Make sure that we now have uncommitted changes
            self.assertTrue(self.run_function('git.diff', [name, 'HEAD']))

            # Re-run state with force_reset=False, this should fail
            ret = self.run_state(
                'git.latest',
                name='https://{0}/saltstack/salt-test-repo.git'.format(self.__domain),
                target=name,
                force_reset=False
            )
            self.assertSaltFalseReturn(ret)

            # Now run the state with force_reset=True, this should succeed
            ret = self.run_state(
                'git.latest',
                name='https://{0}/saltstack/salt-test-repo.git'.format(self.__domain),
                target=name,
                force_reset=True
            )
            self.assertSaltTrueReturn(ret)

            # Make sure that we no longer have uncommitted changes
            self.assertFalse(self.run_function('git.diff', [name, 'HEAD']))

        finally:
            shutil.rmtree(name, ignore_errors=True)

    def test_latest_fast_forward(self):
        '''
        Test running git.latest state a second time after changes have been
        made to the remote repo.
        '''
        def _head(cwd):
            return self.run_function('git.rev_parse', [cwd, 'HEAD'])

        repo_url = 'https://{0}/saltstack/salt-test-repo.git'.format(self.__domain)
        mirror_dir = os.path.join(integration.TMP, 'salt_repo_mirror')
        mirror_url = 'file://' + mirror_dir
        admin_dir = os.path.join(integration.TMP, 'salt_repo_admin')
        clone_dir = os.path.join(integration.TMP, 'salt_repo')

        try:
            # Mirror the repo
            self.run_function('git.clone',
                              [mirror_dir, repo_url, None, '--mirror'])

            # Make sure the directory for the mirror now exists
            self.assertTrue(os.path.exists(mirror_dir))

            # Clone the mirror twice, once to the admin location and once to
            # the clone_dir
            ret = self.run_state('git.latest', name=mirror_url, target=admin_dir)
            self.assertSaltTrueReturn(ret)
            ret = self.run_state('git.latest', name=mirror_url, target=clone_dir)
            self.assertSaltTrueReturn(ret)

            # Make a change to the repo by editing the file in the admin copy
            # of the repo and committing.
            head_pre = _head(admin_dir)
            with open(os.path.join(admin_dir, 'LICENSE'), 'a') as fp_:
                fp_.write('Hello world!')
            self.run_function('git.commit', [admin_dir, 'Added a line', '-a'])
            # Make sure HEAD is pointing to a new SHA so we know we properly
            # committed our change.
            head_post = _head(admin_dir)
            self.assertNotEqual(head_pre, head_post)

            # Push the change to the mirror
            # NOTE: the test will fail if the salt-test-repo's default branch
            # is changed.
            self.run_function('git.push', [admin_dir, 'origin', 'develop'])

            # Re-run the git.latest state on the clone_dir
            ret = self.run_state('git.latest', name=mirror_url, target=clone_dir)
            self.assertSaltTrueReturn(ret)

            # Make sure that the clone_dir now has the correct SHA
            self.assertEqual(head_post, _head(clone_dir))

        finally:
            for path in (mirror_dir, admin_dir, clone_dir):
                shutil.rmtree(path, ignore_errors=True)

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

            with salt.utils.fopen(fname, 'a') as fh_:
                fh_.write('')

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

    @skip_if_binaries_missing('git')
    def test_config_set_value_with_space_character(self):
        '''
        git.config
        '''
        name = tempfile.mkdtemp(dir=integration.TMP)
        self.addCleanup(shutil.rmtree, name, ignore_errors=True)
        subprocess.check_call(['git', 'init', '--quiet', name])

        ret = self.run_state(
            'git.config_set',
            name='user.name',
            value='foo bar',
            repo=name,
            **{'global': False})
        self.assertSaltTrueReturn(ret)


if __name__ == '__main__':
    from integration import run_tests
    run_tests(GitTest)
