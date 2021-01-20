import salt.utils.xmlutil as xmlutil
from salt._compat import ElementTree as ET


def append_to_XMLDesc(mocked, fragment):
    """
    Append an XML fragment at the end of the mocked XMLDesc return_value of mocked.
    """
    xml_doc = ET.fromstring(mocked.XMLDesc())
    xml_fragment = ET.fromstring(fragment)
    xml_doc.append(xml_fragment)
    mocked.XMLDesc.return_value = ET.tostring(xml_doc)


def assert_xml_equals(expected, actual):
    """
    Assert that two ElementTree nodes are equal
    """
    assert xmlutil.to_dict(xmlutil.strip_spaces(expected), True) == xmlutil.to_dict(
        xmlutil.strip_spaces(actual), True
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
