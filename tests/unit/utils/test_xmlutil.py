"""
    tests.unit.xmlutil_test
    ~~~~~~~~~~~~~~~~~~~~
"""
import xml.etree.ElementTree as ET

import salt.utils.xmlutil as xml
from tests.support.unit import TestCase


class XMLUtilTestCase(TestCase):
    """
    Tests that salt.utils.xmlutil properly parses XML data and returns as a properly formatted
    dictionary. The default method of parsing will ignore attributes and return only the child
    items. The full method will include parsing attributes.
    """

    def setUp(self):

        # Populate our use cases for specific XML formats.
        self.cases = {
            "a": {
                "xml": "<parent>data</parent>",
                "legacy": {"parent": "data"},
                "full": "data",
            },
            "b": {
                "xml": '<parent value="data">data</parent>',
                "legacy": {"parent": "data"},
                "full": {"parent": "data", "value": "data"},
            },
            "c": {
                "xml": (
                    '<parent><child>data</child><child value="data">data</child>'
                    '<child value="data"/><child/></parent>'
                ),
                "legacy": {
                    "child": [
                        "data",
                        {"child": "data"},
                        {"child": None},
                        {"child": None},
                    ]
                },
                "full": {
                    "child": [
                        "data",
                        {"child": "data", "value": "data"},
                        {"value": "data"},
                        None,
                    ]
                },
            },
            "d": {
                "xml": (
                    '<parent value="data" another="data"><child>data</child></parent>'
                ),
                "legacy": {"child": "data"},
                "full": {"child": "data", "another": "data", "value": "data"},
            },
            "e": {
                "xml": (
                    '<parent value="data" another="data"><child'
                    ' value="data">data</child></parent>'
                ),
                "legacy": {"child": "data"},
                "full": {
                    "child": {"child": "data", "value": "data"},
                    "another": "data",
                    "value": "data",
                },
            },
            "f": {
                "xml": (
                    '<parent><child><sub-child value="data">data</sub-child></child>'
                    "<child>data</child></parent>"
                ),
                "legacy": {"child": [{"sub-child": "data"}, {"child": "data"}]},
                "full": {
                    "child": [
                        {"sub-child": {"value": "data", "sub-child": "data"}},
                        "data",
                    ]
                },
            },
        }

    def test_xml_case_a(self):
        xmldata = ET.fromstring(self.cases["a"]["xml"])
        defaultdict = xml.to_dict(xmldata)
        self.assertEqual(defaultdict, self.cases["a"]["legacy"])

    def test_xml_case_a_legacy(self):
        xmldata = ET.fromstring(self.cases["a"]["xml"])
        defaultdict = xml.to_dict(xmldata, False)
        self.assertEqual(defaultdict, self.cases["a"]["legacy"])

    def test_xml_case_a_full(self):
        xmldata = ET.fromstring(self.cases["a"]["xml"])
        defaultdict = xml.to_dict(xmldata, True)
        self.assertEqual(defaultdict, self.cases["a"]["full"])

    def test_xml_case_b(self):
        xmldata = ET.fromstring(self.cases["b"]["xml"])
        defaultdict = xml.to_dict(xmldata)
        self.assertEqual(defaultdict, self.cases["b"]["legacy"])

    def test_xml_case_b_legacy(self):
        xmldata = ET.fromstring(self.cases["b"]["xml"])
        defaultdict = xml.to_dict(xmldata, False)
        self.assertEqual(defaultdict, self.cases["b"]["legacy"])

    def test_xml_case_b_full(self):
        xmldata = ET.fromstring(self.cases["b"]["xml"])
        defaultdict = xml.to_dict(xmldata, True)
        self.assertEqual(defaultdict, self.cases["b"]["full"])

    def test_xml_case_c(self):
        xmldata = ET.fromstring(self.cases["c"]["xml"])
        defaultdict = xml.to_dict(xmldata)
        self.assertEqual(defaultdict, self.cases["c"]["legacy"])

    def test_xml_case_c_legacy(self):
        xmldata = ET.fromstring(self.cases["c"]["xml"])
        defaultdict = xml.to_dict(xmldata, False)
        self.assertEqual(defaultdict, self.cases["c"]["legacy"])

    def test_xml_case_c_full(self):
        xmldata = ET.fromstring(self.cases["c"]["xml"])
        defaultdict = xml.to_dict(xmldata, True)
        self.assertEqual(defaultdict, self.cases["c"]["full"])

    def test_xml_case_d(self):
        xmldata = ET.fromstring(self.cases["d"]["xml"])
        defaultdict = xml.to_dict(xmldata)
        self.assertEqual(defaultdict, self.cases["d"]["legacy"])

    def test_xml_case_d_legacy(self):
        xmldata = ET.fromstring(self.cases["d"]["xml"])
        defaultdict = xml.to_dict(xmldata, False)
        self.assertEqual(defaultdict, self.cases["d"]["legacy"])

    def test_xml_case_d_full(self):
        xmldata = ET.fromstring(self.cases["d"]["xml"])
        defaultdict = xml.to_dict(xmldata, True)
        self.assertEqual(defaultdict, self.cases["d"]["full"])

    def test_xml_case_e(self):
        xmldata = ET.fromstring(self.cases["e"]["xml"])
        defaultdict = xml.to_dict(xmldata)
        self.assertEqual(defaultdict, self.cases["e"]["legacy"])

    def test_xml_case_e_legacy(self):
        xmldata = ET.fromstring(self.cases["e"]["xml"])
        defaultdict = xml.to_dict(xmldata, False)
        self.assertEqual(defaultdict, self.cases["e"]["legacy"])

    def test_xml_case_e_full(self):
        xmldata = ET.fromstring(self.cases["e"]["xml"])
        defaultdict = xml.to_dict(xmldata, True)
        self.assertEqual(defaultdict, self.cases["e"]["full"])

    def test_xml_case_f(self):
        xmldata = ET.fromstring(self.cases["f"]["xml"])
        defaultdict = xml.to_dict(xmldata)
        self.assertEqual(defaultdict, self.cases["f"]["legacy"])

    def test_xml_case_f_legacy(self):
        xmldata = ET.fromstring(self.cases["f"]["xml"])
        defaultdict = xml.to_dict(xmldata, False)
        self.assertEqual(defaultdict, self.cases["f"]["legacy"])

    def test_xml_case_f_full(self):
        xmldata = ET.fromstring(self.cases["f"]["xml"])
        defaultdict = xml.to_dict(xmldata, True)
        self.assertEqual(defaultdict, self.cases["f"]["full"])
