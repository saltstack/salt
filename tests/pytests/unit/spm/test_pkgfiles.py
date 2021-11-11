import os
import pathlib

import pytest
import salt.spm.pkgfiles.local as spm
import salt.syspaths
from tests.support.mock import MagicMock


@pytest.fixture()
def configure_loader_modules():
    return {spm: {"__opts__": {"spm_node_type": "master"}}}


class MockTar:
    def __init__(self):
        self.name = str(pathlib.Path("apache", "_README"))
        self.path = str(
            pathlib.Path(os.sep, salt.syspaths.CACHE_DIR, "master", "extmods")
        )


def test_install_file():
    """
    test spm.pkgfiles.local
    """
    assert (
        spm.install_file(
            "apache",
            formula_tar=MagicMock(),
            member=MockTar(),
            formula_def={"name": "apache"},
            conn={"formula_path": "/tmp/test"},
        )
        == MockTar().path
    )
