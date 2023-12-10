"""
    :codeauthor: :email:`Jayesh Kariya <jayeshk@saltstack.com>`
"""

import pytest

import salt.states.nexus as nexus
from tests.support.mock import MagicMock, patch


@pytest.fixture
def configure_loader_modules():
    return {nexus: {}}


def test_downloaded():
    """
    Test to ensures that the artifact from nexus exists at
    given location.
    """
    name = "jboss"
    arti_url = "http://nexus.example.com/repository"
    artifact = {
        "nexus_url": arti_url,
        "artifact_id": "module",
        "repository": "libs-releases",
        "packaging": "jar",
        "group_id": "com.company.module",
        "classifier": "sources",
        "version": "1.0",
    }

    ret = {"name": name, "result": False, "changes": {}, "comment": ""}

    mck = MagicMock(return_value={"status": False, "changes": {}, "comment": ""})
    with patch.dict(nexus.__salt__, {"nexus.get_release": mck}):
        assert nexus.downloaded(name, artifact) == ret

    with patch.object(
        nexus, "__fetch_from_nexus", MagicMock(side_effect=Exception("error"))
    ):
        ret = nexus.downloaded(name, artifact)
        assert ret["result"] is False
        assert ret["comment"] == "error"
