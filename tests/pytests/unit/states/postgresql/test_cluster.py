"""
    :codeauthor: Logilab <contact@logilab.fr>
"""

import pytest

import salt.states.postgres_cluster as postgres_cluster
from tests.support.mock import MagicMock, patch


@pytest.fixture
def configure_loader_modules():
    return {postgres_cluster: {}}


def test_present():
    """
    Test to ensure that the named database is present
    with the specified properties.
    """
    name = "main"
    version = "9.4"

    ret = {"name": name, "changes": {}, "result": False, "comment": ""}

    mock_t = MagicMock(return_value=True)
    mock_f = MagicMock(return_value=False)
    infos = {f"{version}/{name}": {}}
    mock = MagicMock(return_value=infos)
    with patch.dict(
        postgres_cluster.__salt__,
        {
            "postgres.cluster_list": mock,
            "postgres.cluster_exists": mock_t,
            "postgres.cluster_create": mock_t,
        },
    ):
        comt = f"Cluster {version}/{name} is already present"
        ret.update({"comment": comt, "result": True})
        assert postgres_cluster.present(version, name) == ret
        infos[f"{version}/{name}"]["port"] = 5433
        comt = (
            "Cluster {}/{} has wrong parameters "
            "which couldn't be changed on fly.".format(version, name)
        )
        ret.update({"comment": comt, "result": False})
        assert postgres_cluster.present(version, name, port=5434) == ret
        infos[f"{version}/{name}"]["datadir"] = "/tmp/"
        comt = (
            "Cluster {}/{} has wrong parameters "
            "which couldn't be changed on fly.".format(version, name)
        )
        ret.update({"comment": comt, "result": False})
        assert postgres_cluster.present(version, name, port=5434) == ret

    with patch.dict(
        postgres_cluster.__salt__,
        {
            "postgres.cluster_list": mock,
            "postgres.cluster_exists": mock_f,
            "postgres.cluster_create": mock_t,
        },
    ):
        comt = f"The cluster {version}/{name} has been created"
        ret.update(
            {
                "comment": comt,
                "result": True,
                "changes": {f"{version}/{name}": "Present"},
            }
        )
        assert postgres_cluster.present(version, name) == ret
        with patch.dict(postgres_cluster.__opts__, {"test": True}):
            comt = f"Cluster {version}/{name} is set to be created"
            ret.update({"comment": comt, "result": None, "changes": {}})
            assert postgres_cluster.present(version, name) == ret

    with patch.dict(
        postgres_cluster.__salt__,
        {
            "postgres.cluster_list": mock,
            "postgres.cluster_exists": mock_f,
            "postgres.cluster_create": mock_f,
        },
    ):
        comt = f"Failed to create cluster {version}/{name}"
        ret.update({"comment": comt, "result": False})
        assert postgres_cluster.present(version, name) == ret


def test_absent():
    """
    Test to ensure that the named database is absent.
    """
    name = "main"
    version = "9.4"

    ret = {"name": name, "changes": {}, "result": False, "comment": ""}

    mock_t = MagicMock(return_value=True)
    mock = MagicMock(side_effect=[True, True, False])
    with patch.dict(
        postgres_cluster.__salt__,
        {"postgres.cluster_exists": mock, "postgres.cluster_remove": mock_t},
    ):
        with patch.dict(postgres_cluster.__opts__, {"test": True}):
            comt = f"Cluster {version}/{name} is set to be removed"
            ret.update({"comment": comt, "result": None})
            assert postgres_cluster.absent(version, name) == ret

        with patch.dict(postgres_cluster.__opts__, {"test": False}):
            comt = f"Cluster {version}/{name} has been removed"
            ret.update({"comment": comt, "result": True, "changes": {name: "Absent"}})
            assert postgres_cluster.absent(version, name) == ret

            comt = "Cluster {}/{} is not present, so it cannot be removed".format(
                version, name
            )
            ret.update({"comment": comt, "result": True, "changes": {}})
            assert postgres_cluster.absent(version, name) == ret
