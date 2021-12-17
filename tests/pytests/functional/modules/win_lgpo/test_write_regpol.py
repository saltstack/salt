import pytest
import salt.modules.win_file
import salt.modules.win_lgpo as win_lgpo
import salt.utils.files

pytestmark = [
    pytest.mark.windows_whitelisted,
    pytest.mark.skip_unless_on_windows,
]


@pytest.fixture
def configure_loader_modules():
    return {win_lgpo: {"__salt__": {"file.makedirs": salt.modules.win_file.makedirs_}}}


def test_issue_56769_windows_line_endings():
    """
    Test that it handles a gpt.ini file with Windows-style line endings.
    Should create a gpt.ini with Windows-style line endings.
    """

    data_to_write = b"[\x00d\x00u\x00m\x00m\x00y\x00\\\x00d\x00a\x00t\x00a]\x00"
    gpt_extension = "gPCMachineExtensionNames"
    gpt_extension_guid = (
        "[{35378EAC-683F-11D2-A89A-00C04FBBCFA2}{D02B1F72-3407-48AE-BA88-E8213C6761F1}]"
    )

    gpt_ini = "\r\n".join(["[General]", "gPCMachineExtensionNames=", "Version=8", ""])
    expected = "\r\n".join(
        [
            "[General]",
            "gPCMachineExtensionNames=[{35378EAC-683F-11D2-A89A-00C04FBBCFA2}{D02B1F72-3407-48AE-BA88-E8213C6761F1}]",
            "Version=9",
            "",
        ]
    )

    with pytest.helpers.temp_file(
        "Registry.pol"
    ) as reg_pol_file, pytest.helpers.temp_file("gpt.ini") as gpt_ini_file:
        # We're using salt.utils.file.fopen here because the temp_file helper
        # doesn't preserve line endings when writing the test file
        with salt.utils.files.fopen(str(gpt_ini_file), "w") as fp:
            fp.write(gpt_ini)
        win_lgpo._write_regpol_data(
            data_to_write=data_to_write,
            policy_file_path=str(reg_pol_file),
            gpt_ini_path=str(gpt_ini_file),
            gpt_extension=gpt_extension,
            gpt_extension_guid=gpt_extension_guid,
        )
        # We're using salt.utils.file.fopen here because the temp_file helper
        # doesn't preserve line endings when reading the test file
        with salt.utils.files.fopen(str(gpt_ini_file)) as fp:
            result = fp.read()

        assert result == expected


def test_issue_56769_unix_line_endings():
    """
    Test that it handles a gpt.ini file with Unix-style line endings.
    Should create a gpt.ini with Windows-style line endings.
    """

    data_to_write = b"[\x00d\x00u\x00m\x00m\x00y\x00\\\x00d\x00a\x00t\x00a]\x00"
    gpt_extension = "gPCMachineExtensionNames"
    gpt_extension_guid = (
        "[{35378EAC-683F-11D2-A89A-00C04FBBCFA2}{D02B1F72-3407-48AE-BA88-E8213C6761F1}]"
    )

    gpt_ini = "\n".join(["[General]", "gPCMachineExtensionNames=", "Version=8", ""])
    expected = "\r\n".join(
        [
            "[General]",
            "gPCMachineExtensionNames=[{35378EAC-683F-11D2-A89A-00C04FBBCFA2}{D02B1F72-3407-48AE-BA88-E8213C6761F1}]",
            "Version=9",
            "",
        ]
    )

    with pytest.helpers.temp_file(
        "Registry.pol"
    ) as reg_pol_file, pytest.helpers.temp_file("gpt.ini") as gpt_ini_file:
        # We're using salt.utils.file.fopen here because the temp_file helper
        # doesn't preserve line endings when writing the test file
        with salt.utils.files.fopen(str(gpt_ini_file), "w") as fp:
            fp.write(gpt_ini)
        win_lgpo._write_regpol_data(
            data_to_write=data_to_write,
            policy_file_path=str(reg_pol_file),
            gpt_ini_path=str(gpt_ini_file),
            gpt_extension=gpt_extension,
            gpt_extension_guid=gpt_extension_guid,
        )
        # We're using salt.utils.file.fopen here because the temp_file helper
        # doesn't preserve line endings when reading the test file
        with salt.utils.files.fopen(str(gpt_ini_file)) as fp:
            result = fp.read()

        assert result == expected


def test_issue_56769_mixed_line_endings():
    """
    Test that it handles a gpt.ini file with mixed line endings.
    Should create a gpt.ini with Windows-style line endings.
    """

    data_to_write = b"[\x00d\x00u\x00m\x00m\x00y\x00\\\x00d\x00a\x00t\x00a]\x00"
    gpt_extension = "gPCMachineExtensionNames"
    gpt_extension_guid = (
        "[{35378EAC-683F-11D2-A89A-00C04FBBCFA2}{D02B1F72-3407-48AE-BA88-E8213C6761F1}]"
    )

    gpt_ini = "[General]\ngPCMachineExtensionNames=\r\nVersion=8\n"
    expected = "\r\n".join(
        [
            "[General]",
            "gPCMachineExtensionNames=[{35378EAC-683F-11D2-A89A-00C04FBBCFA2}{D02B1F72-3407-48AE-BA88-E8213C6761F1}]",
            "Version=9",
            "",
        ]
    )

    with pytest.helpers.temp_file(
        "Registry.pol"
    ) as reg_pol_file, pytest.helpers.temp_file("gpt.ini") as gpt_ini_file:
        # We're using salt.utils.file.fopen here because the temp_file helper
        # doesn't preserve line endings when writing the test file
        with salt.utils.files.fopen(str(gpt_ini_file), "w") as fp:
            fp.write(gpt_ini)
        win_lgpo._write_regpol_data(
            data_to_write=data_to_write,
            policy_file_path=str(reg_pol_file),
            gpt_ini_path=str(gpt_ini_file),
            gpt_extension=gpt_extension,
            gpt_extension_guid=gpt_extension_guid,
        )
        # We're using salt.utils.file.fopen here because the temp_file helper
        # doesn't preserve line endings when reading the test file
        with salt.utils.files.fopen(str(gpt_ini_file)) as fp:
            result = fp.read()

        assert result == expected
