"""
    :codeauthor: :email:`David Murphy <david-dm.murphy@broadcom.com`
"""

## import logging
import os
import tempfile

import pytest

import salt.utils.files
import salt.utils.path
from tests.support.mock import patch

pytestmark = [
    pytest.mark.skip_unless_on_linux(reason="Only supported on Linux family"),
]

## log = logging.getLogger(__name__)


def test_secure_boot_efivars():
    _salt_utils_files_fopen = salt.utils.files.fopen

    with tempfile.TemporaryDirectory() as tempdir:
        secure_boot_path = os.path.join(tempdir, "secure-boot/efivars")

        print(
            f"DGM test_secure_boot_efivars, secure_boot_path '{secure_boot_path}'",
            flush=True,
        )

        with _salt_utils_files_fopen(
            os.path.join(secure_boot_path, "/SecureBoot-dog", "wb+")
        ) as fd:
            binary_data = b"\x06\x00\x00\x00\x01"
            fd.write(binary_data)

    secure_boot_path_file = os.path.join(secure_boot_path, "/SecureBoot-dog")
    print(
        f"DGM test_secure_boot_efivars secure_boot_path file '{secure_boot_path_file}'",
        flush=True,
    )

    with patch("salt.grains.extra.get_secure_boot_path", return_value=secure_boot_path):
        grains = salt.grains.extra.uefi()

        print(f"DGM test_secure_boot_efivars grains '{grains}'", flush=True)

        expected = {"efi": True, "efi-secure-boot": True}
        assert grains == expected
