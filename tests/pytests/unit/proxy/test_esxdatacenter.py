"""
    :codeauthor: :email:`Alexandru Bleotu <alexandru.bleotu@morganstanley.com>`

    Tests for esxdatacenter proxy
"""
import pytest

import salt.exceptions
import salt.proxy.esxdatacenter as esxdatacenter
from salt.config.schemas.esxdatacenter import EsxdatacenterProxySchema
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
            "proxytype": "esxdatacenter",
            "vcenter": "fake_vcenter",
            "datacenter": "fake_dc",
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
            "proxytype": "esxdatacenter",
            "vcenter": "fake_vcenter",
            "datacenter": "fake_dc",
            "mechanism": "sspi",
            "domain": "fake_domain",
            "principal": "fake_principal",
            "protocol": "fake_protocol",
            "port": 100,
        }
    }


@pytest.fixture
def configure_loader_modules(opts_sspi):
    with patch.dict(esxdatacenter.DETAILS):
        with patch(
            "salt.proxy.esxdatacenter.merge",
            MagicMock(return_value=opts_sspi["proxy"]),
        ):
            yield {esxdatacenter: {"__pillar__": {}}}


def test_merge(opts_sspi):
    mock_pillar_proxy = MagicMock()
    mock_opts_proxy = MagicMock()
    mock_merge = MagicMock(return_value=opts_sspi["proxy"])
    with patch.dict(esxdatacenter.__pillar__, {"proxy": mock_pillar_proxy}):
        with patch("salt.proxy.esxdatacenter.merge", mock_merge):
            esxdatacenter.init(opts={"proxy": mock_opts_proxy})
    mock_merge.assert_called_once_with(mock_opts_proxy, mock_pillar_proxy)


def test_esxdatacenter_schema(opts_sspi):
    mock_json_validate = MagicMock()
    serialized_schema = EsxdatacenterProxySchema().serialize()
    with patch("salt.proxy.esxdatacenter.jsonschema.validate", mock_json_validate):
        esxdatacenter.init(opts_sspi)
    mock_json_validate.assert_called_once_with(opts_sspi["proxy"], serialized_schema)


def test_invalid_proxy_input_error(opts_userpass):
    with patch(
        "salt.proxy.esxdatacenter.jsonschema.validate",
        MagicMock(
            side_effect=jsonschema.exceptions.ValidationError("Validation Error")
        ),
    ):
        with pytest.raises(salt.exceptions.InvalidConfigError) as excinfo:
            esxdatacenter.init(opts_userpass)
    assert excinfo.value.message == "Validation Error"


def test_no_username(opts_userpass):
    opts = opts_userpass.copy()
    del opts["proxy"]["username"]
    with patch("salt.proxy.esxdatacenter.merge", MagicMock(return_value=opts["proxy"])):
        with pytest.raises(salt.exceptions.InvalidConfigError) as excinfo:
            esxdatacenter.init(opts)
    assert (
        excinfo.value.message == "Mechanism is set to 'userpass', but no "
        "'username' key found in proxy config."
    )


def test_no_passwords(opts_userpass):
    opts = opts_userpass.copy()
    del opts["proxy"]["passwords"]
    with patch("salt.proxy.esxdatacenter.merge", MagicMock(return_value=opts["proxy"])):
        with pytest.raises(salt.exceptions.InvalidConfigError) as excinfo:
            esxdatacenter.init(opts)
    assert (
        excinfo.value.message == "Mechanism is set to 'userpass', but no "
        "'passwords' key found in proxy config."
    )


def test_no_domain(opts_sspi):
    opts = opts_sspi.copy()
    del opts["proxy"]["domain"]
    with patch("salt.proxy.esxdatacenter.merge", MagicMock(return_value=opts["proxy"])):
        with pytest.raises(salt.exceptions.InvalidConfigError) as excinfo:
            esxdatacenter.init(opts)
    assert (
        excinfo.value.message
        == "Mechanism is set to 'sspi', but no 'domain' key found in proxy config."
    )


def test_no_principal(opts_sspi):
    opts = opts_sspi.copy()
    del opts["proxy"]["principal"]
    with patch("salt.proxy.esxdatacenter.merge", MagicMock(return_value=opts["proxy"])):
        with pytest.raises(salt.exceptions.InvalidConfigError) as excinfo:
            esxdatacenter.init(opts)
    assert (
        excinfo.value.message
        == "Mechanism is set to 'sspi', but no 'principal' key found in proxy config."
    )


def test_find_credentials(opts_userpass):
    mock_find_credentials = MagicMock(return_value=("fake_username", "fake_password"))
    with patch(
        "salt.proxy.esxdatacenter.merge",
        MagicMock(return_value=opts_userpass["proxy"]),
    ):
        with patch("salt.proxy.esxdatacenter.find_credentials", mock_find_credentials):
            esxdatacenter.init(opts_userpass)
    mock_find_credentials.assert_called_once_with()


def test_details_userpass(opts_userpass):
    mock_find_credentials = MagicMock(return_value=("fake_username", "fake_password"))
    with patch(
        "salt.proxy.esxdatacenter.merge",
        MagicMock(return_value=opts_userpass["proxy"]),
    ):
        with patch("salt.proxy.esxdatacenter.find_credentials", mock_find_credentials):
            esxdatacenter.init(opts_userpass)
    assert esxdatacenter.DETAILS == {
        "vcenter": "fake_vcenter",
        "datacenter": "fake_dc",
        "mechanism": "userpass",
        "username": "fake_username",
        "password": "fake_password",
        "passwords": ["fake_password"],
        "protocol": "fake_protocol",
        "port": 100,
    }


def test_details_sspi(opts_sspi):
    esxdatacenter.init(opts_sspi)
    assert esxdatacenter.DETAILS == {
        "vcenter": "fake_vcenter",
        "datacenter": "fake_dc",
        "mechanism": "sspi",
        "domain": "fake_domain",
        "principal": "fake_principal",
        "protocol": "fake_protocol",
        "port": 100,
    }
