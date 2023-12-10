"""
Unit tests for the docker state
"""

import pytest

import salt.modules.dockermod as docker_mod
import salt.states.docker_volume as docker_state
from tests.support.mock import Mock, patch


@pytest.fixture
def configure_loader_modules():
    return {
        docker_mod: {"__context__": {"docker.docker_version": ""}},
        docker_state: {"__opts__": {"test": False}},
    }


def test_present():
    """
    Test docker_volume.present
    """
    volumes = []
    default_driver = "dummy_default"

    def create_volume(name, driver=None, driver_opts=None):
        for v in volumes:
            assert v["Name"] != name
        if driver is None:
            driver = default_driver
        new = {"Name": name, "Driver": driver}
        volumes.append(new)
        return new

    def remove_volume(name):
        removed = [v for v in volumes if v["Name"] == name]
        assert 1 == len(removed)
        volumes.remove(removed[0])
        return removed[0]

    docker_create_volume = Mock(side_effect=create_volume)
    __salt__ = {
        "docker.create_volume": docker_create_volume,
        "docker.volumes": Mock(return_value={"Volumes": volumes}),
        "docker.remove_volume": Mock(side_effect=remove_volume),
    }
    with patch.dict(docker_state.__dict__, {"__salt__": __salt__}):
        ret = docker_state.present("volume_foo")
        docker_create_volume.assert_called_with(
            "volume_foo", driver=None, driver_opts=None
        )
        assert ret == {
            "name": "volume_foo",
            "comment": "",
            "changes": {"created": {"Driver": default_driver, "Name": "volume_foo"}},
            "result": True,
        }
        assert len(volumes) == 1
        assert volumes[0]["Name"] == "volume_foo"
        assert volumes[0]["Driver"] is default_driver

        # run it again with the same arguments
        orig_volumes = [volumes[0].copy()]
        ret = docker_state.present("volume_foo")
        assert ret == {
            "name": "volume_foo",
            "comment": "Volume 'volume_foo' already exists.",
            "changes": {},
            "result": True,
        }
        assert orig_volumes == volumes

        # run it again with a different driver but don't force
        ret = docker_state.present("volume_foo", driver="local")
        assert ret == {
            "name": "volume_foo",
            "comment": (
                "Driver for existing volume 'volume_foo'"
                " ('dummy_default') does not match specified"
                " driver ('local') and force is False"
            ),
            "changes": {},
            "result": False,
        }
        assert orig_volumes == volumes

        # run it again with a different driver and force
        ret = docker_state.present("volume_foo", driver="local", force=True)
        assert ret == {
            "name": "volume_foo",
            "comment": "",
            "changes": {
                "removed": {"Driver": default_driver, "Name": "volume_foo"},
                "created": {"Driver": "local", "Name": "volume_foo"},
            },
            "result": True,
        }
        mod_orig_volumes = [orig_volumes[0].copy()]
        mod_orig_volumes[0]["Driver"] = "local"
        assert mod_orig_volumes == volumes


def test_present_with_another_driver():
    """
    Test docker_volume.present
    """
    docker_create_volume = Mock(return_value="created")
    docker_remove_volume = Mock(return_value="removed")
    __salt__ = {
        "docker.create_volume": docker_create_volume,
        "docker.remove_volume": docker_remove_volume,
        "docker.volumes": Mock(
            return_value={"Volumes": [{"Name": "volume_foo", "Driver": "foo"}]}
        ),
    }
    with patch.dict(docker_state.__dict__, {"__salt__": __salt__}):
        ret = docker_state.present(
            "volume_foo",
            driver="bar",
            force=True,
        )
    docker_remove_volume.assert_called_with("volume_foo")
    docker_create_volume.assert_called_with(
        "volume_foo", driver="bar", driver_opts=None
    )
    assert ret == {
        "name": "volume_foo",
        "comment": "",
        "changes": {"created": "created", "removed": "removed"},
        "result": True,
    }


def test_present_wo_existing_volumes():
    """
    Test docker_volume.present without existing volumes.
    """
    docker_create_volume = Mock(return_value="created")
    docker_remove_volume = Mock(return_value="removed")
    __salt__ = {
        "docker.create_volume": docker_create_volume,
        "docker.remove_volume": docker_remove_volume,
        "docker.volumes": Mock(return_value={"Volumes": None}),
    }
    with patch.dict(docker_state.__dict__, {"__salt__": __salt__}):
        ret = docker_state.present(
            "volume_foo",
            driver="bar",
            force=True,
        )
    docker_create_volume.assert_called_with(
        "volume_foo", driver="bar", driver_opts=None
    )
    assert ret == {
        "name": "volume_foo",
        "comment": "",
        "changes": {"created": "created"},
        "result": True,
    }


def test_absent():
    """
    Test docker_volume.absent
    """
    docker_remove_volume = Mock(return_value="removed")
    __salt__ = {
        "docker.remove_volume": docker_remove_volume,
        "docker.volumes": Mock(return_value={"Volumes": [{"Name": "volume_foo"}]}),
    }
    with patch.dict(docker_state.__dict__, {"__salt__": __salt__}):
        ret = docker_state.absent(
            "volume_foo",
        )
    docker_remove_volume.assert_called_with("volume_foo")
    assert ret == {
        "name": "volume_foo",
        "comment": "",
        "changes": {"removed": "removed"},
        "result": True,
    }
