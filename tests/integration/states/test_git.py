"""
Tests for the Git state
"""

import functools
import inspect
import logging
import os
import shutil
import socket
import string
import tempfile
import urllib.parse

import pytest
import salt.utils.files
import salt.utils.path
from salt.utils.versions import LooseVersion as _LooseVersion
from tests.support.case import ModuleCase
from tests.support.helpers import TstSuiteLoggingHandler, with_tempdir
from tests.support.mixins import SaltReturnAssertsMixin
from tests.support.runtests import RUNTIME_VARS

TEST_REPO = "https://github.com/saltstack/salt-test-repo.git"


def __check_git_version(caller, min_version, skip_msg):
    """
    Common logic for version check
    """
    if inspect.isclass(caller):
        actual_setup = getattr(caller, "setUp", None)

        def setUp(self, *args, **kwargs):
            if not salt.utils.path.which("git"):
                self.skipTest("git is not installed")
            git_version = self.run_function("git.version")
            if _LooseVersion(git_version) < _LooseVersion(min_version):
                self.skipTest(skip_msg.format(min_version, git_version))
            if actual_setup is not None:
                actual_setup(self, *args, **kwargs)

        caller.setUp = setUp
        return caller

    @functools.wraps(caller)
    def wrapper(self, *args, **kwargs):
        if not salt.utils.path.which("git"):
            self.skipTest("git is not installed")
        git_version = self.run_function("git.version")
        if _LooseVersion(git_version) < _LooseVersion(min_version):
            self.skipTest(skip_msg.format(min_version, git_version))
        return caller(self, *args, **kwargs)

    return wrapper


def ensure_min_git(caller=None, min_version="1.6.5"):
    """
    Skip test if minimum supported git version is not installed
    """
    if caller is None:
        return functools.partial(ensure_min_git, min_version=min_version)

    return __check_git_version(
        caller, min_version, "git {0} or newer required to run this test (detected {1})"
    )


def uses_git_opts(caller):
    """
    Skip test if git_opts is not supported

    IMPORTANT! This decorator should be at the bottom of any decorators added
    to a given function.
    """
    min_version = "1.7.2"
    return __check_git_version(
        caller,
        min_version,
        "git_opts only supported in git {0} and newer (detected {1})",
    )


class WithGitMirror:
    def __init__(self, repo_url, **kwargs):
        self.repo_url = repo_url
        if "dir" not in kwargs:
            kwargs["dir"] = RUNTIME_VARS.TMP
        self.kwargs = kwargs

    def __call__(self, func):
        self.func = func
        return functools.wraps(func)(
            # pylint: disable=unnecessary-lambda
            lambda testcase, *args, **kwargs: self.wrap(testcase, *args, **kwargs)
            # pylint: enable=unnecessary-lambda
        )

    def wrap(self, testcase, *args, **kwargs):
        # Get temp dir paths
        mirror_dir = tempfile.mkdtemp(**self.kwargs)
        admin_dir = tempfile.mkdtemp(**self.kwargs)
        clone_dir = tempfile.mkdtemp(**self.kwargs)
        # Clean up the directories, we want git to actually create them
        os.rmdir(mirror_dir)
        os.rmdir(admin_dir)
        os.rmdir(clone_dir)
        # Create a URL to clone
        mirror_url = "file://" + mirror_dir
        # Mirror the repo
        testcase.run_function("git.clone", [mirror_dir], url=TEST_REPO, opts="--mirror")
        # Make sure the directory for the mirror now exists
        assert os.path.exists(mirror_dir)
        # Clone to the admin dir
        ret = testcase.run_state("git.latest", name=mirror_url, target=admin_dir)
        ret = ret[next(iter(ret))]
        assert os.path.exists(admin_dir)

        try:
            # Run the actual function with three arguments added:
            #   1. URL for the test to use to clone
            #   2. Cloned admin dir for making/pushing changes to the mirror
            #   3. Yet-nonexistent clone_dir for the test function to use as a
            #      destination for cloning.
            return self.func(
                testcase, mirror_url, admin_dir, clone_dir, *args, **kwargs
            )
        finally:
            shutil.rmtree(mirror_dir, ignore_errors=True)
            shutil.rmtree(admin_dir, ignore_errors=True)
            shutil.rmtree(clone_dir, ignore_errors=True)


with_git_mirror = WithGitMirror


@ensure_min_git
class GitTest(ModuleCase, SaltReturnAssertsMixin):
    """
    Validate the git state
    """

    def setUp(self):
        domain = urllib.parse.urlparse(TEST_REPO).netloc
        try:
            if hasattr(socket, "setdefaulttimeout"):
                # 10 second dns timeout
                socket.setdefaulttimeout(10)
            socket.gethostbyname(domain)
        except OSError:
            msg = "error resolving {0}, possible network issue?"
            self.skipTest(msg.format(domain))

    def tearDown(self):
        # Reset the dns timeout after the test is over
        socket.setdefaulttimeout(None)

    def _head(self, cwd):
        return self.run_function("git.rev_parse", [cwd, "HEAD"])

    @with_tempdir(create=False)
    @pytest.mark.slow_test
    def test_latest(self, target):
        """
        git.latest
        """
        ret = self.run_state("git.latest", name=TEST_REPO, target=target)
        self.assertSaltTrueReturn(ret)
        self.assertTrue(os.path.isdir(os.path.join(target, ".git")))

    @with_tempdir(create=False)
    @pytest.mark.slow_test
    def test_latest_config_get_regexp_retcode(self, target):
        """
        git.latest
        """

        log_format = "[%(levelname)-8s] %(jid)s %(message)s"
        self.handler = TstSuiteLoggingHandler(format=log_format, level=logging.DEBUG)
        ret_code_err = "failed with return code: 1"
        with self.handler:
            ret = self.run_state("git.latest", name=TEST_REPO, target=target)
            self.assertSaltTrueReturn(ret)
            self.assertTrue(os.path.isdir(os.path.join(target, ".git")))
            assert any(ret_code_err in s for s in self.handler.messages) is False, False

    @with_tempdir(create=False)
    @pytest.mark.slow_test
    def test_latest_with_rev_and_submodules(self, target):
        """
        git.latest
        """
        ret = self.run_state(
            "git.latest", name=TEST_REPO, rev="develop", target=target, submodules=True
        )
        self.assertSaltTrueReturn(ret)
        self.assertTrue(os.path.isdir(os.path.join(target, ".git")))

    @with_tempdir(create=False)
    @pytest.mark.slow_test
    def test_latest_failure(self, target):
        """
        git.latest
        """
        ret = self.run_state(
            "git.latest",
            name="https://youSpelledGitHubWrong.com/saltstack/salt-test-repo.git",
            rev="develop",
            target=target,
            submodules=True,
        )
        self.assertSaltFalseReturn(ret)
        self.assertFalse(os.path.isdir(os.path.join(target, ".git")))

    @with_tempdir()
    @pytest.mark.slow_test
    def test_latest_empty_dir(self, target):
        """
        git.latest
        """
        ret = self.run_state(
            "git.latest", name=TEST_REPO, rev="develop", target=target, submodules=True
        )
        self.assertSaltTrueReturn(ret)
        self.assertTrue(os.path.isdir(os.path.join(target, ".git")))

    @with_tempdir(create=False)
    @pytest.mark.slow_test
    def test_latest_unless_no_cwd_issue_6800(self, target):
        """
        cwd=target was being passed to _run_check which blew up if
        target dir did not already exist.
        """
        ret = self.run_state(
            "git.latest",
            name=TEST_REPO,
            rev="develop",
            target=target,
            unless="test -e {}".format(target),
            submodules=True,
        )
        self.assertSaltTrueReturn(ret)
        self.assertTrue(os.path.isdir(os.path.join(target, ".git")))

    @with_tempdir(create=False)
    @pytest.mark.slow_test
    def test_numeric_rev(self, target):
        """
        git.latest with numeric revision
        """
        ret = self.run_state(
            "git.latest",
            name=TEST_REPO,
            rev=0.11,
            target=target,
            submodules=True,
            timeout=120,
        )
        self.assertSaltTrueReturn(ret)
        self.assertTrue(os.path.isdir(os.path.join(target, ".git")))

    @with_tempdir(create=False)
    @pytest.mark.slow_test
    def test_latest_with_local_changes(self, target):
        """
        Ensure that we fail the state when there are local changes and succeed
        when force_reset is True.
        """
        # Clone repo
        ret = self.run_state("git.latest", name=TEST_REPO, target=target)
        self.assertSaltTrueReturn(ret)
        self.assertTrue(os.path.isdir(os.path.join(target, ".git")))

        # Make change to LICENSE file.
        with salt.utils.files.fopen(os.path.join(target, "LICENSE"), "a") as fp_:
            fp_.write("Lorem ipsum dolor blah blah blah....\n")

        # Make sure that we now have uncommitted changes
        self.assertTrue(self.run_function("git.diff", [target, "HEAD"]))

        # Re-run state with force_reset=False
        ret = self.run_state(
            "git.latest", name=TEST_REPO, target=target, force_reset=False
        )
        self.assertSaltTrueReturn(ret)
        self.assertEqual(
            ret[next(iter(ret))]["comment"],
            "Repository {} is up-to-date, but with uncommitted changes. "
            "Set 'force_reset' to True to purge uncommitted changes.".format(target),
        )

        # Now run the state with force_reset=True
        ret = self.run_state(
            "git.latest", name=TEST_REPO, target=target, force_reset=True
        )
        self.assertSaltTrueReturn(ret)

        # Make sure that we no longer have uncommitted changes
        self.assertFalse(self.run_function("git.diff", [target, "HEAD"]))

    @with_git_mirror(TEST_REPO)
    @uses_git_opts
    @pytest.mark.slow_test
    def test_latest_fast_forward(self, mirror_url, admin_dir, clone_dir):
        """
        Test running git.latest state a second time after changes have been
        made to the remote repo.
        """
        # Clone the repo
        ret = self.run_state("git.latest", name=mirror_url, target=clone_dir)
        ret = ret[next(iter(ret))]
        assert ret["result"]

        # Make a change to the repo by editing the file in the admin copy
        # of the repo and committing.
        head_pre = self._head(admin_dir)
        with salt.utils.files.fopen(os.path.join(admin_dir, "LICENSE"), "a") as fp_:
            fp_.write("Hello world!")
        self.run_function(
            "git.commit",
            [admin_dir, "added a line"],
            git_opts='-c user.name="Foo Bar" -c user.email=foo@bar.com',
            opts="-a",
        )
        # Make sure HEAD is pointing to a new SHA so we know we properly
        # committed our change.
        head_post = self._head(admin_dir)
        assert head_pre != head_post

        # Push the change to the mirror
        # NOTE: the test will fail if the salt-test-repo's default branch
        # is changed.
        self.run_function("git.push", [admin_dir, "origin", "develop"])

        # Re-run the git.latest state on the clone_dir
        ret = self.run_state("git.latest", name=mirror_url, target=clone_dir)
        ret = ret[next(iter(ret))]
        assert ret["result"]

        # Make sure that the clone_dir now has the correct SHA
        assert head_post == self._head(clone_dir)

    @with_tempdir(create=False)
    def _changed_local_branch_helper(self, target, rev, hint):
        """
        We're testing two almost identical cases, the only thing that differs
        is the rev used for the git.latest state.
        """
        # Clone repo
        ret = self.run_state("git.latest", name=TEST_REPO, rev=rev, target=target)
        self.assertSaltTrueReturn(ret)

        # Check out a new branch in the clone and make a commit, to ensure
        # that when we re-run the state, it is not a fast-forward change
        self.run_function("git.checkout", [target, "new_branch"], opts="-b")
        with salt.utils.files.fopen(os.path.join(target, "foo"), "w"):
            pass
        self.run_function("git.add", [target, "."])
        self.run_function(
            "git.commit",
            [target, "add file"],
            git_opts='-c user.name="Foo Bar" -c user.email=foo@bar.com',
        )

        # Re-run the state, this should fail with a specific hint in the
        # comment field.
        ret = self.run_state("git.latest", name=TEST_REPO, rev=rev, target=target)
        self.assertSaltFalseReturn(ret)

        comment = ret[next(iter(ret))]["comment"]
        self.assertTrue(hint in comment)

    @uses_git_opts
    @pytest.mark.slow_test
    def test_latest_changed_local_branch_rev_head(self):
        """
        Test for presence of hint in failure message when the local branch has
        been changed and a the rev is set to HEAD

        This test will fail if the default branch for the salt-test-repo is
        ever changed.
        """
        self._changed_local_branch_helper(  # pylint: disable=no-value-for-parameter
            "HEAD",
            "The default remote branch (develop) differs from the local "
            "branch (new_branch)",
        )

    @uses_git_opts
    @pytest.mark.slow_test
    def test_latest_changed_local_branch_rev_develop(self):
        """
        Test for presence of hint in failure message when the local branch has
        been changed and a non-HEAD rev is specified
        """
        self._changed_local_branch_helper(  # pylint: disable=no-value-for-parameter
            "develop",
            "The desired rev (develop) differs from the name of the local "
            "branch (new_branch)",
        )

    @uses_git_opts
    @with_tempdir(create=False)
    @with_tempdir()
    @pytest.mark.slow_test
    def test_latest_updated_remote_rev(self, name, target):
        """
        Ensure that we don't exit early when checking for a fast-forward
        """
        # Initialize a new git repository
        self.run_function("git.init", [name])

        # Add and commit a file
        with salt.utils.files.fopen(os.path.join(name, "foo.txt"), "w") as fp_:
            fp_.write("Hello world\n")
        self.run_function("git.add", [name, "."])
        self.run_function(
            "git.commit",
            [name, "initial commit"],
            git_opts='-c user.name="Foo Bar" -c user.email=foo@bar.com',
        )

        # Run the state to clone the repo we just created
        ret = self.run_state(
            "git.latest",
            name=name,
            target=target,
        )
        self.assertSaltTrueReturn(ret)

        # Add another commit
        with salt.utils.files.fopen(os.path.join(name, "foo.txt"), "w") as fp_:
            fp_.write("Added a line\n")
        self.run_function(
            "git.commit",
            [name, "added a line"],
            git_opts='-c user.name="Foo Bar" -c user.email=foo@bar.com',
            opts="-a",
        )

        # Run the state again. It should pass, if it doesn't then there was
        # a problem checking whether or not the change is a fast-forward.
        ret = self.run_state(
            "git.latest",
            name=name,
            target=target,
        )
        self.assertSaltTrueReturn(ret)

    @with_tempdir(create=False)
    @pytest.mark.slow_test
    def test_latest_depth(self, target):
        """
        Test running git.latest state using the "depth" argument to limit the
        history. See #45394.
        """
        ret = self.run_state(
            "git.latest", name=TEST_REPO, rev="HEAD", target=target, depth=1
        )
        # HEAD is not a branch, this should fail
        self.assertSaltFalseReturn(ret)
        self.assertIn(
            "must be set to the name of a branch", ret[next(iter(ret))]["comment"]
        )

        ret = self.run_state(
            "git.latest",
            name=TEST_REPO,
            rev="non-default-branch",
            target=target,
            depth=1,
        )
        self.assertSaltTrueReturn(ret)
        self.assertTrue(os.path.isdir(os.path.join(target, ".git")))

    @with_git_mirror(TEST_REPO)
    @uses_git_opts
    @pytest.mark.slow_test
    def test_latest_sync_tags(self, mirror_url, admin_dir, clone_dir):
        """
        Test that a removed tag is properly reported as such and removed in the
        local clone, and that new tags are reported as new.
        """
        tag1 = "mytag1"
        tag2 = "mytag2"

        # Add and push a tag
        self.run_function("git.tag", [admin_dir, tag1])
        self.run_function("git.push", [admin_dir, "origin", tag1])

        # Clone the repo
        ret = self.run_state("git.latest", name=mirror_url, target=clone_dir)
        ret = ret[next(iter(ret))]
        assert ret["result"]

        # Now remove the tag
        self.run_function("git.push", [admin_dir, "origin", ":{}".format(tag1)])
        # Add and push another tag
        self.run_function("git.tag", [admin_dir, tag2])
        self.run_function("git.push", [admin_dir, "origin", tag2])

        # Re-run the state with sync_tags=False. This should NOT delete the tag
        # from the local clone, but should report that a tag has been added.
        ret = self.run_state(
            "git.latest", name=mirror_url, target=clone_dir, sync_tags=False
        )
        ret = ret[next(iter(ret))]
        assert ret["result"]
        # Make ABSOLUTELY SURE both tags are present, since we shouldn't have
        # removed tag1.
        all_tags = self.run_function("git.list_tags", [clone_dir])
        assert tag1 in all_tags
        assert tag2 in all_tags
        # Make sure the reported changes are correct
        expected_changes = {"new_tags": [tag2]}
        assert ret["changes"] == expected_changes, ret["changes"]

        # Re-run the state with sync_tags=True. This should remove the local
        # tag, since it doesn't exist in the remote repository.
        ret = self.run_state(
            "git.latest", name=mirror_url, target=clone_dir, sync_tags=True
        )
        ret = ret[next(iter(ret))]
        assert ret["result"]
        # Make ABSOLUTELY SURE the expected tags are present/gone
        all_tags = self.run_function("git.list_tags", [clone_dir])
        assert tag1 not in all_tags
        assert tag2 in all_tags
        # Make sure the reported changes are correct
        expected_changes = {"deleted_tags": [tag1]}
        assert ret["changes"] == expected_changes, ret["changes"]

    @with_tempdir(create=False)
    @pytest.mark.slow_test
    def test_cloned(self, target):
        """
        Test git.cloned state
        """
        # Test mode
        ret = self.run_state("git.cloned", name=TEST_REPO, target=target, test=True)
        ret = ret[next(iter(ret))]
        assert ret["result"] is None
        assert ret["changes"] == {"new": "{} => {}".format(TEST_REPO, target)}
        assert ret["comment"] == "{} would be cloned to {}".format(TEST_REPO, target)

        # Now actually run the state
        ret = self.run_state("git.cloned", name=TEST_REPO, target=target)
        ret = ret[next(iter(ret))]
        assert ret["result"] is True
        assert ret["changes"] == {"new": "{} => {}".format(TEST_REPO, target)}
        assert ret["comment"] == "{} cloned to {}".format(TEST_REPO, target)

        # Run the state again to test idempotence
        ret = self.run_state("git.cloned", name=TEST_REPO, target=target)
        ret = ret[next(iter(ret))]
        assert ret["result"] is True
        assert not ret["changes"]
        assert ret["comment"] == "Repository already exists at {}".format(target)

        # Run the state again to test idempotence (test mode)
        ret = self.run_state("git.cloned", name=TEST_REPO, target=target, test=True)
        ret = ret[next(iter(ret))]
        assert not ret["changes"]
        assert ret["result"] is True
        assert ret["comment"] == "Repository already exists at {}".format(target)

    @with_tempdir(create=False)
    @pytest.mark.slow_test
    def test_cloned_with_branch(self, target):
        """
        Test git.cloned state with branch provided
        """
        old_branch = "master"
        new_branch = "develop"
        bad_branch = "thisbranchdoesnotexist"

        # Test mode
        ret = self.run_state(
            "git.cloned", name=TEST_REPO, target=target, branch=old_branch, test=True
        )
        ret = ret[next(iter(ret))]
        assert ret["result"] is None
        assert ret["changes"] == {"new": "{} => {}".format(TEST_REPO, target)}
        assert ret["comment"] == "{} would be cloned to {} with branch '{}'".format(
            TEST_REPO, target, old_branch
        )

        # Now actually run the state
        ret = self.run_state(
            "git.cloned", name=TEST_REPO, target=target, branch=old_branch
        )
        ret = ret[next(iter(ret))]
        assert ret["result"] is True
        assert ret["changes"] == {"new": "{} => {}".format(TEST_REPO, target)}
        assert ret["comment"] == "{} cloned to {} with branch '{}'".format(
            TEST_REPO, target, old_branch
        )

        # Run the state again to test idempotence
        ret = self.run_state(
            "git.cloned", name=TEST_REPO, target=target, branch=old_branch
        )
        ret = ret[next(iter(ret))]
        assert ret["result"] is True
        assert not ret["changes"]
        assert ret[
            "comment"
        ] == "Repository already exists at {} and is checked out to branch '{}'".format(
            target, old_branch
        )

        # Run the state again to test idempotence (test mode)
        ret = self.run_state(
            "git.cloned", name=TEST_REPO, target=target, test=True, branch=old_branch
        )
        ret = ret[next(iter(ret))]
        assert ret["result"] is True
        assert not ret["changes"]
        assert ret[
            "comment"
        ] == "Repository already exists at {} and is checked out to branch '{}'".format(
            target, old_branch
        )

        # Change branch (test mode)
        ret = self.run_state(
            "git.cloned", name=TEST_REPO, target=target, branch=new_branch, test=True
        )
        ret = ret[next(iter(ret))]
        assert ret["result"] is None
        assert ret["changes"] == {"branch": {"old": old_branch, "new": new_branch}}
        assert ret["comment"] == "Branch would be changed to '{}'".format(new_branch)

        # Now really change the branch
        ret = self.run_state(
            "git.cloned", name=TEST_REPO, target=target, branch=new_branch
        )
        ret = ret[next(iter(ret))]
        assert ret["result"] is True
        assert ret["changes"] == {"branch": {"old": old_branch, "new": new_branch}}
        assert ret["comment"] == "Branch changed to '{}'".format(new_branch)

        # Change back to original branch. This tests that we don't attempt to
        # checkout a new branch (i.e. git checkout -b) for a branch that exists
        # locally, as that would fail.
        ret = self.run_state(
            "git.cloned", name=TEST_REPO, target=target, branch=old_branch
        )
        ret = ret[next(iter(ret))]
        assert ret["result"] is True
        assert ret["changes"] == {"branch": {"old": new_branch, "new": old_branch}}
        assert ret["comment"] == "Branch changed to '{}'".format(old_branch)

        # Test switching to a nonexistent branch. This should fail.
        ret = self.run_state(
            "git.cloned", name=TEST_REPO, target=target, branch=bad_branch
        )
        ret = ret[next(iter(ret))]
        assert ret["result"] is False
        assert not ret["changes"]
        assert ret["comment"].startswith(
            "Failed to change branch to '{}':".format(bad_branch)
        )

    @with_tempdir(create=False)
    @ensure_min_git(min_version="1.7.10")
    @pytest.mark.slow_test
    def test_cloned_with_nonexistant_branch(self, target):
        """
        Test git.cloned state with a nonexistent branch provided
        """
        branch = "thisbranchdoesnotexist"

        # Test mode
        ret = self.run_state(
            "git.cloned", name=TEST_REPO, target=target, branch=branch, test=True
        )
        ret = ret[next(iter(ret))]
        assert ret["result"] is None
        assert ret["changes"]
        assert ret["comment"] == "{} would be cloned to {} with branch '{}'".format(
            TEST_REPO, target, branch
        )

        # Now actually run the state
        ret = self.run_state("git.cloned", name=TEST_REPO, target=target, branch=branch)
        ret = ret[next(iter(ret))]
        assert ret["result"] is False
        assert not ret["changes"]
        assert ret["comment"].startswith("Clone failed:")
        assert "not found in upstream origin" in ret["comment"]

    @with_tempdir(create=False)
    @pytest.mark.slow_test
    def test_present(self, name):
        """
        git.present
        """
        ret = self.run_state("git.present", name=name, bare=True)
        self.assertSaltTrueReturn(ret)
        self.assertTrue(os.path.isfile(os.path.join(name, "HEAD")))

    @with_tempdir()
    @pytest.mark.slow_test
    def test_present_failure(self, name):
        """
        git.present
        """
        fname = os.path.join(name, "stoptheprocess")

        with salt.utils.files.fopen(fname, "a"):
            pass

        ret = self.run_state("git.present", name=name, bare=True)
        self.assertSaltFalseReturn(ret)
        self.assertFalse(os.path.isfile(os.path.join(name, "HEAD")))

    @with_tempdir()
    @pytest.mark.slow_test
    def test_present_empty_dir(self, name):
        """
        git.present
        """
        ret = self.run_state("git.present", name=name, bare=True)
        self.assertSaltTrueReturn(ret)
        self.assertTrue(os.path.isfile(os.path.join(name, "HEAD")))

    @with_tempdir()
    @pytest.mark.slow_test
    def test_config_set_value_with_space_character(self, name):
        """
        git.config
        """
        self.run_function("git.init", [name])

        ret = self.run_state(
            "git.config_set",
            name="user.name",
            value="foo bar",
            repo=name,
            **{"global": False}
        )
        self.assertSaltTrueReturn(ret)


@ensure_min_git
@uses_git_opts
class LocalRepoGitTest(ModuleCase, SaltReturnAssertsMixin):
    """
    Tests which do no require connectivity to github.com
    """

    def setUp(self):
        self.repo = tempfile.mkdtemp(dir=RUNTIME_VARS.TMP)
        self.admin = tempfile.mkdtemp(dir=RUNTIME_VARS.TMP)
        self.target = tempfile.mkdtemp(dir=RUNTIME_VARS.TMP)
        for dirname in (self.repo, self.admin, self.target):
            self.addCleanup(shutil.rmtree, dirname, ignore_errors=True)

        # Create bare repo
        self.run_function("git.init", [self.repo], bare=True)
        # Clone bare repo
        self.run_function("git.clone", [self.admin], url=self.repo)
        self._commit(self.admin, "", message="initial commit")
        self._push(self.admin)

    def _commit(self, repo_path, content, message):
        with salt.utils.files.fopen(os.path.join(repo_path, "foo"), "a") as fp_:
            fp_.write(content)
        self.run_function("git.add", [repo_path, "."])
        self.run_function(
            "git.commit",
            [repo_path, message],
            git_opts='-c user.name="Foo Bar" -c user.email=foo@bar.com',
        )

    def _push(self, repo_path, remote="origin", ref="master"):
        self.run_function("git.push", [repo_path], remote=remote, ref=ref)

    def _test_latest_force_reset_setup(self):
        # Perform the initial clone
        ret = self.run_state("git.latest", name=self.repo, target=self.target)
        self.assertSaltTrueReturn(ret)

        # Make and push changes to remote repo
        self._commit(self.admin, content="Hello world!\n", message="added a line")
        self._push(self.admin)

        # Make local changes to clone, but don't commit them
        with salt.utils.files.fopen(os.path.join(self.target, "foo"), "a") as fp_:
            fp_.write("Local changes!\n")

    @pytest.mark.slow_test
    def test_latest_force_reset_remote_changes(self):
        """
        This tests that an otherwise fast-forward change with local chanegs
        will not reset local changes when force_reset='remote_changes'
        """
        self._test_latest_force_reset_setup()

        # This should fail because of the local changes
        ret = self.run_state("git.latest", name=self.repo, target=self.target)
        self.assertSaltFalseReturn(ret)
        ret = ret[next(iter(ret))]
        self.assertIn("there are uncommitted changes", ret["comment"])
        self.assertIn("Set 'force_reset' to True (or 'remote-changes')", ret["comment"])
        self.assertEqual(ret["changes"], {})

        # Now run again with force_reset='remote_changes', the state should
        # succeed and discard the local changes
        ret = self.run_state(
            "git.latest",
            name=self.repo,
            target=self.target,
            force_reset="remote-changes",
        )
        self.assertSaltTrueReturn(ret)
        ret = ret[next(iter(ret))]
        self.assertIn("Uncommitted changes were discarded", ret["comment"])
        self.assertIn("Repository was fast-forwarded", ret["comment"])
        self.assertNotIn("forced update", ret["changes"])
        self.assertIn("revision", ret["changes"])

        # Add new local changes, but don't commit them
        with salt.utils.files.fopen(os.path.join(self.target, "foo"), "a") as fp_:
            fp_.write("More local changes!\n")

        # Now run again with force_reset='remote_changes', the state should
        # succeed with an up-to-date message and mention that there are local
        # changes, telling the user how to discard them.
        ret = self.run_state(
            "git.latest",
            name=self.repo,
            target=self.target,
            force_reset="remote-changes",
        )
        self.assertSaltTrueReturn(ret)
        ret = ret[next(iter(ret))]
        self.assertIn("up-to-date, but with uncommitted changes", ret["comment"])
        self.assertIn(
            "Set 'force_reset' to True to purge uncommitted changes", ret["comment"]
        )
        self.assertEqual(ret["changes"], {})

    @pytest.mark.slow_test
    def test_latest_force_reset_true_fast_forward(self):
        """
        This tests that an otherwise fast-forward change with local chanegs
        does reset local changes when force_reset=True
        """
        self._test_latest_force_reset_setup()

        # Test that local changes are discarded and that we fast-forward
        ret = self.run_state(
            "git.latest", name=self.repo, target=self.target, force_reset=True
        )
        self.assertSaltTrueReturn(ret)
        ret = ret[next(iter(ret))]
        self.assertIn("Uncommitted changes were discarded", ret["comment"])
        self.assertIn("Repository was fast-forwarded", ret["comment"])

        # Add new local changes
        with salt.utils.files.fopen(os.path.join(self.target, "foo"), "a") as fp_:
            fp_.write("More local changes!\n")

        # Running without setting force_reset should mention uncommitted changes
        ret = self.run_state("git.latest", name=self.repo, target=self.target)
        self.assertSaltTrueReturn(ret)
        ret = ret[next(iter(ret))]
        self.assertIn("up-to-date, but with uncommitted changes", ret["comment"])
        self.assertIn(
            "Set 'force_reset' to True to purge uncommitted changes", ret["comment"]
        )
        self.assertEqual(ret["changes"], {})

        # Test that local changes are discarded
        ret = self.run_state(
            "git.latest", name=TEST_REPO, target=self.target, force_reset=True
        )
        self.assertSaltTrueReturn(ret)
        ret = ret[next(iter(ret))]
        assert "Uncommitted changes were discarded" in ret["comment"]
        assert "Repository was hard-reset" in ret["comment"]
        assert "forced update" in ret["changes"]

    @pytest.mark.slow_test
    def test_latest_force_reset_true_non_fast_forward(self):
        """
        This tests that a non fast-forward change with divergent commits fails
        unless force_reset=True.
        """
        self._test_latest_force_reset_setup()

        # Reset to remote HEAD
        ret = self.run_state(
            "git.latest", name=self.repo, target=self.target, force_reset=True
        )
        self.assertSaltTrueReturn(ret)
        ret = ret[next(iter(ret))]
        self.assertIn("Uncommitted changes were discarded", ret["comment"])
        self.assertIn("Repository was fast-forwarded", ret["comment"])

        # Make and push changes to remote repo
        self._commit(self.admin, content="New line\n", message="added another line")
        self._push(self.admin)

        # Make different changes to local file and commit locally
        self._commit(
            self.target,
            content="Different new line\n",
            message="added a different line",
        )

        # This should fail since the local clone has diverged and cannot
        # fast-forward to the remote rev
        ret = self.run_state("git.latest", name=self.repo, target=self.target)
        self.assertSaltFalseReturn(ret)
        ret = ret[next(iter(ret))]
        self.assertIn("this is not a fast-forward merge", ret["comment"])
        self.assertIn("Set 'force_reset' to True to force this update", ret["comment"])
        self.assertEqual(ret["changes"], {})

        # Repeat the state with force_reset=True and confirm that the hard
        # reset was performed
        ret = self.run_state(
            "git.latest", name=self.repo, target=self.target, force_reset=True
        )
        self.assertSaltTrueReturn(ret)
        ret = ret[next(iter(ret))]
        self.assertIn("Repository was hard-reset", ret["comment"])
        self.assertIn("forced update", ret["changes"])
        self.assertIn("revision", ret["changes"])

    @pytest.mark.slow_test
    def test_renamed_default_branch(self):
        """
        Test the case where the remote branch has been removed
        https://github.com/saltstack/salt/issues/36242
        """
        # Rename remote 'master' branch to 'develop'
        os.rename(
            os.path.join(self.repo, "refs", "heads", "master"),
            os.path.join(self.repo, "refs", "heads", "develop"),
        )

        # Run git.latest state. This should successfully clone and fail with a
        # specific error in the comment field.
        ret = self.run_state(
            "git.latest",
            name=self.repo,
            target=self.target,
            rev="develop",
        )
        self.assertSaltFalseReturn(ret)
        self.assertEqual(
            ret[next(iter(ret))]["comment"],
            "Remote HEAD refers to a ref that does not exist. "
            "This can happen when the default branch on the "
            "remote repository is renamed or deleted. If you "
            "are unable to fix the remote repository, you can "
            "work around this by setting the 'branch' argument "
            "(which will ensure that the named branch is created "
            "if it does not already exist).\n\n"
            "Changes already made: {} cloned to {}".format(self.repo, self.target),
        )
        self.assertEqual(
            ret[next(iter(ret))]["changes"],
            {"new": "{} => {}".format(self.repo, self.target)},
        )

        # Run git.latest state again. This should fail again, with a different
        # error in the comment field, and should not change anything.
        ret = self.run_state(
            "git.latest",
            name=self.repo,
            target=self.target,
            rev="develop",
        )
        self.assertSaltFalseReturn(ret)
        self.assertEqual(
            ret[next(iter(ret))]["comment"],
            "Cannot set/unset upstream tracking branch, local "
            "HEAD refers to nonexistent branch. This may have "
            "been caused by cloning a remote repository for which "
            "the default branch was renamed or deleted. If you "
            "are unable to fix the remote repository, you can "
            "work around this by setting the 'branch' argument "
            "(which will ensure that the named branch is created "
            "if it does not already exist).",
        )
        self.assertEqual(ret[next(iter(ret))]["changes"], {})

        # Run git.latest state again with a branch manually set. This should
        # checkout a new branch and the state should pass.
        ret = self.run_state(
            "git.latest",
            name=self.repo,
            target=self.target,
            rev="develop",
            branch="develop",
        )
        # State should succeed
        self.assertSaltTrueReturn(ret)
        self.assertSaltCommentRegexpMatches(
            ret,
            "New branch 'develop' was checked out, with origin/develop "
            r"\([0-9a-f]{7}\) as a starting point",
        )
        # Only the revision should be in the changes dict.
        self.assertEqual(list(ret[next(iter(ret))]["changes"].keys()), ["revision"])
        # Since the remote repo was incorrectly set up, the local head should
        # not exist (therefore the old revision should be None).
        self.assertEqual(ret[next(iter(ret))]["changes"]["revision"]["old"], None)
        # Make sure the new revision is a SHA (40 chars, all hex)
        self.assertTrue(len(ret[next(iter(ret))]["changes"]["revision"]["new"]) == 40)
        self.assertTrue(
            all(
                [
                    x in string.hexdigits
                    for x in ret[next(iter(ret))]["changes"]["revision"]["new"]
                ]
            )
        )
