# -*- coding: utf-8 -*-
"""
    :codeauthor: Erik Johnson <erik@saltstack.com>
"""

# Import Python libs
from __future__ import absolute_import

import logging
import os

# Import Salt Libs
import salt.states.git as git_state  # Don't potentially shadow GitPython

# Import Salt Testing Libs
from tests.support.helpers import with_tempdir
from tests.support.mixins import LoaderModuleMockMixin
from tests.support.mock import DEFAULT, MagicMock, Mock, patch
from tests.support.unit import TestCase

log = logging.getLogger(__name__)


class GitTestCase(TestCase, LoaderModuleMockMixin):
    """
    Test cases for salt.states.git
    """

    def setup_loader_modules(self):
        return {
            git_state: {"__env__": "base", "__opts__": {"test": False}, "__salt__": {}}
        }

    @with_tempdir()
    def test_latest_no_diff_for_bare_repo(self, target):
        """
        This test ensures that we don't attempt to diff when cloning a repo
        using either bare=True or mirror=True.
        """
        name = "https://foo.com/bar/baz.git"
        gitdir = os.path.join(target, "refs")
        isdir_mock = MagicMock(
            side_effect=lambda path: DEFAULT if path != gitdir else True
        )

        branches = ["foo", "bar", "baz"]
        tags = ["v1.1.0", "v.1.1.1", "v1.2.0"]
        local_head = "b9ef06ab6b7524eb7c27d740dbbd5109c6d75ee4"
        remote_head = "eef672c1ec9b8e613905dbcd22a4612e31162807"

        git_diff = Mock()
        dunder_salt = {
            "git.current_branch": MagicMock(return_value=branches[0]),
            "git.config_get_regexp": MagicMock(return_value={}),
            "git.diff": git_diff,
            "git.fetch": MagicMock(return_value={}),
            "git.is_worktree": MagicMock(return_value=False),
            "git.list_branches": MagicMock(return_value=branches),
            "git.list_tags": MagicMock(return_value=tags),
            "git.remote_refs": MagicMock(return_value={"HEAD": remote_head}),
            "git.remotes": MagicMock(
                return_value={"origin": {"fetch": name, "push": name}}
            ),
            "git.rev_parse": MagicMock(side_effect=git_state.CommandExecutionError()),
            "git.revision": MagicMock(return_value=local_head),
            "git.version": MagicMock(return_value="1.8.3.1"),
        }
        with patch("os.path.isdir", isdir_mock), patch.dict(
            git_state.__salt__, dunder_salt
        ):
            result = git_state.latest(
                name=name, target=target, mirror=True,  # mirror=True implies bare=True
            )
            assert result["result"] is True, result
            git_diff.assert_not_called()

    def test_uptodate_message_format_gen(self):
        fetch_url = "https://xyz.invalid/salt/unit/test/repo.git"
        local_path = "/local/salt/unit/test/repo.git"
        branch = "master"
        head_rev = "cafe0000cafe0000cafe0000cafe0000cafe0000"
        remote_name = "salt_test_remote"

        tags = []
        remote_refs = {
            "HEAD": head_rev,
            "refs/heads/" + branch: head_rev
        }

        def rev_parse(cwd, rev, *args, **kwargs):
            assert cwd == local_path

            if "--abbrev-ref" in kwargs.get("opts", []) and rev.endswith("@{upstream}"):
                return remote_name + "/" + rev.split("@")[0]

            rev = rev.split("^")[0]
            return remote_refs.get(rev) \
                or remote_refs.get("refs/heads/" + rev) \
                or rev

        def ls_remote(cwd, remote, opts, *args, **kwargs):
            assert cwd == local_path
            assert remote in [remote_name, fetch_url]

            if opts == "--tags":
                return tags
            raise NotImplementedError()

        def merge_base(cwd, refs, is_ancestor=False, **kwargs):
            assert cwd == local_path
            assert is_ancestor

            return all(ref == refs[0] for ref in refs)

        dunder_salt = {
            "git.config_get_regexp": MagicMock(return_value={}),
            "git.remote_refs": MagicMock(return_value=remote_refs),
            "git.version": MagicMock(return_value="1.8.3.1"),
            "git.list_branches": MagicMock(return_value=[branch]),
            "git.list_tags": MagicMock(return_value=tags),
            "git.revision": MagicMock(return_value=head_rev),
            "git.current_branch": MagicMock(return_value=branch),
            "git.remotes": MagicMock(return_value={
                remote_name: {
                    "fetch": fetch_url,
                },
            }),
            "git.diff": MagicMock(return_value=""),
            "git.rev_parse": MagicMock(side_effect=rev_parse),
            "git.ls_remote": MagicMock(side_effect=ls_remote),
            "git.fetch": MagicMock(return_value=True),
            "git.merge_base": MagicMock(side_effect=merge_base),
        }

        # Things that would interact with FS on test host
        isfile_mock = MagicMock(return_value=False)
        # expanduser reads home directory from system
        expanduser_mock = MagicMock(side_effect=NotImplementedError)
        isdir_mock = MagicMock(return_value=True)

        with patch.dict(git_state.__salt__, dunder_salt), \
                patch("os.path.isfile", isfile_mock), \
                patch("os.path.expanduser", expanduser_mock), \
                patch("os.path.isdir", isdir_mock):
            result = git_state.latest(
                fetch_url, rev=branch, remote=remote_name, target=local_path
            )
            assert result["result"] is True, result
            # Ensure the comment is formatted correctly. Namely that the repo
            # path is not mangled.
            self.assertIn(
                "Repository {repo} is up-to-date".format(repo=local_path),
                result["comment"],
            )
            self.assertIn(
                "{repo} was fetched, resulting in updated refs".format(repo=fetch_url),
                result["comment"],
            )
