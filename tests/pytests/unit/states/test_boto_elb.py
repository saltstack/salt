"""
    :codeauthor: Jayesh Kariya <jayeshk@saltstack.com>
"""

import copy

import pytest
import salt.states.boto_elb as boto_elb
from tests.support.mock import MagicMock, patch


@pytest.fixture
def configure_loader_modules():
    return {boto_elb: {}}


def test_present():
    """
    Test to ensure the IAM role exists.
    """
    name = "myelb"
    listeners = [
        {
            "elb_port": "ELBPORT",
            "instance_port": "PORT",
            "elb_protocol": "HTTPS",
            "certificate": "A",
        }
    ]
    alarms = {"MyAlarm": {"name": name, "attributes": {"description": "A"}}}
    attrs = {
        "alarm_actions": ["arn:aws:sns:us-east-1:12345:myalarm"],
        "insufficient_data_actions": [],
        "ok_actions": ["arn:aws:sns:us-east-1:12345:myalarm"],
    }
    health_check = {"target:": "HTTP:80/"}
    avail_zones = ["us-east-1a", "us-east-1c", "us-east-1d"]
    cnames = [{"name": "www.test.com", "zone": "test.com", "ttl": 60}]

    ret = {"name": name, "result": True, "changes": {}, "comment": ""}
    ret1 = copy.deepcopy(ret)

    mock = MagicMock(return_value={})
    mock_false_bool = MagicMock(return_value=False)
    mock_true_bool = MagicMock(return_value=True)
    mock_attributes = MagicMock(return_value=attrs)
    mock_health_check = MagicMock(return_value=health_check)

    with patch.dict(
        boto_elb.__salt__,
        {
            "config.option": mock,
            "boto_elb.exists": mock_false_bool,
            "boto_elb.create": mock_false_bool,
            "pillar.get": MagicMock(return_value={}),
        },
    ):
        with patch.dict(boto_elb.__opts__, {"test": False}):
            ret = boto_elb.present(name, listeners, availability_zones=avail_zones)
            assert boto_elb.__salt__["boto_elb.exists"].called
            assert boto_elb.__salt__["boto_elb.create"].called
            assert "Failed to create myelb ELB." in ret["comment"]
            assert not ret["result"]

    def mock_config_option(*args, **kwargs):
        if args[0] == "boto_elb_policies":
            return []
        return {}

    mock = MagicMock(return_value={})
    with patch.dict(
        boto_elb.__salt__,
        {
            "config.option": MagicMock(side_effect=mock_config_option),
            "boto_elb.exists": mock_false_bool,
            "boto_elb.create": mock_true_bool,
            "boto_elb.get_attributes": mock_attributes,
            "boto_elb.get_health_check": mock_health_check,
            "boto_elb.get_elb_config": MagicMock(side_effect=[mock, MagicMock()]),
            "pillar.get": MagicMock(return_value={}),
        },
    ):
        with patch.dict(boto_elb.__opts__, {"test": False}):
            with patch.dict(
                boto_elb.__states__,
                {"boto_cloudwatch_alarm.present": MagicMock(return_value=ret1)},
            ):
                ret = boto_elb.present(
                    name,
                    listeners,
                    availability_zones=avail_zones,
                    health_check=health_check,
                    alarms=alarms,
                )
                assert boto_elb.__salt__["boto_elb.exists"].called
                assert boto_elb.__salt__["boto_elb.create"].called
                assert boto_elb.__states__["boto_cloudwatch_alarm.present"].called
                assert not boto_elb.__salt__["boto_elb.get_attributes"].called
                assert boto_elb.__salt__["boto_elb.get_health_check"].called
                assert "ELB myelb created." in ret["comment"]
                assert ret["result"]

    mock = MagicMock(return_value={})
    mock_elb = MagicMock(
        return_value={
            "dns_name": "myelb.amazon.com",
            "policies": [],
            "listeners": [],
            "backends": [],
        }
    )
    with patch.dict(
        boto_elb.__salt__,
        {
            "config.option": MagicMock(side_effect=mock_config_option),
            "boto_elb.exists": mock_false_bool,
            "boto_elb.create": mock_true_bool,
            "boto_elb.get_attributes": mock_attributes,
            "boto_elb.get_health_check": mock_health_check,
            "boto_elb.get_elb_config": mock_elb,
            "pillar.get": MagicMock(return_value={}),
        },
    ):
        with patch.dict(boto_elb.__opts__, {"test": False}):
            with patch.dict(
                boto_elb.__states__,
                {"boto_route53.present": MagicMock(return_value=ret1)},
            ):
                ret = boto_elb.present(
                    name,
                    listeners,
                    availability_zones=avail_zones,
                    health_check=health_check,
                    cnames=cnames,
                )
                mock_changes = {"new": {"elb": "myelb"}, "old": {"elb": None}}
                assert boto_elb.__states__["boto_route53.present"].called
                assert mock_changes == ret["changes"]
                assert ret["result"]


def test_register_instances():
    """
    Test to add instance/s to load balancer
    """
    name = "myelb"
    instances = ["instance-id1", "instance-id2"]

    ret = {"name": name, "result": False, "changes": {}, "comment": ""}

    mock_bool = MagicMock(return_value=False)
    with patch.dict(boto_elb.__salt__, {"boto_elb.exists": mock_bool}):
        comt = "Could not find lb {}".format(name)
        ret.update({"comment": comt})
        assert boto_elb.register_instances(name, instances) == ret


def test_absent():
    """
    Test to ensure the IAM role is deleted.
    """
    name = "new_table"

    ret = {"name": name, "result": True, "changes": {}, "comment": ""}

    mock = MagicMock(side_effect=[False, True])
    with patch.dict(boto_elb.__salt__, {"boto_elb.exists": mock}):
        comt = "{} ELB does not exist.".format(name)
        ret.update({"comment": comt})
        assert boto_elb.absent(name) == ret

        with patch.dict(boto_elb.__opts__, {"test": True}):
            comt = "ELB {} is set to be removed.".format(name)
            ret.update({"comment": comt, "result": None})
            assert boto_elb.absent(name) == ret
