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
