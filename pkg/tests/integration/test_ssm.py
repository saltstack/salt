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
    ssm_path = os.path.join(*install_salt.binary_paths["ssm"])
    assert os.path.exists(ssm_path)
