"""
Unit tests for the docker state
"""

import pytest
import salt.modules.dockermod as docker_mod
import salt.states.docker_image as docker_state
from tests.support.mock import MagicMock, patch


@pytest.fixture
def configure_loader_modules():
    return {
        docker_mod: {"__context__": {"docker.docker_version": ""}},
        docker_state: {"__opts__": {"test": False}},
    }


def test_present_already_local():
    """
    According following sls,

    .. code-block:: yaml

        image:latest:
          docker_image.present:
            - force: true

    if ``image:latest`` is already downloaded locally the state
    should not report changes.
    """
    docker_inspect_image = MagicMock(return_value={"Id": "abcdefghijkl"})
    docker_pull = MagicMock(
        return_value={
            "Layers": {"Already_Pulled": ["abcdefghijkl"], "Pulled": []},
            "Status": "Image is up to date for image:latest",
            "Time_Elapsed": 1.1,
        }
    )
    docker_list_tags = MagicMock(return_value=["image:latest"])
    docker_resolve_tag = MagicMock(return_value="image:latest")
    __salt__ = {
        "docker.list_tags": docker_list_tags,
        "docker.pull": docker_pull,
        "docker.inspect_image": docker_inspect_image,
        "docker.resolve_tag": docker_resolve_tag,
    }
    with patch.dict(docker_state.__dict__, {"__salt__": __salt__}):
        ret = docker_state.present("image:latest", force=True)
        assert ret == {
            "changes": {},
            "result": True,
            "comment": "Image 'image:latest' was pulled, but there were no changes",
            "name": "image:latest",
        }


def test_present_and_force():
    """
    According following sls,

    .. code-block:: yaml

        image:latest:
          docker_image.present:
            - force: true

    if ``image:latest`` is not downloaded and force is true
    should pull a new image successfully.
    """
    docker_inspect_image = MagicMock(return_value={"Id": "1234567890ab"})
    docker_pull = MagicMock(
        return_value={
            "Layers": {"Pulled": ["abcdefghijkl"]},
            "Status": "Image 'image:latest' was pulled",
            "Time_Elapsed": 1.1,
        }
    )
    docker_list_tags = MagicMock(side_effect=[[], ["image:latest"]])
    docker_resolve_tag = MagicMock(return_value="image:latest")
    __salt__ = {
        "docker.list_tags": docker_list_tags,
        "docker.pull": docker_pull,
        "docker.inspect_image": docker_inspect_image,
        "docker.resolve_tag": docker_resolve_tag,
    }
    with patch.dict(docker_state.__dict__, {"__salt__": __salt__}):
        ret = docker_state.present("image:latest", force=True)
    assert ret == {
        "changes": {
            "Layers": {"Pulled": ["abcdefghijkl"]},
            "Status": "Image 'image:latest' was pulled",
            "Time_Elapsed": 1.1,
        },
        "result": True,
        "comment": "Image 'image:latest' was pulled",
        "name": "image:latest",
    }
