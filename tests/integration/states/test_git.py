# -*- coding: utf-8 -*-
'''
Tests for the Git state
'''

# Import python libs
from __future__ import absolute_import
import errno
import os
import shutil
import socket
import string
import tempfile

# Import Salt Testing libs
from tests.support.case import ModuleCase
from tests.support.paths import TMP
from tests.support.helpers import skip_if_binaries_missing
from tests.support.mixins import SaltReturnAssertsMixin

# Import salt libs
import salt.utils


@skip_if_binaries_missing('git')
class GitTest(ModuleCase, SaltReturnAssertsMixin):
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

    def tearDown(self):
        # Reset the dns timeout after the test is over
        socket.setdefaulttimeout(None)

    def test_latest(self):
        '''
        git.latest
        '''
        name = os.path.join(TMP, 'salt_repo')
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
        name = os.path.join(TMP, 'salt_repo')
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
        name = os.path.join(TMP, 'salt_repo')
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
        name = os.path.join(TMP, 'salt_repo')
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
        name = os.path.join(TMP, 'salt_repo')
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
        name = os.path.join(TMP, 'salt_repo')
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
        name = os.path.join(TMP, 'salt_repo')
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

            # Re-run state with force_reset=False
            ret = self.run_state(
                'git.latest',
                name='https://{0}/saltstack/salt-test-repo.git'.format(self.__domain),
                target=name,
                force_reset=False
            )
            self.assertSaltTrueReturn(ret)
            self.assertEqual(
                ret[next(iter(ret))]['comment'],
                ('Repository {0} is up-to-date, but with local changes. Set '
                 '\'force_reset\' to True to purge local changes.'.format(name))
            )

            # Now run the state with force_reset=True
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
        mirror_dir = os.path.join(TMP, 'salt_repo_mirror')
        mirror_url = 'file://' + mirror_dir
        admin_dir = os.path.join(TMP, 'salt_repo_admin')
        clone_dir = os.path.join(TMP, 'salt_repo')

        try:
            # Mirror the repo
            self.run_function(
                'git.clone', [mirror_dir], url=repo_url, opts='--mirror')

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
            self.run_function(
                'git.commit', [admin_dir, 'added a line'],
                git_opts='-c user.name="Foo Bar" -c user.email=foo@bar.com',
                opts='-a',
            )
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

    def _changed_local_branch_helper(self, rev, hint):
        '''
        We're testing two almost identical cases, the only thing that differs
        is the rev used for the git.latest state.
        '''
        name = os.path.join(TMP, 'salt_repo')
        try:
            # Clone repo
            ret = self.run_state(
                'git.latest',
                name='https://{0}/saltstack/salt-test-repo.git'.format(self.__domain),
                rev=rev,
                target=name
            )
            self.assertSaltTrueReturn(ret)

            # Check out a new branch in the clone and make a commit, to ensure
            # that when we re-run the state, it is not a fast-forward change
            self.run_function('git.checkout', [name, 'new_branch'], opts='-b')
            with salt.utils.fopen(os.path.join(name, 'foo'), 'w'):
                pass
            self.run_function('git.add', [name, '.'])
            self.run_function(
                'git.commit', [name, 'add file'],
                git_opts='-c user.name="Foo Bar" -c user.email=foo@bar.com',
            )

            # Re-run the state, this should fail with a specific hint in the
            # comment field.
            ret = self.run_state(
                'git.latest',
                name='https://{0}/saltstack/salt-test-repo.git'.format(self.__domain),
                rev=rev,
                target=name
            )
            self.assertSaltFalseReturn(ret)

            comment = ret[next(iter(ret))]['comment']
            self.assertTrue(hint in comment)
        finally:
            shutil.rmtree(name, ignore_errors=True)

    def test_latest_changed_local_branch_rev_head(self):
        '''
        Test for presence of hint in failure message when the local branch has
        been changed and a the rev is set to HEAD

        This test will fail if the default branch for the salt-test-repo is
        ever changed.
        '''
        self._changed_local_branch_helper(
            'HEAD',
            'The default remote branch (develop) differs from the local '
            'branch (new_branch)'
        )

    def test_latest_changed_local_branch_rev_develop(self):
        '''
        Test for presence of hint in failure message when the local branch has
        been changed and a non-HEAD rev is specified
        '''
        self._changed_local_branch_helper(
            'develop',
            'The desired rev (develop) differs from the name of the local '
            'branch (new_branch)'
        )

    def test_latest_updated_remote_rev(self):
        '''
        Ensure that we don't exit early when checking for a fast-forward
        '''
        name = tempfile.mkdtemp(dir=TMP)
        target = os.path.join(TMP, 'test_latest_updated_remote_rev')

        # Initialize a new git repository
        self.run_function('git.init', [name])

        try:
            # Add and commit a file
            with salt.utils.fopen(os.path.join(name, 'foo.txt'), 'w') as fp_:
                fp_.write('Hello world\n')
            self.run_function('git.add', [name, '.'])
            self.run_function(
                'git.commit', [name, 'initial commit'],
                git_opts='-c user.name="Foo Bar" -c user.email=foo@bar.com',
            )

            # Run the state to clone the repo we just created
            ret = self.run_state(
                'git.latest',
                name=name,
                target=target,
            )
            self.assertSaltTrueReturn(ret)

            # Add another commit
            with salt.utils.fopen('foo.txt', 'w') as fp_:
                fp_.write('Added a line\n')
            self.run_function(
                'git.commit', [name, 'added a line'],
                git_opts='-c user.name="Foo Bar" -c user.email=foo@bar.com',
                opts='-a',
            )

            # Run the state again. It should pass, if it doesn't then there was
            # a problem checking whether or not the change is a fast-forward.
            ret = self.run_state(
                'git.latest',
                name=name,
                target=target,
            )
            self.assertSaltTrueReturn(ret)
        finally:
            for path in (name, target):
                try:
                    shutil.rmtree(path)
                except OSError as exc:
                    if exc.errno != errno.ENOENT:
                        raise exc

    def test_present(self):
        '''
        git.present
        '''
        name = os.path.join(TMP, 'salt_repo')
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
        name = os.path.join(TMP, 'salt_repo')
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
        name = os.path.join(TMP, 'salt_repo')
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

    def test_config_set_value_with_space_character(self):
        '''
        git.config
        '''
        name = tempfile.mkdtemp(dir=TMP)
        self.addCleanup(shutil.rmtree, name, ignore_errors=True)
        self.run_function('git.init', [name])

        ret = self.run_state(
            'git.config_set',
            name='user.name',
            value='foo bar',
            repo=name,
            **{'global': False})
        self.assertSaltTrueReturn(ret)


@skip_if_binaries_missing('git')
class LocalRepoGitTest(ModuleCase, SaltReturnAssertsMixin):
    '''
    Tests which do no require connectivity to github.com
    '''
    def test_renamed_default_branch(self):
        '''
        Test the case where the remote branch has been removed
        https://github.com/saltstack/salt/issues/36242
        '''
        repo = tempfile.mkdtemp(dir=TMP)
        admin = tempfile.mkdtemp(dir=TMP)
        name = tempfile.mkdtemp(dir=TMP)
        for dirname in (repo, admin, name):
            self.addCleanup(shutil.rmtree, dirname, ignore_errors=True)

        # Create bare repo
        self.run_function('git.init', [repo], bare=True)
        # Clone bare repo
        self.run_function('git.clone', [admin], url=repo)
        # Create, add, commit, and push file
        with salt.utils.fopen(os.path.join(admin, 'foo'), 'w'):
            pass
        self.run_function('git.add', [admin, '.'])
        self.run_function(
            'git.commit', [admin, 'initial commit'],
            git_opts='-c user.name="Foo Bar" -c user.email=foo@bar.com',
        )
        self.run_function('git.push', [admin], remote='origin', ref='master')

        # Rename remote 'master' branch to 'develop'
        os.rename(
            os.path.join(repo, 'refs', 'heads', 'master'),
            os.path.join(repo, 'refs', 'heads', 'develop')
        )

        # Run git.latest state. This should successfuly clone and fail with a
        # specific error in the comment field.
        ret = self.run_state(
            'git.latest',
            name=repo,
            target=name,
            rev='develop',
        )
        self.assertSaltFalseReturn(ret)
        self.assertEqual(
            ret[next(iter(ret))]['comment'],
            'Remote HEAD refers to a ref that does not exist. '
            'This can happen when the default branch on the '
            'remote repository is renamed or deleted. If you '
            'are unable to fix the remote repository, you can '
            'work around this by setting the \'branch\' argument '
            '(which will ensure that the named branch is created '
            'if it does not already exist).\n\n'
            'Changes already made: {0} cloned to {1}'
            .format(repo, name)
        )
        self.assertEqual(
            ret[next(iter(ret))]['changes'],
            {'new': '{0} => {1}'.format(repo, name)}
        )

        # Run git.latest state again. This should fail again, with a different
        # error in the comment field, and should not change anything.
        ret = self.run_state(
            'git.latest',
            name=repo,
            target=name,
            rev='develop',
        )
        self.assertSaltFalseReturn(ret)
        self.assertEqual(
            ret[next(iter(ret))]['comment'],
            'Cannot set/unset upstream tracking branch, local '
            'HEAD refers to nonexistent branch. This may have '
            'been caused by cloning a remote repository for which '
            'the default branch was renamed or deleted. If you '
            'are unable to fix the remote repository, you can '
            'work around this by setting the \'branch\' argument '
            '(which will ensure that the named branch is created '
            'if it does not already exist).'
        )
        self.assertEqual(ret[next(iter(ret))]['changes'], {})

        # Run git.latest state again with a branch manually set. This should
        # checkout a new branch and the state should pass.
        ret = self.run_state(
            'git.latest',
            name=repo,
            target=name,
            rev='develop',
            branch='develop',
        )
        # State should succeed
        self.assertSaltTrueReturn(ret)
        self.assertSaltCommentRegexpMatches(
            ret,
            'New branch \'develop\' was checked out, with origin/develop '
            r'\([0-9a-f]{7}\) as a starting point'
        )
        # Only the revision should be in the changes dict.
        self.assertEqual(
            list(ret[next(iter(ret))]['changes'].keys()),
            ['revision']
        )
        # Since the remote repo was incorrectly set up, the local head should
        # not exist (therefore the old revision should be None).
        self.assertEqual(
            ret[next(iter(ret))]['changes']['revision']['old'],
            None
        )
        # Make sure the new revision is a SHA (40 chars, all hex)
        self.assertTrue(
            len(ret[next(iter(ret))]['changes']['revision']['new']) == 40)
        self.assertTrue(
            all([x in string.hexdigits for x in
                 ret[next(iter(ret))]['changes']['revision']['new']])
        )
