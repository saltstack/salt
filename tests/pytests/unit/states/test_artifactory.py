"""
    :codeauthor: Jayesh Kariya <jayeshk@saltstack.com>
"""

import pytest
import salt.states.artifactory as artifactory
from tests.support.mock import MagicMock, patch


@pytest.fixture
def configure_loader_modules():
    return {artifactory: {}}


def test_downloaded():
    """
    Test to ensures that the artifact from artifactory exists at
    given location.
    """
    name = "jboss"
    arti_url = "http://artifactory.intranet.example.com/artifactory"
    artifact = {
        "artifactory_url": arti_url,
        "artifact_id": "module",
        "repository": "libs-release-local",
        "packaging": "jar",
        "group_id": "com.company.module",
        "classifier": "sources",
        "version": "1.0",
    }

    ret = {"name": name, "result": False, "changes": {}, "comment": ""}

    mck = MagicMock(return_value={"status": False, "changes": {}, "comment": ""})
    with patch.dict(artifactory.__salt__, {"artifactory.get_release": mck}):
        assert artifactory.downloaded(name, artifact) == ret

    with patch.object(
        artifactory,
        "__fetch_from_artifactory",
        MagicMock(side_effect=Exception("error")),
    ):
        ret = artifactory.downloaded(name, artifact)
        assert ret["result"] is False
        assert ret["comment"] == "error"


def test_downloaded_test_true():
    """
    Test to ensures that the artifact from artifactory exists at
    given location.
    """
    name = "jboss"
    arti_url = "http://artifactory.intranet.example.com/artifactory"
    artifact = {
        "artifactory_url": arti_url,
        "artifact_id": "module",
        "repository": "libs-release-local",
        "packaging": "jar",
        "group_id": "com.company.module",
        "classifier": "sources",
        "version": "1.0",
    }

    ret = {
        "name": name,
        "result": True,
        "changes": {},
        "comment": (
            "Artifact would be downloaded from URL:"
            " http://artifactory.intranet.example.com/artifactory"
        ),
    }

    mck = MagicMock(return_value={"status": False, "changes": {}, "comment": ""})
    with patch.dict(artifactory.__salt__, {"artifactory.get_release": mck}):
        with patch.dict(artifactory.__opts__, {"test": True}):
            assert artifactory.downloaded(name, artifact) == ret

    with patch.object(
        artifactory,
        "__fetch_from_artifactory",
        MagicMock(side_effect=Exception("error")),
    ):
        ret = artifactory.downloaded(name, artifact)
        assert ret["result"] is False
        assert ret["comment"] == "error"
