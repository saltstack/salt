# -*- coding: utf-8 -*-
'''
Tests for the Git state
'''

# Import python libs
from __future__ import absolute_import, print_function, unicode_literals
import errno
import functools
import inspect
import os
import shutil
import socket
import string
import tempfile

# Import Salt Testing libs
from tests.support.case import ModuleCase
from tests.support.paths import TMP
from tests.support.mixins import SaltReturnAssertsMixin

# Import salt libs
import salt.utils.files
import salt.utils.path
from salt.utils.versions import LooseVersion as _LooseVersion


def __check_git_version(caller, min_version, skip_msg):
    '''
    Common logic for version check
    '''
    if inspect.isclass(caller):
        actual_setup = getattr(caller, 'setUp', None)

        def setUp(self, *args, **kwargs):
            if not salt.utils.path.which('git'):
                self.skipTest('git is not installed')
            git_version = self.run_function('git.version')
            if _LooseVersion(git_version) < _LooseVersion(min_version):
                self.skipTest(skip_msg.format(min_version, git_version))
            if actual_setup is not None:
                actual_setup(self, *args, **kwargs)
        caller.setUp = setUp
        return caller

    @functools.wraps(caller)
    def wrapper(self, *args, **kwargs):
        if not salt.utils.path.which('git'):
            self.skipTest('git is not installed')
        git_version = self.run_function('git.version')
        if _LooseVersion(git_version) < _LooseVersion(min_version):
            self.skipTest(skip_msg.format(min_version, git_version))
        return caller(self, *args, **kwargs)
    return wrapper


def ensure_min_git(caller):
    '''
    Skip test if minimum supported git version is not installed
    '''
    min_version = '1.6.5'
    return __check_git_version(
        caller,
        min_version,
        'git {0} or newer required to run this test (detected {1})'
    )


def uses_git_opts(caller):
    '''
    Skip test if git_opts is not supported
    '''
    min_version = '1.7.2'
    return __check_git_version(
        caller,
        min_version,
        'git_opts only supported in git {0} and newer (detected {1})'
    )


@ensure_min_git
class GitTest(ModuleCase, SaltReturnAssertsMixin):
    '''
    Validate the git state
    '''
    def setUp(self):
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
            with salt.utils.files.fopen(os.path.join(name, 'LICENSE'), 'a') as fp_:
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
                ('Repository {0} is up-to-date, but with uncommitted changes. '
                 'Set \'force_reset\' to True to purge uncommitted changes.'
                 .format(name))
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

    @uses_git_opts
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
            with salt.utils.files.fopen(os.path.join(admin_dir, 'LICENSE'), 'a') as fp_:
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
            with salt.utils.files.fopen(os.path.join(name, 'foo'), 'w'):
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

    @uses_git_opts
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

    @uses_git_opts
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

    @uses_git_opts
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
            with salt.utils.files.fopen(os.path.join(name, 'foo.txt'), 'w') as fp_:
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
            with salt.utils.files.fopen(os.path.join(name, 'foo.txt'), 'w') as fp_:
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

    def test_latest_depth(self):
        '''
        Test running git.latest state using the "depth" argument to limit the
        history. See #45394.
        '''
        name = os.path.join(TMP, 'salt_repo')
        try:
            ret = self.run_state(
                'git.latest',
                name='https://{0}/saltstack/salt-test-repo.git'.format(self.__domain),
                rev='HEAD',
                target=name,
                depth=1
            )
            # HEAD is not a branch, this should fail
            self.assertSaltFalseReturn(ret)
            self.assertIn(
                'must be set to the name of a branch',
                ret[next(iter(ret))]['comment']
            )

            ret = self.run_state(
                'git.latest',
                name='https://{0}/saltstack/salt-test-repo.git'.format(self.__domain),
                rev='non-default-branch',
                target=name,
                depth=1
            )
            self.assertSaltTrueReturn(ret)
            self.assertTrue(os.path.isdir(os.path.join(name, '.git')))
        finally:
            shutil.rmtree(name, ignore_errors=True)

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

            with salt.utils.files.fopen(fname, 'a'):
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


@ensure_min_git
@uses_git_opts
class LocalRepoGitTest(ModuleCase, SaltReturnAssertsMixin):
    '''
    Tests which do no require connectivity to github.com
    '''
    def setUp(self):
        self.repo = tempfile.mkdtemp(dir=TMP)
        self.admin = tempfile.mkdtemp(dir=TMP)
        self.target = tempfile.mkdtemp(dir=TMP)
        for dirname in (self.repo, self.admin, self.target):
            self.addCleanup(shutil.rmtree, dirname, ignore_errors=True)

        # Create bare repo
        self.run_function('git.init', [self.repo], bare=True)
        # Clone bare repo
        self.run_function('git.clone', [self.admin], url=self.repo)
        self._commit(self.admin, '', message='initial commit')
        self._push(self.admin)

    def _commit(self, repo_path, content, message):
        with salt.utils.files.fopen(os.path.join(repo_path, 'foo'), 'a') as fp_:
            fp_.write(content)
        self.run_function('git.add', [repo_path, '.'])
        self.run_function(
            'git.commit', [repo_path, message],
            git_opts='-c user.name="Foo Bar" -c user.email=foo@bar.com',
        )

    def _push(self, repo_path, remote='origin', ref='master'):
        self.run_function('git.push', [repo_path], remote=remote, ref=ref)

    def _test_latest_force_reset_setup(self):
        # Perform the initial clone
        ret = self.run_state(
            'git.latest',
            name=self.repo,
            target=self.target)
        self.assertSaltTrueReturn(ret)

        # Make and push changes to remote repo
        self._commit(self.admin,
                     content='Hello world!\n',
                     message='added a line')
        self._push(self.admin)

        # Make local changes to clone, but don't commit them
        with salt.utils.files.fopen(os.path.join(self.target, 'foo'), 'a') as fp_:
            fp_.write('Local changes!\n')

    def test_latest_force_reset_remote_changes(self):
        '''
        This tests that an otherwise fast-forward change with local chanegs
        will not reset local changes when force_reset='remote_changes'
        '''
        self._test_latest_force_reset_setup()

        # This should fail because of the local changes
        ret = self.run_state(
            'git.latest',
            name=self.repo,
            target=self.target)
        self.assertSaltFalseReturn(ret)
        ret = ret[next(iter(ret))]
        self.assertIn('there are uncommitted changes', ret['comment'])
        self.assertIn(
            'Set \'force_reset\' to True (or \'remote-changes\')',
            ret['comment']
        )
        self.assertEqual(ret['changes'], {})

        # Now run again with force_reset='remote_changes', the state should
        # succeed and discard the local changes
        ret = self.run_state(
            'git.latest',
            name=self.repo,
            target=self.target,
            force_reset='remote-changes')
        self.assertSaltTrueReturn(ret)
        ret = ret[next(iter(ret))]
        self.assertIn('Uncommitted changes were discarded', ret['comment'])
        self.assertIn('Repository was fast-forwarded', ret['comment'])
        self.assertNotIn('forced update', ret['changes'])
        self.assertIn('revision', ret['changes'])

        # Add new local changes, but don't commit them
        with salt.utils.files.fopen(os.path.join(self.target, 'foo'), 'a') as fp_:
            fp_.write('More local changes!\n')

        # Now run again with force_reset='remote_changes', the state should
        # succeed with an up-to-date message and mention that there are local
        # changes, telling the user how to discard them.
        ret = self.run_state(
            'git.latest',
            name=self.repo,
            target=self.target,
            force_reset='remote-changes')
        self.assertSaltTrueReturn(ret)
        ret = ret[next(iter(ret))]
        self.assertIn('up-to-date, but with uncommitted changes', ret['comment'])
        self.assertIn(
            'Set \'force_reset\' to True to purge uncommitted changes',
            ret['comment']
        )
        self.assertEqual(ret['changes'], {})

    def test_latest_force_reset_true_fast_forward(self):
        '''
        This tests that an otherwise fast-forward change with local chanegs
        does reset local changes when force_reset=True
        '''
        self._test_latest_force_reset_setup()

        # Test that local changes are discarded and that we fast-forward
        ret = self.run_state(
            'git.latest',
            name=self.repo,
            target=self.target,
            force_reset=True)
        self.assertSaltTrueReturn(ret)
        ret = ret[next(iter(ret))]
        self.assertIn('Uncommitted changes were discarded', ret['comment'])
        self.assertIn('Repository was fast-forwarded', ret['comment'])

        # Add new local changes
        with salt.utils.files.fopen(os.path.join(self.target, 'foo'), 'a') as fp_:
            fp_.write('More local changes!\n')

        # Running without setting force_reset should mention uncommitted changes
        ret = self.run_state(
            'git.latest',
            name=self.repo,
            target=self.target)
        self.assertSaltTrueReturn(ret)
        ret = ret[next(iter(ret))]
        self.assertIn('up-to-date, but with uncommitted changes', ret['comment'])
        self.assertIn(
            'Set \'force_reset\' to True to purge uncommitted changes',
            ret['comment']
        )
        self.assertEqual(ret['changes'], {})

        # Test that local changes are discarded
        ret = self.run_state(
            'git.latest',
            name=self.repo,
            target=self.target,
            force_reset=True)
        self.assertSaltTrueReturn(ret)
        ret = ret[next(iter(ret))]
        self.assertIn('Uncommitted changes were discarded', ret['comment'])
        self.assertIn('Repository was hard-reset', ret['comment'])
        self.assertIn('forced update', ret['changes'])

    def test_latest_force_reset_true_non_fast_forward(self):
        '''
        This tests that a non fast-forward change with divergent commits fails
        unless force_reset=True.
        '''
        self._test_latest_force_reset_setup()

        # Reset to remote HEAD
        ret = self.run_state(
            'git.latest',
            name=self.repo,
            target=self.target,
            force_reset=True)
        self.assertSaltTrueReturn(ret)
        ret = ret[next(iter(ret))]
        self.assertIn('Uncommitted changes were discarded', ret['comment'])
        self.assertIn('Repository was fast-forwarded', ret['comment'])

        # Make and push changes to remote repo
        self._commit(self.admin,
                     content='New line\n',
                     message='added another line')
        self._push(self.admin)

        # Make different changes to local file and commit locally
        self._commit(self.target,
                     content='Different new line\n',
                     message='added a different line')

        # This should fail since the local clone has diverged and cannot
        # fast-forward to the remote rev
        ret = self.run_state(
            'git.latest',
            name=self.repo,
            target=self.target)
        self.assertSaltFalseReturn(ret)
        ret = ret[next(iter(ret))]
        self.assertIn('this is not a fast-forward merge', ret['comment'])
        self.assertIn(
            'Set \'force_reset\' to True to force this update',
            ret['comment']
        )
        self.assertEqual(ret['changes'], {})

        # Repeat the state with force_reset=True and confirm that the hard
        # reset was performed
        ret = self.run_state(
            'git.latest',
            name=self.repo,
            target=self.target,
            force_reset=True)
        self.assertSaltTrueReturn(ret)
        ret = ret[next(iter(ret))]
        self.assertIn('Repository was hard-reset', ret['comment'])
        self.assertIn('forced update', ret['changes'])
        self.assertIn('revision', ret['changes'])

    def test_renamed_default_branch(self):
        '''
        Test the case where the remote branch has been removed
        https://github.com/saltstack/salt/issues/36242
        '''
        # Rename remote 'master' branch to 'develop'
        os.rename(
            os.path.join(self.repo, 'refs', 'heads', 'master'),
            os.path.join(self.repo, 'refs', 'heads', 'develop')
        )

        # Run git.latest state. This should successfully clone and fail with a
        # specific error in the comment field.
        ret = self.run_state(
            'git.latest',
            name=self.repo,
            target=self.target,
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
            .format(self.repo, self.target)
        )
        self.assertEqual(
            ret[next(iter(ret))]['changes'],
            {'new': '{0} => {1}'.format(self.repo, self.target)}
        )

        # Run git.latest state again. This should fail again, with a different
        # error in the comment field, and should not change anything.
        ret = self.run_state(
            'git.latest',
            name=self.repo,
            target=self.target,
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
            name=self.repo,
            target=self.target,
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
