"""
Tests for git execution module

NOTE: These tests may modify the global git config, and have been marked as
destructive as a result. If no values are set for user.name or user.email in
the user's global .gitconfig, then these tests will set one.
"""

import logging
import os
import pathlib
import re
import shutil
import subprocess
import tarfile
import tempfile
from contextlib import closing

import pytest

import salt.utils.data
import salt.utils.files
import salt.utils.platform
from salt.utils.versions import LooseVersion
from tests.support.case import ModuleCase
from tests.support.runtests import RUNTIME_VARS

log = logging.getLogger(__name__)


def _git_version():
    git = shutil.which("git")
    if not git:
        log.debug("Git not installed")
        return False
    ret = subprocess.run(
        ["git", "--version"],
        stdout=subprocess.PIPE,
        check=False,
        shell=False,
        text=True,
    )
    # On macOS, the git version is displayed in a different format
    #  git version 2.21.1 (Apple Git-122.3)
    # As opposed to:
    #  git version 2.21.1
    version_str = ret.stdout.strip().split("(")[0].strip().split()[-1]
    git_version = LooseVersion(version_str)
    log.debug("Detected git version: %s", git_version)
    return git_version


def _worktrees_supported():
    """
    Check if the git version is 2.5.0 or later
    """
    try:
        return _git_version() >= LooseVersion("2.5.0")
    except AttributeError:
        return False


@pytest.mark.windows_whitelisted
@pytest.mark.skip_if_binaries_missing("git")
class GitModuleTest(ModuleCase):
    def setUp(self):
        super().setUp()
        self.repo = tempfile.mkdtemp(dir=RUNTIME_VARS.TMP)
        self.addCleanup(shutil.rmtree, self.repo, ignore_errors=True)
        self.addCleanup(delattr, self, "repo")
        self.files = ("foo", "bar", "baz", "питон")
        self.addCleanup(delattr, self, "files")
        self.dirs = ("", "qux")
        self.addCleanup(delattr, self, "dirs")
        self.branches = ("master", "iamanewbranch")
        self.addCleanup(delattr, self, "branches")
        self.tags = ("git_testing",)
        self.addCleanup(delattr, self, "tags")
        for dirname in self.dirs:
            dir_path = pathlib.Path(self.repo) / dirname
            dir_path.mkdir(parents=True, exist_ok=True)
            for filename in self.files:
                with salt.utils.files.fopen(str(dir_path / filename), "wb") as fp_:
                    fp_.write(f"This is a test file named {filename}.".encode())
        # Navigate to the root of the repo to init, stage, and commit
        with pytest.helpers.change_cwd(self.repo):
            # Initialize a new git repository
            subprocess.check_call(["git", "init", "--quiet", self.repo])

            # Set user.name and user.email config attributes if not present
            for key, value in (
                ("user.name", "Jenkins"),
                ("user.email", "qa@saltstack.com"),
            ):
                # Check if key is missing
                keycheck = subprocess.Popen(
                    ["git", "config", "--get", "--global", key],
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                )
                if keycheck.wait() != 0:
                    # Set the key if it is not present
                    subprocess.check_call(["git", "config", "--global", key, value])

            subprocess.check_call(["git", "add", "."])
            subprocess.check_call(
                ["git", "commit", "--quiet", "--message", "Initial commit"]
            )
            # Add a tag
            subprocess.check_call(["git", "tag", "-a", self.tags[0], "-m", "Add tag"])
            # Checkout a second branch
            subprocess.check_call(
                ["git", "checkout", "--quiet", "-b", self.branches[1]]
            )
            # Add a line to the file
            with salt.utils.files.fopen(self.files[0], "a") as fp_:
                fp_.write(salt.utils.stringutils.to_str("Added a line\n"))
            # Commit the updated file
            subprocess.check_call(
                [
                    "git",
                    "commit",
                    "--quiet",
                    "--message",
                    "Added a line to " + self.files[0],
                    self.files[0],
                ]
            )
            # Switch back to master
            subprocess.check_call(["git", "checkout", "--quiet", "master"])

    def run_function(self, *args, **kwargs):  # pylint: disable=arguments-differ
        """
        Ensure that results are decoded

        TODO: maybe move this behavior to ModuleCase itself?
        """
        return salt.utils.data.decode(super().run_function(*args, **kwargs))

    @pytest.mark.slow_test
    def test_add_dir(self):
        """
        Test git.add with a directory
        """
        newdir = "quux"
        # Change to the repo dir
        newdir_path = pathlib.Path(self.repo) / newdir
        newdir_path.mkdir(parents=True, exist_ok=True)
        files = [str(newdir_path / x) for x in self.files]
        files_relpath = [os.path.join(newdir, x) for x in self.files]
        for path in files:
            with salt.utils.files.fopen(path, "wb") as fp_:
                fp_.write(f"This is a test file with relative path {path}.\n".encode())
        ret = self.run_function("git.add", [self.repo, newdir])
        res = "\n".join(sorted(f"add '{x}'" for x in files_relpath))
        if salt.utils.platform.is_windows():
            res = res.replace("\\", "/")
        self.assertEqual(ret, res)

    @pytest.mark.slow_test
    def test_add_file(self):
        """
        Test git.add with a file
        """
        filename = "quux"
        file_path = os.path.join(self.repo, filename)
        with salt.utils.files.fopen(file_path, "w") as fp_:
            fp_.write(
                salt.utils.stringutils.to_str(
                    f"This is a test file named {filename}.\n"
                )
            )
        ret = self.run_function("git.add", [self.repo, filename])
        self.assertEqual(ret, f"add '{filename}'")

    @pytest.mark.slow_test
    def test_archive(self):
        """
        Test git.archive
        """
        tar_archive = os.path.join(RUNTIME_VARS.TMP, "test_archive.tar.gz")
        try:
            self.assertTrue(
                self.run_function(
                    "git.archive", [self.repo, tar_archive], prefix="foo/"
                )
            )
            self.assertTrue(tarfile.is_tarfile(tar_archive))
            self.run_function("cmd.run", ["cp " + tar_archive + " /root/"])
            with closing(tarfile.open(tar_archive, "r")) as tar_obj:
                self.assertEqual(
                    sorted(salt.utils.data.decode(tar_obj.getnames())),
                    sorted(
                        [
                            "foo",
                            "foo/bar",
                            "foo/baz",
                            "foo/foo",
                            "foo/питон",
                            "foo/qux",
                            "foo/qux/bar",
                            "foo/qux/baz",
                            "foo/qux/foo",
                            "foo/qux/питон",
                        ]
                    ),
                )
        finally:
            try:
                os.unlink(tar_archive)
            except OSError:
                pass

    @pytest.mark.slow_test
    def test_archive_subdir(self):
        """
        Test git.archive on a subdir, giving only a partial copy of the repo in
        the resulting archive
        """
        tar_archive = os.path.join(RUNTIME_VARS.TMP, "test_archive.tar.gz")
        try:
            self.assertTrue(
                self.run_function(
                    "git.archive",
                    [os.path.join(self.repo, "qux"), tar_archive],
                    prefix="foo/",
                )
            )
            self.assertTrue(tarfile.is_tarfile(tar_archive))
            with closing(tarfile.open(tar_archive, "r")) as tar_obj:
                self.assertEqual(
                    sorted(salt.utils.data.decode(tar_obj.getnames())),
                    sorted(["foo", "foo/bar", "foo/baz", "foo/foo", "foo/питон"]),
                )
        finally:
            try:
                os.unlink(tar_archive)
            except OSError:
                pass

    @pytest.mark.slow_test
    def test_branch(self):
        """
        Test creating, renaming, and deleting a branch using git.branch
        """
        renamed_branch = "ihavebeenrenamed"
        self.assertTrue(self.run_function("git.branch", [self.repo, self.branches[1]]))
        self.assertTrue(
            self.run_function(
                "git.branch", [self.repo, renamed_branch], opts="-m " + self.branches[1]
            )
        )
        self.assertTrue(
            self.run_function("git.branch", [self.repo, renamed_branch], opts="-D")
        )

    @pytest.mark.slow_test
    def test_checkout(self):
        """
        Test checking out a new branch and then checking out master again
        """
        new_branch = "iamanothernewbranch"
        self.assertEqual(
            self.run_function(
                "git.checkout", [self.repo, "HEAD"], opts="-b " + new_branch
            ),
            "Switched to a new branch '" + new_branch + "'",
        )
        self.assertTrue(
            "Switched to branch 'master'"
            in self.run_function("git.checkout", [self.repo, "master"]),
        )

    @pytest.mark.slow_test
    def test_checkout_no_rev(self):
        """
        Test git.checkout without a rev, both with -b in opts and without
        """
        new_branch = "iamanothernewbranch"
        self.assertEqual(
            self.run_function(
                "git.checkout", [self.repo], rev=None, opts="-b " + new_branch
            ),
            "Switched to a new branch '" + new_branch + "'",
        )
        self.assertTrue(
            "'rev' argument is required unless -b or -B in opts"
            in self.run_function("git.checkout", [self.repo])
        )

    @pytest.mark.slow_test
    def test_clone(self):
        """
        Test cloning an existing repo
        """
        clone_parent_dir = tempfile.mkdtemp(dir=RUNTIME_VARS.TMP)
        self.assertTrue(self.run_function("git.clone", [clone_parent_dir, self.repo]))
        # Cleanup after yourself
        shutil.rmtree(clone_parent_dir, True)

    @pytest.mark.slow_test
    def test_clone_with_alternate_name(self):
        """
        Test cloning an existing repo with an alternate name for the repo dir
        """
        clone_parent_dir = tempfile.mkdtemp(dir=RUNTIME_VARS.TMP)
        clone_name = os.path.basename(self.repo)
        # Change to newly-created temp dir
        self.assertTrue(
            self.run_function(
                "git.clone", [clone_parent_dir, self.repo], name=clone_name
            )
        )
        # Cleanup after yourself
        shutil.rmtree(clone_parent_dir, True)

    @pytest.mark.slow_test
    def test_commit(self):
        """
        Test git.commit two ways:
            1) First using git.add, then git.commit
            2) Using git.commit with the 'filename' argument to skip staging
        """
        filename = "foo"
        commit_re_prefix = r"^\[master [0-9a-f]+\] "
        # Add a line
        with salt.utils.files.fopen(os.path.join(self.repo, filename), "a") as fp_:
            fp_.write("Added a line\n")
        # Stage the file
        self.run_function("git.add", [self.repo, filename])
        # Commit the staged file
        commit_msg = "Add a line to " + filename
        ret = self.run_function("git.commit", [self.repo, commit_msg])
        # Make sure the expected line is in the output
        self.assertTrue(bool(re.search(commit_re_prefix + commit_msg, ret)))
        # Add another line
        with salt.utils.files.fopen(os.path.join(self.repo, filename), "a") as fp_:
            fp_.write("Added another line\n")
        # Commit the second file without staging
        commit_msg = "Add another line to " + filename
        ret = self.run_function(
            "git.commit", [self.repo, commit_msg], filename=filename
        )
        self.assertTrue(bool(re.search(commit_re_prefix + commit_msg, ret)))

    @pytest.mark.slow_test
    def test_config(self):
        """
        Test setting, getting, and unsetting config values

        WARNING: This test will modify and completely remove a config section
        'foo', both in the repo created in setUp() and in the user's global
        .gitconfig.
        """

        def _clear_config():
            cmds = (
                ["git", "config", "--remove-section", "foo"],
                ["git", "config", "--global", "--remove-section", "foo"],
            )
            for cmd in cmds:
                with salt.utils.files.fopen(os.devnull, "w") as devnull:
                    try:
                        subprocess.check_call(cmd, stderr=devnull)
                    except subprocess.CalledProcessError:
                        pass

        cfg_local = {"foo.single": ["foo"], "foo.multi": ["foo", "bar", "baz"]}
        cfg_global = {"foo.single": ["abc"], "foo.multi": ["abc", "def", "ghi"]}
        _clear_config()
        try:
            log.debug("Try to specify both single and multivar (should raise error)")
            self.assertTrue(
                "Only one of 'value' and 'multivar' is permitted"
                in self.run_function(
                    "git.config_set",
                    ["foo.single"],
                    value=cfg_local["foo.single"][0],
                    multivar=cfg_local["foo.multi"],
                    cwd=self.repo,
                )
            )
            log.debug("Try to set single local value without cwd (should raise error)")
            self.assertTrue(
                "'cwd' argument required unless global=True"
                in self.run_function(
                    "git.config_set",
                    ["foo.single"],
                    value=cfg_local["foo.single"][0],
                )
            )
            log.debug("Set single local value")
            self.assertEqual(
                self.run_function(
                    "git.config_set",
                    ["foo.single"],
                    value=cfg_local["foo.single"][0],
                    cwd=self.repo,
                ),
                cfg_local["foo.single"],
            )
            log.debug("Set single global value")
            self.assertEqual(
                self.run_function(
                    "git.config_set",
                    ["foo.single"],
                    value=cfg_global["foo.single"][0],
                    **{"global": True},
                ),
                cfg_global["foo.single"],
            )
            log.debug("Set local multivar")
            self.assertEqual(
                self.run_function(
                    "git.config_set",
                    ["foo.multi"],
                    multivar=cfg_local["foo.multi"],
                    cwd=self.repo,
                ),
                cfg_local["foo.multi"],
            )
            log.debug("Set global multivar")
            self.assertEqual(
                self.run_function(
                    "git.config_set",
                    ["foo.multi"],
                    multivar=cfg_global["foo.multi"],
                    **{"global": True},
                ),
                cfg_global["foo.multi"],
            )
            log.debug("Get single local value")
            self.assertEqual(
                self.run_function("git.config_get", ["foo.single"], cwd=self.repo),
                cfg_local["foo.single"][0],
            )
            log.debug("Get single value from local multivar")
            self.assertEqual(
                self.run_function("git.config_get", ["foo.multi"], cwd=self.repo),
                cfg_local["foo.multi"][-1],
            )
            log.debug("Get all values from multivar (includes globals)")
            self.assertEqual(
                self.run_function(
                    "git.config_get", ["foo.multi"], cwd=self.repo, **{"all": True}
                ),
                cfg_local["foo.multi"],
            )
            log.debug("Get single global value")
            self.assertEqual(
                self.run_function("git.config_get", ["foo.single"], **{"global": True}),
                cfg_global["foo.single"][0],
            )
            log.debug("Get single value from global multivar")
            self.assertEqual(
                self.run_function("git.config_get", ["foo.multi"], **{"global": True}),
                cfg_global["foo.multi"][-1],
            )
            log.debug("Get all values from global multivar")
            self.assertEqual(
                self.run_function(
                    "git.config_get", ["foo.multi"], **{"all": True, "global": True}
                ),
                cfg_global["foo.multi"],
            )
            log.debug("Get all local keys/values using regex")
            self.assertEqual(
                self.run_function(
                    "git.config_get_regexp", ["foo.(single|multi)"], cwd=self.repo
                ),
                cfg_local,
            )
            log.debug("Get all global keys/values using regex")
            self.assertEqual(
                self.run_function(
                    "git.config_get_regexp",
                    ["foo.(single|multi)"],
                    cwd=self.repo,
                    **{"global": True},
                ),
                cfg_global,
            )
            log.debug("Get just the local foo.multi values containing 'a'")
            self.assertEqual(
                self.run_function(
                    "git.config_get_regexp",
                    ["foo.multi"],
                    value_regex="a",
                    cwd=self.repo,
                ),
                {"foo.multi": [x for x in cfg_local["foo.multi"] if "a" in x]},
            )
            log.debug("Get just the global foo.multi values containing 'a'")
            self.assertEqual(
                self.run_function(
                    "git.config_get_regexp",
                    ["foo.multi"],
                    value_regex="a",
                    cwd=self.repo,
                    **{"global": True},
                ),
                {"foo.multi": [x for x in cfg_global["foo.multi"] if "a" in x]},
            )

            # TODO: More robust unset testing, try to trigger all the
            # exceptions raised.

            log.debug("Unset a single local value")
            self.assertTrue(
                self.run_function(
                    "git.config_unset",
                    ["foo.single"],
                    cwd=self.repo,
                )
            )
            log.debug("Unset an entire local multivar")
            self.assertTrue(
                self.run_function(
                    "git.config_unset", ["foo.multi"], cwd=self.repo, **{"all": True}
                )
            )
            log.debug("Unset a single global value")
            self.assertTrue(
                self.run_function(
                    "git.config_unset", ["foo.single"], **{"global": True}
                )
            )
            log.debug("Unset an entire local multivar")
            self.assertTrue(
                self.run_function(
                    "git.config_unset", ["foo.multi"], **{"all": True, "global": True}
                )
            )
        finally:
            _clear_config()

    @pytest.mark.slow_test
    def test_current_branch(self):
        """
        Test git.current_branch
        """
        self.assertEqual(self.run_function("git.current_branch", [self.repo]), "master")

    @pytest.mark.slow_test
    def test_describe(self):
        """
        Test git.describe
        """
        self.assertEqual(self.run_function("git.describe", [self.repo]), self.tags[0])

    # Test for git.fetch would be unreliable on Jenkins, skipping for now
    # The test should go into test_remotes when ready

    @pytest.mark.slow_test
    def test_init(self):
        """
        Use git.init to init a new repo
        """
        new_repo = tempfile.mkdtemp(dir=RUNTIME_VARS.TMP)

        # `tempfile.mkdtemp` gets the path to the Temp directory using
        # environment variables. As a result, folder names longer than 8
        # characters are shortened. For example "C:\Users\Administrators"
        # becomes "C:\Users\Admini~1". However, the "git.init" function returns
        # the full, unshortened name of the folder. Therefore you can't compare
        # the path returned by `tempfile.mkdtemp` and the results of `git.init`
        # exactly.
        if salt.utils.platform.is_windows():
            new_repo = new_repo.replace("\\", "/")

            # Get the name of the temp directory
            tmp_dir = os.path.basename(new_repo)

            # Get git output
            git_ret = self.run_function("git.init", [new_repo]).lower()

            self.assertIn("Initialized empty Git repository in".lower(), git_ret)
            self.assertIn(tmp_dir, git_ret)

        else:
            self.assertEqual(
                self.run_function("git.init", [new_repo]).lower(),
                f"Initialized empty Git repository in {new_repo}/.git/".lower(),
            )

        shutil.rmtree(new_repo)

    @pytest.mark.slow_test
    def test_list_branches(self):
        """
        Test git.list_branches
        """
        self.assertEqual(
            self.run_function("git.list_branches", [self.repo]), sorted(self.branches)
        )

    @pytest.mark.slow_test
    def test_list_tags(self):
        """
        Test git.list_tags
        """
        self.assertEqual(
            self.run_function("git.list_tags", [self.repo]), sorted(self.tags)
        )

    # Test for git.ls_remote will need to wait for now, while I think of how to
    # properly mock it.

    @pytest.mark.slow_test
    def test_merge(self):
        """
        Test git.merge

        # TODO: Test more than just a fast-forward merge
        """
        # Merge the second branch into the current branch
        ret = self.run_function("git.merge", [self.repo], rev=self.branches[1])
        # Merge should be a fast-forward
        self.assertTrue("Fast-forward" in ret.splitlines())

    @pytest.mark.slow_test
    def test_merge_base_and_tree(self):
        """
        Test git.merge_base, git.merge_tree and git.revision

        TODO: Test all of the arguments
        """
        # Get the SHA1 of current HEAD
        head_rev = self.run_function("git.revision", [self.repo], rev="HEAD")
        # Make sure revision is a 40-char string
        self.assertTrue(len(head_rev) == 40)
        # Get the second branch's SHA1
        second_rev = self.run_function(
            "git.revision", [self.repo], rev=self.branches[1], timeout=120
        )
        # Make sure revision is a 40-char string
        self.assertTrue(len(second_rev) == 40)
        # self.branches[1] should be just one commit ahead, so the merge base
        # for master and self.branches[1] should be the same as the current
        # HEAD.
        self.assertEqual(
            self.run_function(
                "git.merge_base", [self.repo], refs=",".join((head_rev, second_rev))
            ),
            head_rev,
        )
        # There should be no conflict here, so the return should be an empty
        # string.
        ret = self.run_function(
            "git.merge_tree", [self.repo, head_rev, second_rev]
        ).splitlines()
        self.assertTrue(len([x for x in ret if x.startswith("@@")]) == 1)

    # Test for git.pull would be unreliable on Jenkins, skipping for now

    # Test for git.push would be unreliable on Jenkins, skipping for now

    @pytest.mark.slow_test
    def test_rebase(self):
        """
        Test git.rebase
        """
        # Switch to the second branch
        self.assertNotIn(
            "ERROR",
            self.run_function("git.checkout", [self.repo], rev=self.branches[0]),
        )
        # Make a change to a different file than the one modified in setUp
        file_path = os.path.join(self.repo, self.files[1])
        with salt.utils.files.fopen(file_path, "a") as fp_:
            fp_.write("Added a line\n")
        # Commit the change
        self.assertNotIn(
            "ERROR",
            self.run_function(
                "git.commit",
                [self.repo, "Added a line to " + self.files[1]],
                filename=self.files[1],
            ),
        )
        # Switch to the second branch
        self.assertNotIn(
            "ERROR",
            self.run_function("git.checkout", [self.repo], rev=self.branches[1]),
        )
        # Perform the rebase. The commit should show a comment about
        # self.files[0] being modified, as that is the file that was modified
        # in the second branch in the setUp function
        ret = self.run_function("git.rebase", [self.repo], opts="-vvv")
        self.assertNotIn("ERROR", ret)
        self.assertNotIn("up to date", ret)

    # Test for git.remote_get is in test_remotes

    # Test for git.remote_set is in test_remotes

    @pytest.mark.slow_test
    def test_remotes(self):
        """
        Test setting a remote (git.remote_set), and getting a remote
        (git.remote_get and git.remotes)

        TODO: Properly mock fetching a remote (git.fetch), and build out more
        robust testing that confirms that the https auth bits work.
        """
        remotes = {
            "first": {"fetch": "/dev/null", "push": "/dev/null"},
            "second": {"fetch": "/dev/null", "push": "/dev/stdout"},
        }
        self.assertEqual(
            self.run_function(
                "git.remote_set", [self.repo, remotes["first"]["fetch"]], remote="first"
            ),
            remotes["first"],
        )
        self.assertEqual(
            self.run_function(
                "git.remote_set",
                [self.repo, remotes["second"]["fetch"]],
                remote="second",
                push_url=remotes["second"]["push"],
            ),
            remotes["second"],
        )
        self.assertEqual(self.run_function("git.remotes", [self.repo]), remotes)

    @pytest.mark.slow_test
    def test_reset(self):
        """
        Test git.reset

        TODO: Test more than just a hard reset
        """
        # Switch to the second branch
        self.assertTrue(
            "ERROR"
            not in self.run_function("git.checkout", [self.repo], rev=self.branches[1])
        )
        # Back up one commit. We should now be at the same revision as master
        self.run_function("git.reset", [self.repo], opts="--hard HEAD~1")
        # Get the SHA1 of current HEAD (remember, we're on the second branch)
        head_rev = self.run_function("git.revision", [self.repo], rev="HEAD")
        # Make sure revision is a 40-char string
        self.assertTrue(len(head_rev) == 40)
        # Get the master branch's SHA1
        master_rev = self.run_function("git.revision", [self.repo], rev="master")
        # Make sure revision is a 40-char string
        self.assertTrue(len(master_rev) == 40)
        # The two revisions should be the same
        self.assertEqual(head_rev, master_rev)

    @pytest.mark.slow_test
    def test_rev_parse(self):
        """
        Test git.rev_parse
        """
        # Using --abbrev-ref on HEAD will give us the current branch
        self.assertEqual(
            self.run_function(
                "git.rev_parse", [self.repo, "HEAD"], opts="--abbrev-ref"
            ),
            "master",
        )

    # Test for git.revision happens in test_merge_base

    @pytest.mark.slow_test
    def test_rm(self):
        """
        Test git.rm
        """
        single_file = self.files[0]
        entire_dir = self.dirs[1]
        # Remove a single file
        self.assertEqual(
            self.run_function("git.rm", [self.repo, single_file]),
            "rm '" + single_file + "'",
        )
        # Remove an entire dir
        expected = "\n".join(
            sorted("rm '" + os.path.join(entire_dir, x) + "'" for x in self.files)
        )
        if salt.utils.platform.is_windows():
            expected = expected.replace("\\", "/")
        self.assertEqual(
            self.run_function("git.rm", [self.repo, entire_dir], opts="-r"), expected
        )

    @pytest.mark.slow_test
    def test_stash(self):
        """
        Test git.stash

        # TODO: test more stash actions
        """
        file_path = os.path.join(self.repo, self.files[0])
        with salt.utils.files.fopen(file_path, "a") as fp_:
            fp_.write("Temp change to be stashed")
        self.assertTrue("ERROR" not in self.run_function("git.stash", [self.repo]))
        # List stashes
        ret = self.run_function("git.stash", [self.repo], action="list")
        self.assertTrue("ERROR" not in ret)
        self.assertTrue(len(ret.splitlines()) == 1)
        # Apply the stash
        self.assertTrue(
            "ERROR"
            not in self.run_function(
                "git.stash", [self.repo], action="apply", opts="stash@{0}"
            )
        )
        # Drop the stash
        self.assertTrue(
            "ERROR"
            not in self.run_function(
                "git.stash", [self.repo], action="drop", opts="stash@{0}"
            )
        )

    @pytest.mark.slow_test
    def test_status(self):
        """
        Test git.status
        """
        changes = {
            "modified": ["foo"],
            "new": ["thisisdefinitelyanewfile"],
            "deleted": ["bar"],
            "untracked": ["thisisalsoanewfile"],
        }
        for filename in changes["modified"]:
            with salt.utils.files.fopen(os.path.join(self.repo, filename), "a") as fp_:
                fp_.write("Added a line\n")
        for filename in changes["new"]:
            with salt.utils.files.fopen(os.path.join(self.repo, filename), "w") as fp_:
                fp_.write(
                    salt.utils.stringutils.to_str(
                        f"This is a new file named {filename}."
                    )
                )
            # Stage the new file so it shows up as a 'new' file
            self.assertTrue(
                "ERROR" not in self.run_function("git.add", [self.repo, filename])
            )
        for filename in changes["deleted"]:
            self.run_function("git.rm", [self.repo, filename])
        for filename in changes["untracked"]:
            with salt.utils.files.fopen(os.path.join(self.repo, filename), "w") as fp_:
                fp_.write(
                    salt.utils.stringutils.to_str(
                        f"This is a new file named {filename}."
                    )
                )
        self.assertEqual(self.run_function("git.status", [self.repo]), changes)

    # TODO: Add git.submodule test

    @pytest.mark.slow_test
    def test_symbolic_ref(self):
        """
        Test git.symbolic_ref
        """
        self.assertEqual(
            self.run_function("git.symbolic_ref", [self.repo, "HEAD"], opts="--quiet"),
            "refs/heads/master",
        )

    @pytest.mark.skipif(
        not _worktrees_supported(),
        reason="Git 2.5 or newer required for worktree support",
    )
    @pytest.mark.slow_test
    def test_worktree_add_rm(self):
        """
        This tests git.worktree_add, git.is_worktree, git.worktree_rm, and
        git.worktree_prune. Tests for 'git worktree list' are covered in
        tests.unit.modules.git_test.
        """
        # We don't need to enclose this comparison in a try/except, since the
        # decorator would skip this test if git is not installed and we'd never
        # get here in the first place.
        git_version = _git_version()
        if git_version >= LooseVersion("2.6.0"):
            worktree_add_prefix = "Preparing "
        else:
            worktree_add_prefix = "Enter "

        worktree_path = tempfile.mkdtemp(dir=RUNTIME_VARS.TMP)
        worktree_basename = os.path.basename(worktree_path)
        worktree_path2 = tempfile.mkdtemp(dir=RUNTIME_VARS.TMP)
        worktree_basename2 = os.path.basename(worktree_path2)

        # Even though this is Windows, git commands return a unix style path
        if salt.utils.platform.is_windows():
            worktree_path = worktree_path.replace("\\", "/")
            worktree_path2 = worktree_path2.replace("\\", "/")

        # Add the worktrees
        ret = self.run_function(
            "git.worktree_add",
            [self.repo, worktree_path],
        )
        self.assertTrue(worktree_add_prefix in ret)
        self.assertTrue(worktree_basename in ret)
        ret = self.run_function("git.worktree_add", [self.repo, worktree_path2])
        self.assertTrue(worktree_add_prefix in ret)
        self.assertTrue(worktree_basename2 in ret)
        # Check if this new path is a worktree
        self.assertTrue(self.run_function("git.is_worktree", [worktree_path]))
        # Check if the main repo is a worktree
        self.assertFalse(self.run_function("git.is_worktree", [self.repo]))
        # Check if a non-repo directory is a worktree
        empty_dir = tempfile.mkdtemp(dir=RUNTIME_VARS.TMP)
        self.assertFalse(self.run_function("git.is_worktree", [empty_dir]))
        shutil.rmtree(empty_dir)
        # Remove the first worktree
        self.assertTrue(self.run_function("git.worktree_rm", [worktree_path]))
        # Prune the worktrees
        prune_message = (
            "Removing worktrees/{}: gitdir file points to non-existent location".format(
                worktree_basename
            )
        )
        # Test dry run output. It should match the same output we get when we
        # actually prune the worktrees.
        result = self.run_function("git.worktree_prune", [self.repo], dry_run=True)
        self.assertEqual(result, prune_message)
        # Test pruning for real, and make sure the output is the same
        self.assertEqual(
            self.run_function("git.worktree_prune", [self.repo]), prune_message
        )
