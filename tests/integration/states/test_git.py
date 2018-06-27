# -*- coding: utf-8 -*-
'''
Tests for the Git state
'''

# Import python libs
from __future__ import absolute_import, print_function, unicode_literals
import functools
import inspect
import os
import socket
import string

# Import Salt Testing libs
from tests.support.case import ModuleCase
from tests.support.helpers import with_tempdir
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
        domain = 'github.com'
        self.test_repo = 'https://{0}/saltstack/salt-test-repo.git'.format(domain)
        try:
            if hasattr(socket, 'setdefaulttimeout'):
                # 10 second dns timeout
                socket.setdefaulttimeout(10)
            socket.gethostbyname(domain)
        except socket.error:
            msg = 'error resolving {0}, possible network issue?'
            self.skipTest(msg.format(domain))

    def tearDown(self):
        # Reset the dns timeout after the test is over
        socket.setdefaulttimeout(None)

    @with_tempdir(create=False)
    def test_latest(self, target):
        '''
        git.latest
        '''
        ret = self.run_state(
            'git.latest',
            name=self.test_repo,
            target=target
        )
        self.assertSaltTrueReturn(ret)
        self.assertTrue(os.path.isdir(os.path.join(target, '.git')))

    @with_tempdir(create=False)
    def test_latest_with_rev_and_submodules(self, target):
        '''
        git.latest
        '''
        ret = self.run_state(
            'git.latest',
            name=self.test_repo,
            rev='develop',
            target=target,
            submodules=True
        )
        self.assertSaltTrueReturn(ret)
        self.assertTrue(os.path.isdir(os.path.join(target, '.git')))

    @with_tempdir(create=False)
    def test_latest_failure(self, target):
        '''
        git.latest
        '''
        ret = self.run_state(
            'git.latest',
            name='https://youSpelledGitHubWrong.com/saltstack/salt-test-repo.git',
            rev='develop',
            target=target,
            submodules=True
        )
        self.assertSaltFalseReturn(ret)
        self.assertFalse(os.path.isdir(os.path.join(target, '.git')))

    @with_tempdir()
    def test_latest_empty_dir(self, target):
        '''
        git.latest
        '''
        ret = self.run_state(
            'git.latest',
            name=self.test_repo,
            rev='develop',
            target=target,
            submodules=True
        )
        self.assertSaltTrueReturn(ret)
        self.assertTrue(os.path.isdir(os.path.join(target, '.git')))

    @with_tempdir(create=False)
    def test_latest_unless_no_cwd_issue_6800(self, target):
        '''
        cwd=target was being passed to _run_check which blew up if
        target dir did not already exist.
        '''
        ret = self.run_state(
            'git.latest',
            name=self.test_repo,
            rev='develop',
            target=target,
            unless='test -e {0}'.format(target),
            submodules=True
        )
        self.assertSaltTrueReturn(ret)
        self.assertTrue(os.path.isdir(os.path.join(target, '.git')))

    @with_tempdir(create=False)
    def test_numeric_rev(self, target):
        '''
        git.latest with numeric revision
        '''
        ret = self.run_state(
            'git.latest',
            name=self.test_repo,
            rev=0.11,
            target=target,
            submodules=True,
            timeout=120
        )
        self.assertSaltTrueReturn(ret)
        self.assertTrue(os.path.isdir(os.path.join(target, '.git')))

    @with_tempdir(create=False)
    def test_latest_with_local_changes(self, target):
        '''
        Ensure that we fail the state when there are local changes and succeed
        when force_reset is True.
        '''
        # Clone repo
        ret = self.run_state(
            'git.latest',
            name=self.test_repo,
            target=target
        )
        self.assertSaltTrueReturn(ret)
        self.assertTrue(os.path.isdir(os.path.join(target, '.git')))

        # Make change to LICENSE file.
        with salt.utils.files.fopen(os.path.join(target, 'LICENSE'), 'a') as fp_:
            fp_.write('Lorem ipsum dolor blah blah blah....\n')

        # Make sure that we now have uncommitted changes
        self.assertTrue(self.run_function('git.diff', [target, 'HEAD']))

        # Re-run state with force_reset=False
        ret = self.run_state(
            'git.latest',
            name=self.test_repo,
            target=target,
            force_reset=False
        )
        self.assertSaltTrueReturn(ret)
        self.assertEqual(
            ret[next(iter(ret))]['comment'],
            ('Repository {0} is up-to-date, but with local changes. Set '
             '\'force_reset\' to True to purge local changes.'.format(target))
        )

        # Now run the state with force_reset=True
        ret = self.run_state(
            'git.latest',
            name=self.test_repo,
            target=target,
            force_reset=True
        )
        self.assertSaltTrueReturn(ret)

        # Make sure that we no longer have uncommitted changes
        self.assertFalse(self.run_function('git.diff', [target, 'HEAD']))

    @uses_git_opts
    @with_tempdir(create=False)
    @with_tempdir(create=False)
    @with_tempdir(create=False)
    def test_latest_fast_forward(self, mirror_dir, admin_dir, clone_dir):
        '''
        Test running git.latest state a second time after changes have been
        made to the remote repo.
        '''
        def _head(cwd):
            return self.run_function('git.rev_parse', [cwd, 'HEAD'])

        mirror_url = 'file://' + mirror_dir

        # Mirror the repo
        self.run_function(
            'git.clone', [mirror_dir], url=self.test_repo, opts='--mirror')

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

    @with_tempdir(create=False)
    def _changed_local_branch_helper(self, target, rev, hint):
        '''
        We're testing two almost identical cases, the only thing that differs
        is the rev used for the git.latest state.
        '''
        # Clone repo
        ret = self.run_state(
            'git.latest',
            name=self.test_repo,
            rev=rev,
            target=target
        )
        self.assertSaltTrueReturn(ret)

        # Check out a new branch in the clone and make a commit, to ensure
        # that when we re-run the state, it is not a fast-forward change
        self.run_function('git.checkout', [target, 'new_branch'], opts='-b')
        with salt.utils.files.fopen(os.path.join(target, 'foo'), 'w'):
            pass
        self.run_function('git.add', [target, '.'])
        self.run_function(
            'git.commit', [target, 'add file'],
            git_opts='-c user.name="Foo Bar" -c user.email=foo@bar.com',
        )

        # Re-run the state, this should fail with a specific hint in the
        # comment field.
        ret = self.run_state(
            'git.latest',
            name=self.test_repo,
            rev=rev,
            target=target
        )
        self.assertSaltFalseReturn(ret)

        comment = ret[next(iter(ret))]['comment']
        self.assertTrue(hint in comment)

    @uses_git_opts
    def test_latest_changed_local_branch_rev_head(self):
        '''
        Test for presence of hint in failure message when the local branch has
        been changed and a the rev is set to HEAD

        This test will fail if the default branch for the salt-test-repo is
        ever changed.
        '''
        self._changed_local_branch_helper(  # pylint: disable=no-value-for-parameter
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
        self._changed_local_branch_helper(  # pylint: disable=no-value-for-parameter
            'develop',
            'The desired rev (develop) differs from the name of the local '
            'branch (new_branch)'
        )

    @uses_git_opts
    @with_tempdir(create=False)
    @with_tempdir()
    def test_latest_updated_remote_rev(self, name, target):
        '''
        Ensure that we don't exit early when checking for a fast-forward
        '''
        # Initialize a new git repository
        self.run_function('git.init', [name])

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

    @with_tempdir(create=False)
    def test_latest_depth(self, target):
        '''
        Test running git.latest state using the "depth" argument to limit the
        history. See #45394.
        '''
        ret = self.run_state(
            'git.latest',
            name=self.test_repo,
            rev='HEAD',
            target=target,
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
            name=self.test_repo,
            rev='non-default-branch',
            target=target,
            depth=1
        )
        self.assertSaltTrueReturn(ret)
        self.assertTrue(os.path.isdir(os.path.join(target, '.git')))

    @with_tempdir(create=False)
    def test_cloned(self, target):
        '''
        Test git.cloned state
        '''
        # Test mode
        ret = self.run_state(
            'git.cloned',
            name=self.test_repo,
            target=target,
            test=True)
        ret = ret[next(iter(ret))]
        assert ret['result'] is None
        assert ret['changes'] == {
            'new': '{0} => {1}'.format(self.test_repo, target)
        }
        assert ret['comment'] == '{0} would be cloned to {1}'.format(
            self.test_repo,
            target
        )

        # Now actually run the state
        ret = self.run_state(
            'git.cloned',
            name=self.test_repo,
            target=target)
        ret = ret[next(iter(ret))]
        assert ret['result'] is True
        assert ret['changes'] == {
            'new': '{0} => {1}'.format(self.test_repo, target)
        }
        assert ret['comment'] == '{0} cloned to {1}'.format(self.test_repo, target)

        # Run the state again to test idempotence
        ret = self.run_state(
            'git.cloned',
            name=self.test_repo,
            target=target)
        ret = ret[next(iter(ret))]
        assert ret['result'] is True
        assert not ret['changes']
        assert ret['comment'] == 'Repository already exists at {0}'.format(target)

        # Run the state again to test idempotence (test mode)
        ret = self.run_state(
            'git.cloned',
            name=self.test_repo,
            target=target,
            test=True)
        ret = ret[next(iter(ret))]
        assert not ret['changes']
        assert ret['result'] is True
        assert ret['comment'] == 'Repository already exists at {0}'.format(target)

    @with_tempdir(create=False)
    def test_cloned_with_branch(self, target):
        '''
        Test git.cloned state with branch provided
        '''
        old_branch = 'master'
        new_branch = 'develop'
        bad_branch = 'thisbranchdoesnotexist'

        # Test mode
        ret = self.run_state(
            'git.cloned',
            name=self.test_repo,
            target=target,
            branch=old_branch,
            test=True)
        ret = ret[next(iter(ret))]
        assert ret['result'] is None
        assert ret['changes'] == {
            'new': '{0} => {1}'.format(self.test_repo, target)
        }
        assert ret['comment'] == (
            '{0} would be cloned to {1} with branch \'{2}\''.format(
                self.test_repo,
                target,
                old_branch
            )
        )

        # Now actually run the state
        ret = self.run_state(
            'git.cloned',
            name=self.test_repo,
            target=target,
            branch=old_branch)
        ret = ret[next(iter(ret))]
        assert ret['result'] is True
        assert ret['changes'] == {
            'new': '{0} => {1}'.format(self.test_repo, target)
        }
        assert ret['comment'] == (
            '{0} cloned to {1} with branch \'{2}\''.format(
                self.test_repo,
                target,
                old_branch
            )
        )

        # Run the state again to test idempotence
        ret = self.run_state(
            'git.cloned',
            name=self.test_repo,
            target=target,
            branch=old_branch)
        ret = ret[next(iter(ret))]
        assert ret['result'] is True
        assert not ret['changes']
        assert ret['comment'] == (
            'Repository already exists at {0} '
            'and is checked out to branch \'{1}\''.format(target, old_branch)
        )

        # Run the state again to test idempotence (test mode)
        ret = self.run_state(
            'git.cloned',
            name=self.test_repo,
            target=target,
            test=True,
            branch=old_branch)
        ret = ret[next(iter(ret))]
        assert ret['result'] is True
        assert not ret['changes']
        assert ret['comment'] == (
            'Repository already exists at {0} '
            'and is checked out to branch \'{1}\''.format(target, old_branch)
        )

        # Change branch (test mode)
        ret = self.run_state(
            'git.cloned',
            name=self.test_repo,
            target=target,
            branch=new_branch,
            test=True)
        ret = ret[next(iter(ret))]
        assert ret['result'] is None
        assert ret['changes'] == {
            'branch': {'old': old_branch, 'new': new_branch}
        }
        assert ret['comment'] == 'Branch would be changed to \'{0}\''.format(
            new_branch
        )

        # Now really change the branch
        ret = self.run_state(
            'git.cloned',
            name=self.test_repo,
            target=target,
            branch=new_branch)
        ret = ret[next(iter(ret))]
        assert ret['result'] is True
        assert ret['changes'] == {
            'branch': {'old': old_branch, 'new': new_branch}
        }
        assert ret['comment'] == 'Branch changed to \'{0}\''.format(
            new_branch
        )

        # Change back to original branch. This tests that we don't attempt to
        # checkout a new branch (i.e. git checkout -b) for a branch that exists
        # locally, as that would fail.
        ret = self.run_state(
            'git.cloned',
            name=self.test_repo,
            target=target,
            branch=old_branch)
        ret = ret[next(iter(ret))]
        assert ret['result'] is True
        assert ret['changes'] == {
            'branch': {'old': new_branch, 'new': old_branch}
        }
        assert ret['comment'] == 'Branch changed to \'{0}\''.format(
            old_branch
        )

        # Test switching to a nonexistant branch. This should fail.
        ret = self.run_state(
            'git.cloned',
            name=self.test_repo,
            target=target,
            branch=bad_branch)
        ret = ret[next(iter(ret))]
        assert ret['result'] is False
        assert not ret['changes']
        assert ret['comment'].startswith(
            'Failed to change branch to \'{0}\':'.format(bad_branch)
        )

    @with_tempdir(create=False)
    def test_cloned_with_nonexistant_branch(self, target):
        '''
        Test git.cloned state with a nonexistant branch provided
        '''
        branch = 'thisbranchdoesnotexist'

        # Test mode
        ret = self.run_state(
            'git.cloned',
            name=self.test_repo,
            target=target,
            branch=branch,
            test=True)
        ret = ret[next(iter(ret))]
        assert ret['result'] is None
        assert ret['changes']
        assert ret['comment'] == (
            '{0} would be cloned to {1} with branch \'{2}\''.format(
                self.test_repo,
                target,
                branch
            )
        )

        # Now actually run the state
        ret = self.run_state(
            'git.cloned',
            name=self.test_repo,
            target=target,
            branch=branch)
        ret = ret[next(iter(ret))]
        assert ret['result'] is False
        assert not ret['changes']
        assert ret['comment'].startswith('Clone failed:')
        assert 'not found in upstream origin' in ret['comment']

    @with_tempdir(create=False)
    def test_present(self, name):
        '''
        git.present
        '''
        ret = self.run_state(
            'git.present',
            name=name,
            bare=True
        )
        self.assertSaltTrueReturn(ret)
        self.assertTrue(os.path.isfile(os.path.join(name, 'HEAD')))

    @with_tempdir()
    def test_present_failure(self, name):
        '''
        git.present
        '''
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

    @with_tempdir()
    def test_present_empty_dir(self, name):
        '''
        git.present
        '''
        ret = self.run_state(
            'git.present',
            name=name,
            bare=True
        )
        self.assertSaltTrueReturn(ret)
        self.assertTrue(os.path.isfile(os.path.join(name, 'HEAD')))

    @with_tempdir()
    def test_config_set_value_with_space_character(self, name):
        '''
        git.config
        '''
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
    @with_tempdir()
    @with_tempdir()
    @with_tempdir()
    def test_renamed_default_branch(self, repo, admin, target):
        '''
        Test the case where the remote branch has been removed
        https://github.com/saltstack/salt/issues/36242
        '''
        # Create bare repo
        self.run_function('git.init', [repo], bare=True)
        # Clone bare repo
        self.run_function('git.clone', [admin], url=repo)
        # Create, add, commit, and push file
        with salt.utils.files.fopen(os.path.join(admin, 'foo'), 'w'):
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

        # Run git.latest state. This should successfully clone and fail with a
        # specific error in the comment field.
        ret = self.run_state(
            'git.latest',
            name=repo,
            target=target,
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
            .format(repo, target)
        )
        self.assertEqual(
            ret[next(iter(ret))]['changes'],
            {'new': '{0} => {1}'.format(repo, target)}
        )

        # Run git.latest state again. This should fail again, with a different
        # error in the comment field, and should not change anything.
        ret = self.run_state(
            'git.latest',
            name=repo,
            target=target,
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
            target=target,
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
