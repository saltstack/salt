# -*- coding: utf-8 -*-
"""
    Tests for xml module
"""

from __future__ import absolute_import, print_function, unicode_literals

import os
import tempfile

from salt.modules import xml
from tests.support.mixins import LoaderModuleMockMixin
from tests.support.unit import TestCase

XML_STRING = """
    <root xmlns:foo="http://www.foo.org/" xmlns:bar="http://www.bar.org">
        <actors>
            <actor id="1">Christian Bale</actor>
            <actor id="2">Liam Neeson</actor>
            <actor id="3">Michael Caine</actor>
        </actors>
        <foo:singers>
            <foo:singer id="4">Tom Waits</foo:singer>
            <foo:singer id="5">B.B. King</foo:singer>
            <foo:singer id="6">Ray Charles</foo:singer>
        </foo:singers>
    </root>
    """


class XmlTestCase(TestCase, LoaderModuleMockMixin):
    """
        Test cases for salt.modules.xml
    """

    def setup_loader_modules(self):
        return {xml: {}}

    def test_get_value(self):
        """
            Verify xml.get_value
        """
        with tempfile.NamedTemporaryFile("w+", delete=False) as xml_file:
            xml_file.write(XML_STRING)
            xml_file.flush()

        xml_result = xml.get_value(xml_file.name, ".//actor[@id='2']")
        self.assertEqual(xml_result, "Liam Neeson")

        os.remove(xml_file.name)

    def test_set_value(self):
        """
            Verify xml.set_value
        """
        with tempfile.NamedTemporaryFile("w+", delete=False) as xml_file:
            xml_file.write(XML_STRING)
            xml_file.flush()

        xml_result = xml.set_value(
            xml_file.name, ".//actor[@id='2']", "Patrick Stewart"
        )
        assert xml_result is True

        xml_result = xml.get_value(xml_file.name, ".//actor[@id='2']")
        self.assertEqual(xml_result, "Patrick Stewart")

        os.remove(xml_file.name)

    def test_get_attribute(self):
        """
            Verify xml.get_attribute
        """
        with tempfile.NamedTemporaryFile("w+", delete=False) as xml_file:
            xml_file.write(XML_STRING)
            xml_file.flush()

        xml_result = xml.get_attribute(xml_file.name, ".//actor[@id='3']")
        self.assertEqual(xml_result, {"id": "3"})

        os.remove(xml_file.name)

    def test_set_attribute(self):
        """
            Verify xml.set_value
        """
        with tempfile.NamedTemporaryFile("w+", delete=False) as xml_file:
            xml_file.write(XML_STRING)
            xml_file.flush()

        xml_result = xml.set_attribute(
            xml_file.name, ".//actor[@id='3']", "edited", "uh-huh"
        )
        assert xml_result is True

        xml_result = xml.get_attribute(xml_file.name, ".//actor[@id='3']")
        self.assertEqual(xml_result, {"edited": "uh-huh", "id": "3"})

        os.remove(xml_file.name)
