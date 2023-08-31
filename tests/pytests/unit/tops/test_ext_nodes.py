"""
Test ext_nodes master_tops module
"""

import subprocess
import textwrap

import pytest

import salt.tops.ext_nodes as ext_nodes
import salt.utils.stringutils
from tests.support.mock import MagicMock, patch


@pytest.fixture
def configure_loader_modules():
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


def test_ext_nodes():
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
    run_mock = MagicMock()
    run_mock.return_value.stdout = stdout
    with patch.object(subprocess, "run", run_mock):
        ret = ext_nodes.top(opts={"id": "foo"})
    assert ret == {"base": ["one", "two"]}
    run_mock.assert_called_once_with(["echo", "foo"], check=True, stdout=-1)


def test_ext_nodes_with_environment():
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
    run_mock = MagicMock()
    run_mock.return_value.stdout = stdout
    with patch.object(subprocess, "run", run_mock):
        ret = ext_nodes.top(opts={"id": "foo"})
    assert ret == {"dev": ["one", "two"]}
    run_mock.assert_called_once_with(["echo", "foo"], check=True, stdout=-1)
