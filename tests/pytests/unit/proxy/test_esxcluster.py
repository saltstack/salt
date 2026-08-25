"""
    :codeauthor: :email:`Alexandru Bleotu <alexandru.bleotu@morganstanley.com>`

    Tests for esxcluster proxy
"""

import pytest

import salt.exceptions
import salt.proxy.esxcluster as esxcluster
from salt.config.schemas.esxcluster import EsxclusterProxySchema
from tests.support.mock import MagicMock, patch

try:
    import jsonschema

    HAS_JSONSCHEMA = True
except ImportError:
    HAS_JSONSCHEMA = False


pytestmark = [pytest.mark.skipif(not HAS_JSONSCHEMA, reason="jsonschema is required")]


@pytest.fixture
def opts_userpass():
    return {
        "proxy": {
            "proxytype": "esxcluster",
            "vcenter": "fake_vcenter",
            "datacenter": "fake_dc",
            "cluster": "fake_cluster",
            "mechanism": "userpass",
            "username": "fake_username",
            "passwords": ["fake_password"],
            "protocol": "fake_protocol",
            "port": 100,
        }
    }


@pytest.fixture
def opts_sspi():
    return {
        "proxy": {
            "proxytype": "esxcluster",
            "vcenter": "fake_vcenter",
            "datacenter": "fake_dc",
            "cluster": "fake_cluster",
            "mechanism": "sspi",
            "domain": "fake_domain",
            "principal": "fake_principal",
            "protocol": "fake_protocol",
            "port": 100,
        }
    }


@pytest.fixture
def configure_loader_modules(opts_sspi):
    with patch.dict(esxcluster.DETAILS):
        with patch(
            "salt.proxy.esxcluster.merge",
            MagicMock(return_value=opts_sspi["proxy"]),
        ):
            yield {esxcluster: {"__pillar__": {}}}


def test_merge(opts_sspi):
    mock_pillar_proxy = MagicMock()
    mock_opts_proxy = MagicMock()
    mock_merge = MagicMock(return_value=opts_sspi["proxy"])
    with patch.dict(esxcluster.__pillar__, {"proxy": mock_pillar_proxy}):
        with patch("salt.proxy.esxcluster.merge", mock_merge):
            esxcluster.init(opts={"proxy": mock_opts_proxy})
    mock_merge.assert_called_once_with(mock_opts_proxy, mock_pillar_proxy)


def test_esxcluster_schema(opts_sspi):
    mock_json_validate = MagicMock()
    serialized_schema = EsxclusterProxySchema().serialize()
    with patch("salt.proxy.esxcluster.jsonschema.validate", mock_json_validate):
        esxcluster.init(opts_sspi)
    mock_json_validate.assert_called_once_with(opts_sspi["proxy"], serialized_schema)


def test_invalid_proxy_input_error(opts_userpass):
    with patch(
        "salt.proxy.esxcluster.jsonschema.validate",
        MagicMock(
            side_effect=jsonschema.exceptions.ValidationError("Validation Error")
        ),
    ):
        with pytest.raises(salt.exceptions.InvalidConfigError) as excinfo:
            esxcluster.init(opts_userpass)
    assert excinfo.value.message == "Validation Error"


def test_no_username(opts_userpass):
    opts = opts_userpass.copy()
    del opts["proxy"]["username"]
    with patch("salt.proxy.esxcluster.merge", MagicMock(return_value=opts["proxy"])):
        with pytest.raises(salt.exceptions.InvalidConfigError) as excinfo:
            esxcluster.init(opts)
    assert (
        excinfo.value.message == "Mechanism is set to 'userpass', but no "
        "'username' key found in proxy config."
    )


def test_no_passwords(opts_userpass):
    opts = opts_userpass.copy()
    del opts["proxy"]["passwords"]
    with patch("salt.proxy.esxcluster.merge", MagicMock(return_value=opts["proxy"])):
        with pytest.raises(salt.exceptions.InvalidConfigError) as excinfo:
            esxcluster.init(opts)
    assert (
        excinfo.value.message == "Mechanism is set to 'userpass', but no "
        "'passwords' key found in proxy config."
    )


def test_no_domain(opts_sspi):
    opts = opts_sspi.copy()
    del opts["proxy"]["domain"]
    with patch("salt.proxy.esxcluster.merge", MagicMock(return_value=opts["proxy"])):
        with pytest.raises(salt.exceptions.InvalidConfigError) as excinfo:
            esxcluster.init(opts)
    assert (
        excinfo.value.message
        == "Mechanism is set to 'sspi', but no 'domain' key found in proxy config."
    )


def test_no_principal(opts_sspi):
    opts = opts_sspi.copy()
    del opts["proxy"]["principal"]
    with patch("salt.proxy.esxcluster.merge", MagicMock(return_value=opts["proxy"])):
        with pytest.raises(salt.exceptions.InvalidConfigError) as excinfo:
            esxcluster.init(opts)
    assert (
        excinfo.value.message
        == "Mechanism is set to 'sspi', but no 'principal' key found in proxy config."
    )


def test_find_credentials(opts_userpass):
    mock_find_credentials = MagicMock(return_value=("fake_username", "fake_password"))
    with patch(
        "salt.proxy.esxcluster.merge",
        MagicMock(return_value=opts_userpass["proxy"]),
    ):
        with patch("salt.proxy.esxcluster.find_credentials", mock_find_credentials):
            esxcluster.init(opts_userpass)
    mock_find_credentials.assert_called_once_with()


def test_details_userpass(opts_userpass):
    mock_find_credentials = MagicMock(return_value=("fake_username", "fake_password"))
    with patch(
        "salt.proxy.esxcluster.merge",
        MagicMock(return_value=opts_userpass["proxy"]),
    ):
        with patch("salt.proxy.esxcluster.find_credentials", mock_find_credentials):
            esxcluster.init(opts_userpass)
    assert esxcluster.DETAILS == {
        "vcenter": "fake_vcenter",
        "datacenter": "fake_dc",
        "cluster": "fake_cluster",
        "mechanism": "userpass",
        "username": "fake_username",
        "password": "fake_password",
        "passwords": ["fake_password"],
        "protocol": "fake_protocol",
        "port": 100,
    }


def test_details_sspi(opts_sspi):
    esxcluster.init(opts_sspi)
    assert esxcluster.DETAILS == {
        "vcenter": "fake_vcenter",
        "datacenter": "fake_dc",
        "cluster": "fake_cluster",
        "mechanism": "sspi",
        "domain": "fake_domain",
        "principal": "fake_principal",
        "protocol": "fake_protocol",
        "port": 100,
    }
