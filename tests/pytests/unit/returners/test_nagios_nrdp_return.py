# import pytest
import xml.etree.ElementTree as ET

import salt.returners.nagios_nrdp_return as nagios_nrdp_return


def test_prepare_xml():
    hostname = "salt"
    service = "salt-minion"

    opts = {
        "hostname": hostname,
        "service": service,
        "checktype": "active",
    }

    xml_ret = nagios_nrdp_return._prepare_xml(options=opts)
    root = ET.fromstring(xml_ret)

    checkresult = root.find("checkresult")
    hostname_res = checkresult.find("hostname").text
    servicename_res = checkresult.find("servicename").text

    # Verify the regular XML format.
    assert servicename_res == service
    assert hostname_res == hostname


def test_escaped_xml():
    opts = {
        "hostname": "s&lt",
        "output": 'output"',
        "service": "salt-<minion>",
        "checktype": "active",
    }

    xml_ret = nagios_nrdp_return._prepare_xml(options=opts)

    assert "s&amp;lt" in xml_ret
    assert "salt-&lt;minion&gt;" in xml_ret
    assert "output&quot;" in xml_ret
