# import pytest
import salt.returners.nagios_nrdp_return as nagios_nrdp_return
from salt._compat import ElementTree as ET


def test_prepare_xml():
    hostname = "salt"
    service = "salt-minion"

    opts = {
        "service": service,
        "hostname": hostname,
        "checktype": "active",
    }
    prepared_xml = nagios_nrdp_return._prepare_xml(options=opts)
    root = ET.fromstring(prepared_xml)

    checkresult = root.find("checkresult")
    hostname_res = checkresult.find("hostname").text
    servicename_res = checkresult.find("servicename").text

    assert servicename_res == service
    assert hostname_res == hostname
