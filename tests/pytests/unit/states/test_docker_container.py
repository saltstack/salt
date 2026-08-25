"""
Unit tests for the docker_container state module.
"""

import pytest

import salt.states.docker_container as docker_state
from tests.support.mock import MagicMock, patch


@pytest.fixture
def configure_loader_modules():
    return {
        docker_state: {
            "__opts__": {"test": False},
            "__context__": {},
        },
    }


def _running_state_salt(temp_container, *, current_image_id="img-original"):
    """
    Build a ``__salt__`` mapping sufficient to drive the ``running`` state
    through to the ``skip_comparison`` / force-replace branch where the
    pre-existing container is replaced by the temp container.
    """
    return {
        "docker.resolve_image_id": MagicMock(return_value="img-new"),
        "docker.inspect_container": MagicMock(return_value={"Image": current_image_id}),
        "docker.state": MagicMock(return_value="running"),
        "docker.create": MagicMock(return_value=temp_container),
        "docker.rm": MagicMock(return_value=["mycontainer"]),
        "docker.rename": MagicMock(return_value=True),
        "docker.start": MagicMock(return_value={"state": {"new": "running"}}),
        "docker.compare_container_networks": MagicMock(return_value={}),
        "config.option": MagicMock(return_value={}),
    }


def test_running_force_replace_passes_temp_container_name_to_rename():
    """
    Regression test for issue #68959: on the ``force=True`` /
    ``skip_comparison`` path of ``docker_container.running``, the local
    ``_replace(orig, new)`` helper must receive ``temp_container_name``
    (a string), not the dict returned by ``docker.create``.

    Prior to the fix, ``_replace`` was called with the dict, which was
    then forwarded as the first positional argument to ``docker.rename``.
    ``docker.rename`` calls ``inspect_container`` on that argument, so it
    raised on the dict -- after ``docker.rm`` had already removed the
    original container, leaving the minion with the original destroyed
    and the temp container stranded under its generated name.

    This test pins the contract by asserting ``docker.rename`` is called
    with a string container name, not a dict. It fails on the buggy code
    (the first positional arg is a dict) and passes after the fix.
    """
    temp_container = {"Name": "Salt_Temp_abc123", "Id": "deadbeef"}
    salt_mocks = _running_state_salt(temp_container)

    with patch.dict(docker_state.__dict__, {"__salt__": salt_mocks}):
        ret = docker_state.running(
            name="mycontainer",
            image="myimage",
            force=True,
        )

    # Sanity: we actually exercised the force-replace path.
    salt_mocks["docker.rm"].assert_called()
    salt_mocks["docker.rename"].assert_called_once()

    # The bug: docker.rename(new, orig). ``new`` must be a string
    # (``temp_container["Name"]``), not the dict returned by docker.create.
    call_args, _ = salt_mocks["docker.rename"].call_args
    assert call_args[0] == temp_container["Name"], (
        "docker.rename's first positional arg should be temp_container_name "
        f"(a string), got {call_args[0]!r}"
    )
    assert not isinstance(call_args[0], dict), (
        "docker.rename was called with a dict (the temp container struct) "
        "instead of the temp container name; this is the #68959 bug"
    )

    # And the second positional is the target name we asked to replace.
    assert call_args[1] == "mycontainer"

    assert ret["result"] is True
