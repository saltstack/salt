import pytest

import salt.states.smartos as smartos
from salt.utils.odict import OrderedDict
from tests.support.mock import patch


@pytest.fixture
def configure_loader_modules():
    return {smartos: {"__opts__": {"test": False}}}


def test_config_present_does_not_exist():
    """
    Test salt.states.smartos.config_present
    when the config files does not exist
    """
    name = "test"
    value = "test_value"
    with patch("os.path.isfile", return_value=False):
        with patch("salt.utils.atomicfile.atomic_open", side_effect=IOError):
            ret = smartos.config_present(name=name, value=value)
    assert not ret["result"]
    assert (
        ret["comment"]
        == f'Could not add property {name} with value "{value}" to config'
    )


def test_parse_vmconfig_vrrp():
    """
    Test _parse_vmconfig's vrid -> mac convertor

    SmartOS will always use a mac based on the vrrp_vrid,
    so we will replace the provided mac with the one based
    on this value.

    Doing so ensures that 'old' nics are removed and 'new'
    nics get added as these actions are keyed on the mac
    property.
    """
    # NOTE: vmconfig is not a full vmadm payload,
    #       this is not an issue given we are only testing
    #       the vrrp_vrid to mac conversions
    ret = smartos._parse_vmconfig(
        OrderedDict(
            [
                (
                    "nics",
                    OrderedDict(
                        [
                            (
                                "00:00:5e:00:01:01",
                                OrderedDict(
                                    [
                                        ("vrrp_vrid", 1),
                                        ("vrrp_primary_ip", "12.34.5.6"),
                                    ]
                                ),
                            ),
                            (
                                "00:00:5e:00:01:24",
                                OrderedDict(
                                    [
                                        ("vrrp_vrid", 240),
                                        ("vrrp_primary_ip", "12.34.5.6"),
                                    ]
                                ),
                            ),
                            (
                                "00:22:06:00:00:01",
                                OrderedDict([("ips", ["12.34.5.6/24"])]),
                            ),
                        ]
                    ),
                )
            ]
        ),
        {"nics": "mac"},
    )

    # NOTE: nics.0 is a vrrp nic with correct mac (check mac == vrid based -> unchanged)
    assert ret["nics"][0]["mac"] == "00:00:5e:00:01:01"

    # NOTE: nics.1 is a vrrp nic with incorrect mac (check mac == vrid based -> changed)
    assert ret["nics"][1]["mac"] == "00:00:5e:00:01:f0"

    # NOTE: nics.2 was not a vrrp nic (check mac was not changed)
    assert ret["nics"][2]["mac"] == "00:22:06:00:00:01"
