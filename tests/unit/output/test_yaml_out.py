"""
unittests for yaml outputter
"""


import salt.output.yaml_out as yaml
from tests.support.mixins import LoaderModuleMockMixin
from tests.support.mock import patch
from tests.support.unit import TestCase


class YamlTestCase(TestCase, LoaderModuleMockMixin):
    """
    Test cases for salt.output.json_out
    """

    def setup_loader_modules(self):
        return {yaml: {}}

    def setUp(self):
        self.data = {"test": "two", "example": "one"}
        self.addCleanup(delattr, self, "data")

    def test_default_output(self):
        ret = yaml.output(self.data)
        expect = "example: one\ntest: two\n"
        self.assertEqual(expect, ret)

    def test_negative_int_output(self):
        with patch.dict(yaml.__opts__, {"output_indent": -1}):
            ret = yaml.output(self.data)
            expect = "{example: one, test: two}\n"
            self.assertEqual(expect, ret)
