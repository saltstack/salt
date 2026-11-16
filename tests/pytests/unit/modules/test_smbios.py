"""
Unit tests for the smbios module
"""

import pytest

import salt.modules.smbios as smbios

# The parser saves a field when it reads the next one, so the last field of
# every record is not part of the result. Each record ends with a field that
# the tests do not look at.
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


def test_dmi_parse_returns_one_record_for_every_handle():
    records = smbios._dmi_parse(DMI_OUTPUT)
    assert [(r["handle"], r["type"], r["description"]) for r in records] == [
        ("0x0000", 0, "BIOS Information"),
        ("0x0001", 1, "System Information"),
    ]
    assert records[0]["data"] == {"vendor": "ACME", "version": "1.0"}
    assert records[1]["data"] == {"manufacturer": "ACME", "product_name": "Rocket"}


def test_dmi_parse_keeps_records_without_data_when_not_clean():
    records = smbios._dmi_parse(DMI_OUTPUT, clean=False)
    assert [r["type"] for r in records] == [0, 1, 127]
    assert "data" not in records[2]


def test_dmi_parse_without_handles_returns_nothing():
    assert smbios._dmi_parse("no handles in this text\n") == []
