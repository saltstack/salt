"""
    Tests for xml module
"""


import os
import tempfile

import pytest

from salt.modules import xml


@pytest.fixture
def XML_STRING():
    return """
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


@pytest.fixture
def configure_loader_modules():
    return {xml: {}}


def test_get_value(XML_STRING):
    """
    Verify xml.get_value
    """
    with tempfile.NamedTemporaryFile("w+", delete=False) as xml_file:
        xml_file.write(XML_STRING)
        xml_file.flush()

    xml_result = xml.get_value(xml_file.name, ".//actor[@id='2']")
    assert xml_result == "Liam Neeson"

    os.remove(xml_file.name)


def test_set_value(XML_STRING):
    """
    Verify xml.set_value
    """
    with tempfile.NamedTemporaryFile("w+", delete=False) as xml_file:
        xml_file.write(XML_STRING)
        xml_file.flush()

    xml_result = xml.set_value(xml_file.name, ".//actor[@id='2']", "Patrick Stewart")
    assert xml_result is True

    xml_result = xml.get_value(xml_file.name, ".//actor[@id='2']")
    assert xml_result == "Patrick Stewart"

    os.remove(xml_file.name)


def test_get_attribute(XML_STRING):
    """
    Verify xml.get_attribute
    """
    with tempfile.NamedTemporaryFile("w+", delete=False) as xml_file:
        xml_file.write(XML_STRING)
        xml_file.flush()

    xml_result = xml.get_attribute(xml_file.name, ".//actor[@id='3']")
    assert xml_result == {"id": "3"}

    os.remove(xml_file.name)


def test_set_attribute(XML_STRING):
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
    assert xml_result == {"edited": "uh-huh", "id": "3"}

    os.remove(xml_file.name)
