import tempfile

import pytest


@pytest.fixture(scope="module")
def minion_config_overrides():
    with tempfile.TemporaryDirectory() as tempdir:
        yield {
            "mydude": {
                "driver": "sqlite3",
                "database": tempdir + "/test_sdb.sq3",
                "table": __name__,
                "create_table": True,
            }
        }


@pytest.mark.skip("GREAT MODULE MIGRATION")
@pytest.mark.parametrize(
    "expected_value",
    (
        "foo",
        b"bang",
        ["cool", b"guy", "dude", b"\x00\x31\x99\x42"],
        {
            "this": b"has some",
            b"complicated": "things",
            "all": [{"going": "on"}, {"but": "that", 42: "should be fine"}],
        },
    ),
)
def test_setting_sdb_values_with_text_and_bytes_should_retain_data_types(
    expected_value, modules
):
    modules.sdb.set("sdb://mydude/fnord", expected_value)
    actual_value = modules.sdb.get("sdb://mydude/fnord", strict=True)
    assert actual_value == expected_value
