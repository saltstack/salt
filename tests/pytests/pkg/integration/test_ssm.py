import os

import pytest

pytestmark = [
    pytest.mark.skip_unless_on_windows,
]


def test_ssm_present(install_salt):
    """
    The ssm.exe binary needs to be present in both the zip and the exe/msi
    builds
    """
    assert os.path.exists(install_salt.ssm_bin)
