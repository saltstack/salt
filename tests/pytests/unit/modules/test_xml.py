"""
    Tests for xml module
"""

import pytest

from salt.modules import xml


@pytest.fixture
def xml_string():
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


def test_get_value(xml_string, tmp_path):
    """
    Verify xml.get_value
    """
    xml_file = tmp_path / "test_xml.xml"
    xml_file.write_text(xml_string)
    xml_result = xml.get_value(str(xml_file), ".//actor[@id='2']")
    assert xml_result == "Liam Neeson"


def test_set_value(xml_string, tmp_path):
    """
    Verify xml.set_value
    """
    xml_file = tmp_path / "test_xml.xml"
    xml_file.write_text(xml_string)
    xml_result = xml.set_value(str(xml_file), ".//actor[@id='2']", "Patrick Stewart")
    assert xml_result is True
    xml_result = xml.get_value(str(xml_file), ".//actor[@id='2']")
    assert xml_result == "Patrick Stewart"


def test_get_attribute(xml_string, tmp_path):
    """
    Verify xml.get_attribute
    """
    xml_file = tmp_path / "test_xml.xml"
    xml_file.write_text(xml_string)
    xml_result = xml.get_attribute(str(xml_file), ".//actor[@id='3']")
    assert xml_result == {"id": "3"}


def test_set_attribute(xml_string, tmp_path):
    """
    Verify xml.set_value
    """
    xml_file = tmp_path / "test_xml.xml"
    xml_file.write_text(xml_string)
    xml_result = xml.set_attribute(
        str(xml_file), ".//actor[@id='3']", "edited", "uh-huh"
    )
    assert xml_result is True
    xml_result = xml.get_attribute(str(xml_file), ".//actor[@id='3']")
    assert xml_result == {"edited": "uh-huh", "id": "3"}
