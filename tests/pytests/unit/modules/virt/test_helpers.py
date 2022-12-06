import xml.etree.ElementTree as ET

import salt.utils.xmlutil as xmlutil


def append_to_XMLDesc(mocked, fragment):
    """
    Append an XML fragment at the end of the mocked XMLDesc return_value of mocked.
    """
    xml_doc = ET.fromstring(mocked.XMLDesc())
    xml_fragment = ET.fromstring(fragment)
    xml_doc.append(xml_fragment)
    mocked.XMLDesc.return_value = ET.tostring(xml_doc)


def assert_xml_equals(actual, expected):
    """
    Assert that two ElementTree nodes are equal
    """
    assert xmlutil.to_dict(xmlutil.strip_spaces(actual), True) == xmlutil.to_dict(
        xmlutil.strip_spaces(expected), True
    )


def strip_xml(xml_str):
    """
    Remove all spaces and formatting from an XML string
    """
    return ET.tostring(xmlutil.strip_spaces(ET.fromstring(xml_str)))


def assert_called(mock, condition):
    """
    Assert that the mock has been called if not in test mode, and vice-versa.
    I know it's a simple XOR, but makes the tests easier to read
    """
    assert not condition and not mock.called or condition and mock.called


def assert_equal_unit(actual, expected, unit="KiB"):
    """
    Assert that two ElementTree nodes have the same value and unit
    """
    assert actual.get("unit") == unit
    assert actual.text == str(expected)
