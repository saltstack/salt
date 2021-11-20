"""
Test ext_nodes master_tops module
"""


import subprocess
import textwrap

import salt.tops.ext_nodes as ext_nodes
import salt.utils.stringutils
from tests.support.mixins import LoaderModuleMockMixin
from tests.support.mock import MagicMock, patch
from tests.support.unit import TestCase


class ExtNodesTestCase(TestCase, LoaderModuleMockMixin):
    def setup_loader_modules(self):
        return {
            ext_nodes: {
                "__opts__": {
                    "master_tops": {
                        # Since ext_nodes runs the command with shell=True,
                        # this will keep "command not found" errors from
                        # showing up on the console. We'll be mocking the
                        # communicate results anyway.
                        "ext_nodes": "echo",
                    }
                }
            }
        }

    def test_ext_nodes(self):
        """
        Confirm that subprocess.Popen works as expected and does not raise an
        exception (see https://github.com/saltstack/salt/pull/46863).
        """
        stdout = salt.utils.stringutils.to_bytes(
            textwrap.dedent(
                """\
            classes:
              - one
              - two"""
            )
        )
        communicate_mock = MagicMock(return_value=(stdout, None))
        with patch.object(subprocess.Popen, "communicate", communicate_mock):
            ret = ext_nodes.top(opts={"id": "foo"})
        self.assertEqual(ret, {"base": ["one", "two"]})

    def test_ext_nodes_with_environment(self):
        """
        Same as above, but also tests that the matches are assigned to the proper
        environment if one is returned by the ext_nodes command.
        """
        stdout = salt.utils.stringutils.to_bytes(
            textwrap.dedent(
                """\
            classes:
              - one
              - two
            environment: dev"""
            )
        )
        communicate_mock = MagicMock(return_value=(stdout, None))
        with patch.object(subprocess.Popen, "communicate", communicate_mock):
            ret = ext_nodes.top(opts={"id": "foo"})
        self.assertEqual(ret, {"dev": ["one", "two"]})
