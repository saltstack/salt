from salt._compat import ElementTree as ET


def append_to_XMLDesc(mocked, fragment):
    """
    Append an XML fragment at the end of the mocked XMLDesc return_value of mocked.
    """
    xml_doc = ET.fromstring(mocked.XMLDesc())
    xml_fragment = ET.fromstring(fragment)
    xml_doc.append(xml_fragment)
    mocked.XMLDesc.return_value = ET.tostring(xml_doc)
