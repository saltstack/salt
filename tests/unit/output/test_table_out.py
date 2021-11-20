"""
unittests for table outputter
"""


import salt.output.table_out as table_out
import salt.utils.stringutils
from tests.support.mixins import LoaderModuleMockMixin
from tests.support.unit import TestCase


class TableTestCase(TestCase, LoaderModuleMockMixin):
    """
    Test cases for salt.output.table_out
    """

    def setup_loader_modules(self):
        return {table_out: {}}

    # The test data should include unicode chars, and in Python 2 there should
    # be an example both of an encoded str type and an actual unicode type.
    # Since unicode_literals is imported, we will achieve the former using
    # salt.utils.stringutils.to_str and the latter by simply using a string
    # literal.
    data = [
        {
            "Food": salt.utils.stringutils.to_str("яйца, бекон, колбаса и спам"),
            "Price": 5.99,
        },
        {"Food": "спам, спам, спам, яйца и спам", "Price": 3.99},
    ]

    def test_output(self):
        ret = table_out.output(self.data)
        self.assertEqual(
            ret,
            "    -----------------------------------------\n"
            "    |              Food             | Price |\n"
            "    -----------------------------------------\n"
            "    |  яйца, бекон, колбаса и спам  |  5.99 |\n"
            "    -----------------------------------------\n"
            "    | спам, спам, спам, яйца и спам |  3.99 |\n"
            "    -----------------------------------------",
        )
