"""
unittests for table outputter
"""

from collections import OrderedDict

import pytest

import salt.output.table_out as table_out
import salt.utils.stringutils


@pytest.fixture
def configure_loader_modules():
    return {table_out: {}}


# The test data should include unicode chars, and in Python 2 there should
# be an example both of an encoded str type and an actual unicode type.
# Since unicode_literals is imported, we will achieve the former using
# salt.utils.stringutils.to_str and the latter by simply using a string
# literal.
@pytest.fixture
def data():
    return [
        {
            "Food": salt.utils.stringutils.to_str("яйца, бекон, колбаса и спам"),
            "Price": 5.99,
        },
        {"Food": "спам, спам, спам, яйца и спам", "Price": 3.99},
    ]


def test_output(data):
    ret = table_out.output(data)
    assert ret == (
        "    -----------------------------------------\n"
        "    |              Food             | Price |\n"
        "    -----------------------------------------\n"
        "    |  яйца, бекон, колбаса и спам  |  5.99 |\n"
        "    -----------------------------------------\n"
        "    | спам, спам, спам, яйца и спам |  3.99 |\n"
        "    -----------------------------------------"
    )


@pytest.mark.parametrize(
    "rows",
    [
        [{"Food": "spam", "Price": 1}, {"Food": "eggs", "Price": 2}],
        [{"Food": "spam"}],
        ["spam", "eggs"],
    ],
    ids=["dicts", "one-row", "strings"],
)
def test_display_rows_with_rows_of_one_type(rows):
    assert table_out.TableDisplay().display_rows(rows, None, 4)


@pytest.mark.parametrize(
    "rows",
    [
        [{"Food": "spam"}, ["eggs"]],
        ["spam", 3],
        # A dict and an OrderedDict are not the same type
        [{"Food": "spam"}, OrderedDict([("Food", "eggs")])],
    ],
    ids=["dict-and-list", "str-and-int", "dict-and-ordereddict"],
)
def test_display_rows_with_rows_of_different_types_outputs_nothing(rows):
    assert table_out.TableDisplay().display_rows(rows, None, 4) == []


def test_display_rows_without_rows_outputs_nothing():
    assert table_out.TableDisplay().display_rows([], None, 4) == []
