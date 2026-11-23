"""
Unit tests for the file.line state

See https://github.com/saltstack/salt/issues/67987
"""

import pytest

import salt.states.file as filestate
from tests.support.mock import MagicMock, patch


@pytest.fixture
def configure_loader_modules():
    return {
        filestate: {
            "__env__": "base",
            "__salt__": {},
            "__opts__": {"test": False},
            "__instance_id__": "",
            "__low__": {},
            "__utils__": {},
        }
    }


@pytest.mark.parametrize("test_mode", [True, False])
def test_line_passes_test_mode_as_dry_run(tmp_path, test_mode):
    """
    The file.line execution module decides whether to write based on its own
    ``__opts__["test"]``, which is not changed for the test pass of a ``prereq``
    requisite. The state therefore has to pass its test mode as ``dry_run``.
    """
    name = str(tmp_path / "limits.conf")
    line_mock = MagicMock(return_value="--- diff ---")
    salt_mocks = {"file.line": line_mock}
    with patch.dict(filestate.__salt__, salt_mocks), patch.dict(
        filestate.__opts__, {"test": test_mode}
    ), patch.object(filestate, "managed", MagicMock(return_value={})), patch.object(
        filestate, "_check_file", MagicMock(return_value=(True, ""))
    ):
        ret = filestate.line(name, content="a line", mode="ensure", after="x")

    assert line_mock.call_args.kwargs["dry_run"] is test_mode
    assert ret["changes"] == {"diff": "--- diff ---"}
    assert ret["result"] is (None if test_mode else True)
