"""
Unit tests for the smbios module
"""

import pytest

import salt.modules.smbios as smbios

DMI_OUTPUT = (
    "Handle 0x0000, DMI type 0, 24 bytes\n"
    "BIOS Information\n"
    "\tVendor: ACME\n"
    "\tVersion: 1.0\n"
    "\tROM Size: 8 MB\n"
    "\n"
    "Handle 0x0001, DMI type 1, 27 bytes\n"
    "System Information\n"
    "\tManufacturer: ACME\n"
    "\tProduct Name: Rocket\n"
    "\tWake-up Type: Power Switch\n"
    "\n"
    "Handle 0x0002, DMI type 127, 4 bytes\n"
    "End Of Table\n"
)


@pytest.fixture
def configure_loader_modules():
    return {smbios: {}}


def _only_record(records):
    assert len(records) == 1
    return records[0]


def test_dmi_parse_returns_one_record_for_every_handle():
    records = smbios._dmi_parse(DMI_OUTPUT)
    assert [(r["handle"], r["type"], r["description"]) for r in records] == [
        ("0x0000", 0, "BIOS Information"),
        ("0x0001", 1, "System Information"),
    ]
    assert records[0]["data"] == {
        "vendor": "ACME",
        "version": "1.0",
        "rom_size": "8 MB",
    }
    assert records[1]["data"] == {
        "manufacturer": "ACME",
        "product_name": "Rocket",
        "wake-up_type": "Power Switch",
    }


def test_dmi_parse_keeps_records_without_data_when_not_clean():
    records = smbios._dmi_parse(DMI_OUTPUT, clean=False)
    assert [r["type"] for r in records] == [0, 1, 127]
    assert "data" not in records[2]


def test_dmi_parse_without_handles_returns_nothing():
    assert smbios._dmi_parse("no handles in this text\n") == []


def test_dmi_parse_keeps_the_last_field_of_a_record():
    """
    The last field of a record has no field after it that would save it.
    """
    data = "Handle 0x0000, DMI type 0, 24 bytes\nBIOS Information\n\tVendor: ACME\n"
    record = _only_record(smbios._dmi_parse(data))
    assert record["data"] == {"vendor": "ACME"}


def test_dmi_parse_keeps_a_list_as_the_last_field_of_a_record():
    data = (
        "Handle 0x0000, DMI type 0, 26 bytes\n"
        "BIOS Information\n"
        "\tVendor: Dell Inc.\n"
        "\tCharacteristics:\n"
        "\t\tPCI is supported\n"
        "\t\tBIOS is upgradeable\n"
        "\n"
    )
    record = _only_record(smbios._dmi_parse(data))
    assert record["data"] == {
        "vendor": "Dell Inc.",
        "characteristics": ["PCI is supported", "BIOS is upgradeable"],
    }


def test_dmi_parse_does_not_keep_a_last_field_that_is_not_wanted():
    data = (
        "Handle 0x0000, DMI type 0, 24 bytes\n"
        "BIOS Information\n"
        "\tVendor: ACME\n"
        "\tVersion: To be filled by O.E.M.\n"
    )
    record = _only_record(smbios._dmi_parse(data))
    assert record["data"] == {"vendor": "ACME"}
    record = _only_record(smbios._dmi_parse(data, fields=["vendor"]))
    assert record["data"] == {"vendor": "ACME"}
    record = _only_record(smbios._dmi_parse(data, fields=["version"], clean=False))
    assert record["data"] == {"version": "To be filled by O.E.M."}
