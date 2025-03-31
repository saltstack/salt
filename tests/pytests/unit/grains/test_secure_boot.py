"""
    :codeauthor: :email:`David Murphy <david-dm.murphy@broadcom.com`
"""

import shutil

import pytest

import salt.grains.extra
from tests.support.mock import patch

pytestmark = [
    pytest.mark.skip_unless_on_linux(reason="Only supported on Linux family"),
]


@pytest.mark.parametrize(
    "setting_secure, extra_file, expected_enabled",
    (
        (True, False, True),
        (True, True, False),
        (False, False, False),
        (False, True, False),
    ),
)
def test_secure_boot_efivars(tmp_path, setting_secure, extra_file, expected_enabled):
    secure_boot_path = tmp_path / "secure-boot"
    secure_boot_path_vars = secure_boot_path / "efivars"
    secure_boot_path_vars.mkdir(parents=True, exist_ok=True)
    secure_boot_filepath = secure_boot_path_vars / "SecureBoot-dog"

    if setting_secure:
        secure_boot_filepath.write_bytes(b"\x06\x00\x00\x00\x01")
    else:
        secure_boot_filepath.write_bytes(b"\x06\x00\x00\x00\x00")

    if extra_file:
        secure_boot_filepath2 = secure_boot_path_vars / "SecureBoot-kat"
        if setting_secure:
            secure_boot_filepath2.write_bytes(b"\x06\x00\x00\x00\x01")
        else:
            secure_boot_filepath2.write_bytes(b"\x06\x00\x00\x00\x00")

    with patch(
        "salt.grains.extra.get_secure_boot_path", return_value=secure_boot_path_vars
    ):
        grains = salt.grains.extra.uefi()
        expected = {"efi": True, "efi-secure-boot": expected_enabled}
        assert grains == expected

    shutil.rmtree(secure_boot_path)


@pytest.mark.parametrize(
    "setting_secure, extra_file, expected_enabled",
    (
        (True, False, True),
        (True, True, False),
        (False, False, False),
        (False, True, False),
    ),
)
def test_secure_boot_vars(tmp_path, setting_secure, extra_file, expected_enabled):
    secure_boot_path = tmp_path / "secure-boot"
    secure_boot_path_vars = secure_boot_path / "vars" / "SecureBoot-dog"
    secure_boot_path_vars1 = secure_boot_path_vars / "SecureBoot-dog"
    secure_boot_path_vars1.mkdir(parents=True, exist_ok=True)
    secure_boot_filepath = secure_boot_path_vars1 / "data"

    if setting_secure:
        secure_boot_filepath.write_bytes(b"\x06\x00\x00\x00\x01")
    else:
        secure_boot_filepath.write_bytes(b"\x06\x00\x00\x00\x00")

    if extra_file:
        secure_boot_path_vars2 = secure_boot_path_vars / "SecureBoot-kat"
        secure_boot_path_vars2.mkdir(parents=True, exist_ok=True)
        secure_boot_filepath2 = secure_boot_path_vars2 / "data"
        if setting_secure:
            secure_boot_filepath2.write_bytes(b"\x06\x00\x00\x00\x01")
        else:
            secure_boot_filepath2.write_bytes(b"\x06\x00\x00\x00\x00")

    with patch(
        "salt.grains.extra.get_secure_boot_path", return_value=secure_boot_path_vars
    ):
        grains = salt.grains.extra.uefi()
        expected = {"efi": True, "efi-secure-boot": expected_enabled}
        assert grains == expected

    shutil.rmtree(secure_boot_path)


@pytest.mark.parametrize(
    "setting_secure, expected_enabled",
    (
        (True, True),
        (False, False),
        (False, False),
        (False, False),
    ),
)
def test_secure_boot_efivars_and_vars(tmp_path, setting_secure, expected_enabled):
    secure_boot_path = tmp_path / "secure-boot"
    secure_boot_path_vars = secure_boot_path / "efivars"
    secure_boot_path_vars.mkdir(parents=True, exist_ok=True)
    secure_boot_filepath = secure_boot_path_vars / "SecureBoot-dog"

    secure_boot_path_vars2 = secure_boot_path / "vars" / "SecureBoot-kat"
    secure_boot_path_vars2.mkdir(parents=True, exist_ok=True)
    secure_boot_filepath2 = secure_boot_path_vars2 / "data"

    if setting_secure:
        # efivars True, vars / data False
        secure_boot_filepath.write_bytes(b"\x06\x00\x00\x00\x01")
        secure_boot_filepath2.write_bytes(b"\x06\x00\x00\x00\x00")
    else:
        # efivars false, vars / data True
        secure_boot_filepath.write_bytes(b"\x06\x00\x00\x00\x00")
        secure_boot_filepath2.write_bytes(b"\x06\x00\x00\x00\x01")

    with patch(
        "salt.grains.extra.get_secure_boot_path", return_value=secure_boot_path_vars
    ):
        grains = salt.grains.extra.uefi()
        expected = {"efi": True, "efi-secure-boot": expected_enabled}
        assert grains == expected

    shutil.rmtree(secure_boot_path)
