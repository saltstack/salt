import pytest
import salt.utils.xmlutil as xml
from salt._compat import ElementTree as ET


@pytest.fixture
def xml_doc():
    return ET.fromstring(
        """
        <domain>
            <name>test01</name>
            <memory unit="MiB">1024</memory>
            <cpu>
                <topology sockets="1"/>
            </cpu>
            <vcpus>
              <vcpu enabled="yes" id="1"/>
            </vcpus>
        </domain>
    """
    )


def test_change_xml_text(xml_doc):
    ret = xml.change_xml(
        xml_doc, {"name": "test02"}, [{"path": "name", "xpath": "name"}]
    )
    assert ret
    assert "test02" == xml_doc.find("name").text


def test_change_xml_text_nochange(xml_doc):
    ret = xml.change_xml(
        xml_doc, {"name": "test01"}, [{"path": "name", "xpath": "name"}]
    )
    assert not ret


def test_change_xml_text_notdefined(xml_doc):
    ret = xml.change_xml(xml_doc, {}, [{"path": "name", "xpath": "name"}])
    assert not ret


def test_change_xml_text_removed(xml_doc):
    ret = xml.change_xml(xml_doc, {"name": None}, [{"path": "name", "xpath": "name"}])
    assert ret
    assert xml_doc.find("name") is None


def test_change_xml_text_add(xml_doc):
    ret = xml.change_xml(
        xml_doc,
        {"cpu": {"vendor": "ACME"}},
        [{"path": "cpu:vendor", "xpath": "cpu/vendor"}],
    )
    assert ret
    assert "ACME" == xml_doc.find("cpu/vendor").text


def test_change_xml_convert(xml_doc):
    ret = xml.change_xml(
        xml_doc,
        {"mem": 2},
        [{"path": "mem", "xpath": "memory", "convert": lambda v: v * 1024}],
    )
    assert ret
    assert "2048" == xml_doc.find("memory").text


def test_change_xml_attr(xml_doc):
    ret = xml.change_xml(
        xml_doc,
        {"cpu": {"topology": {"cores": 4}}},
        [
            {
                "path": "cpu:topology:cores",
                "xpath": "cpu/topology",
                "get": lambda n: int(n.get("cores")) if n.get("cores") else None,
                "set": lambda n, v: n.set("cores", str(v)),
                "del": xml.del_attribute("cores"),
            }
        ],
    )
    assert ret
    assert "4" == xml_doc.find("cpu/topology").get("cores")


def test_change_xml_attr_unchanged(xml_doc):
    ret = xml.change_xml(
        xml_doc,
        {"cpu": {"topology": {"sockets": 1}}},
        [
            {
                "path": "cpu:topology:sockets",
                "xpath": "cpu/topology",
                "get": lambda n: int(n.get("sockets")) if n.get("sockets") else None,
                "set": lambda n, v: n.set("sockets", str(v)),
                "del": xml.del_attribute("sockets"),
            }
        ],
    )
    assert not ret


def test_change_xml_attr_remove(xml_doc):
    ret = xml.change_xml(
        xml_doc,
        {"cpu": {"topology": {"sockets": None}}},
        [
            {
                "path": "cpu:topology:sockets",
                "xpath": "./cpu/topology",
                "get": lambda n: int(n.get("sockets")) if n.get("sockets") else None,
                "set": lambda n, v: n.set("sockets", str(v)),
                "del": xml.del_attribute("sockets"),
            }
        ],
    )
    assert ret
    assert xml_doc.find("cpu") is None


def test_change_xml_not_simple_value(xml_doc):
    ret = xml.change_xml(
        xml_doc,
        {"cpu": {"topology": {"sockets": None}}},
        [{"path": "cpu", "xpath": "vcpu", "get": lambda n: int(n.text)}],
    )
    assert not ret


def test_change_xml_template(xml_doc):
    ret = xml.change_xml(
        xml_doc,
        {"cpu": {"vcpus": {2: {"enabled": True}, 4: {"enabled": False}}}},
        [
            {
                "path": "cpu:vcpus:{id}:enabled",
                "xpath": "vcpus/vcpu[@id='$id']",
                "convert": lambda v: "yes" if v else "no",
                "get": lambda n: n.get("enabled"),
                "set": lambda n, v: n.set("enabled", v),
                "del": xml.del_attribute("enabled", ["id"]),
            },
        ],
    )
    assert ret
    assert xml_doc.find("vcpus/vcpu[@id='1']") is None
    assert "yes" == xml_doc.find("vcpus/vcpu[@id='2']").get("enabled")
    assert "no" == xml_doc.find("vcpus/vcpu[@id='4']").get("enabled")


def test_change_xml_template_remove(xml_doc):
    ret = xml.change_xml(
        xml_doc,
        {"cpu": {"vcpus": None}},
        [
            {
                "path": "cpu:vcpus:{id}:enabled",
                "xpath": "vcpus/vcpu[@id='$id']",
                "convert": lambda v: "yes" if v else "no",
                "get": lambda n: n.get("enabled"),
                "set": lambda n, v: n.set("enabled", v),
                "del": xml.del_attribute("enabled", ["id"]),
            },
        ],
    )
    assert ret
    assert xml_doc.find("vcpus") is None
