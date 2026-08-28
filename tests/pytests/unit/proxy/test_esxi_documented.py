"""
Tests that verify the ESXi proxy authentication options documented in
``doc/topics/tutorials/esxi_proxy_minion.rst`` and in
``salt/proxy/esxi.py`` actually validate against the
:class:`~salt.config.schemas.esxi.EsxiProxySchema` schema and that the
proxy ``init()`` accepts them.

This is a documentation-driven regression test for
`saltstack/salt#61987 <https://github.com/saltstack/salt/issues/61987>`_:
the docs used to omit the ``vcenter``, ``esxi_host``, ``mechanism``,
``domain``, and ``principal`` options. The tests here exercise each of
the documented pillar shapes so that if a future code change makes the
documented examples invalid, CI will fail and the docs can be updated
along with the code.

Live vCenter / ESXi integration is intentionally out of scope; the
schema and ``init()`` validation can be fully exercised against
in-memory pillar dictionaries.
"""

import pytest

import salt.proxy.esxi as esxi
from tests.support.mock import patch

pytestmark = [
    pytest.mark.skipif(
        not esxi.HAS_JSONSCHEMA,
        reason="jsonschema is required by the ESXi proxy module.",
    ),
]


@pytest.fixture
def configure_loader_modules():
    return {esxi: {"__pillar__": {}, "__opts__": {}}}


def _init_with_pillar(pillar):
    """
    Run ``esxi.init`` against the given proxy pillar dictionary and return
    a tuple of ``(result, details_snapshot)``.

    ``find_credentials`` and the underlying esxcli/pyVmomi calls are
    patched out so the test never reaches a real network.
    """
    with patch.dict(esxi.__pillar__, {"proxy": pillar}), patch.object(
        esxi, "find_credentials", return_value=("user", "pw")
    ):
        result = esxi.init({})
        return result, dict(esxi.DETAILS)


def test_documented_direct_host_pillar():
    """The direct-ESXi pillar example from the tutorial must validate."""
    result, details = _init_with_pillar(
        {
            "proxytype": "esxi",
            "host": "esxi-1.example.com",
            "username": "root",
            "passwords": ["first_password", "second_password"],
        }
    )
    assert result is True
    assert details["host"] == "esxi-1.example.com"
    assert details["proxytype"] == "esxi"


def test_documented_vcenter_userpass_pillar():
    """
    The ``mechanism: userpass`` vCenter pillar example must validate
    and populate the documented DETAILS keys.
    """
    pillar = {
        "proxytype": "esxi",
        "vcenter": "vcenter01.example.com",
        "esxi_host": "esxi-1.example.com",
        "mechanism": "userpass",
        "username": "administrator@vsphere.local",
        "passwords": ["first_password", "backup_password"],
        "protocol": "https",
        "port": 443,
    }
    _result, details = _init_with_pillar(pillar)
    assert details["vcenter"] == "vcenter01.example.com"
    assert details["esxi_host"] == "esxi-1.example.com"
    assert details["mechanism"] == "userpass"
    assert details["username"] == "administrator@vsphere.local"


def test_documented_vcenter_sspi_pillar():
    """
    The ``mechanism: sspi`` vCenter pillar example must validate and
    must NOT require ``username``/``passwords``.
    """
    pillar = {
        "proxytype": "esxi",
        "vcenter": "vcenter01.example.com",
        "esxi_host": "esxi-1.example.com",
        "mechanism": "sspi",
        "domain": "EXAMPLE.COM",
        "principal": "STS/vcenter01.example.com",
        "protocol": "https",
        "port": 443,
    }
    _result, details = _init_with_pillar(pillar)
    assert details["vcenter"] == "vcenter01.example.com"
    assert details["mechanism"] == "sspi"
    assert details["domain"] == "EXAMPLE.COM"
    assert details["principal"] == "STS/vcenter01.example.com"


def test_vcenter_sspi_requires_domain():
    """Omitting ``domain`` from an SSPI vCenter pillar must fail init."""
    pillar = {
        "proxytype": "esxi",
        "vcenter": "vcenter01.example.com",
        "esxi_host": "esxi-1.example.com",
        "mechanism": "sspi",
        "principal": "STS/vcenter01.example.com",
    }
    result, _details = _init_with_pillar(pillar)
    assert result is False


def test_vcenter_sspi_requires_principal():
    """Omitting ``principal`` from an SSPI vCenter pillar must fail init."""
    pillar = {
        "proxytype": "esxi",
        "vcenter": "vcenter01.example.com",
        "esxi_host": "esxi-1.example.com",
        "mechanism": "sspi",
        "domain": "EXAMPLE.COM",
    }
    result, _details = _init_with_pillar(pillar)
    assert result is False
