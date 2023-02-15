import logging
import random
import string

import pytest

import salt.config
import salt.loader
import salt.states.boto_iot as boto_iot
from tests.support.mock import MagicMock, patch

boto = pytest.importorskip("boto")
boto3 = pytest.importorskip("boto3", "1.2.1")
botocore = pytest.importorskip("botocore", "1.4.41")

log = logging.getLogger(__name__)


class GlobalConfig:
    region = "us-east-1"
    access_key = "GKTADJGHEIQSXMKKRBJ08H"
    secret_key = "askdjghsdfjkghWupUjasdflkdfklgjsdfjajkghs"
    conn_parameters = {
        "region": region,
        "key": access_key,
        "keyid": secret_key,
        "profile": {},
    }
    error_message = (
        "An error occurred (101) when calling the {0} operation: Test-defined error"
    )
    not_found_error = botocore.exceptions.ClientError(
        {
            "Error": {
                "Code": "ResourceNotFoundException",
                "Message": "Test-defined error",
            }
        },
        "msg",
    )
    topic_rule_not_found_error = botocore.exceptions.ClientError(
        {"Error": {"Code": "UnauthorizedException", "Message": "Test-defined error"}},
        "msg",
    )
    error_content = {"Error": {"Code": 101, "Message": "Test-defined error"}}
    policy_ret = dict(
        policyName="testpolicy",
        policyDocument=(
            '{"Version": "2012-10-17", "Statement": [{"Action": ["iot:Publish"],'
            ' "Resource": ["*"], "Effect": "Allow"}]}'
        ),
        policyArn="arn:aws:iot:us-east-1:123456:policy/my_policy",
        policyVersionId=1,
        defaultVersionId=1,
    )
    topic_rule_ret = dict(
        ruleName="testrule",
        sql="SELECT * FROM 'iot/test'",
        description="topic rule description",
        createdAt="1970-01-01",
        actions=[{"iot": {"functionArn": "arn:aws:::function"}}],
        ruleDisabled=True,
    )
    principal = "arn:aws:iot:us-east-1:1234:cert/21fc104aaaf6043f5756c1b57bda84ea8395904c43f28517799b19e4c42514"

    thing_type_name = "test_thing_type"
    thing_type_desc = "test_thing_type_desc"
    thing_type_attr_1 = "test_thing_type_search_attr_1"
    thing_type_ret = dict(
        thingTypeName=thing_type_name,
        thingTypeProperties=dict(
            thingTypeDescription=thing_type_desc,
            searchableAttributes=[thing_type_attr_1],
        ),
        thingTypeMetadata=dict(
            deprecated=False, creationDate="2010-08-01 15:54:49.699000+00:00"
        ),
    )
    deprecated_thing_type_ret = dict(
        thingTypeName=thing_type_name,
        thingTypeProperties=dict(
            thingTypeDescription=thing_type_desc,
            searchableAttributes=[thing_type_attr_1],
        ),
        thingTypeMetadata=dict(
            deprecated=True,
            creationDate="2010-08-01 15:54:49.699000+00:00",
            deprecationDate="2010-08-02 15:54:49.699000+00:00",
        ),
    )
    thing_type_arn = "test_thing_type_arn"
    create_thing_type_ret = dict(
        thingTypeName=thing_type_name, thingTypeArn=thing_type_arn
    )


@pytest.fixture
def session_instance():
    GlobalConfig.conn_parameters["key"] = "".join(
        random.choice(string.ascii_lowercase + string.digits) for _ in range(50)
    )
    with patch("boto3.session.Session") as patched_session:
        yield patched_session()


@pytest.fixture
def configure_loader_modules(minion_opts):
    minion_opts["grains"] = salt.loader.grains(minion_opts)
    ctx = {}
    utils = salt.loader.utils(
        minion_opts,
        whitelist=["boto3", "args", "systemd", "path", "platform"],
        context=ctx,
    )
    serializers = salt.loader.serializers(minion_opts)
    funcs = funcs = salt.loader.minion_mods(
        minion_opts, context=ctx, utils=utils, whitelist=["boto_iot"]
    )
    salt_states = salt.loader.states(
        opts=minion_opts,
        functions=funcs,
        utils=utils,
        whitelist=["boto_iot"],
        serializers=serializers,
    )
    return {
        boto_iot: {
            "__opts__": minion_opts,
            "__salt__": funcs,
            "__utils__": utils,
            "__states__": salt_states,
            "__serializers__": serializers,
        }
    }


def test_present_when_thing_type_does_not_exist(session_instance):
    conn = MagicMock()
    session_instance.client.return_value = conn
    conn.describe_thing_type.side_effect = [
        GlobalConfig.not_found_error,
        GlobalConfig.thing_type_ret,
    ]
    conn.create_thing_type.return_value = GlobalConfig.create_thing_type_ret
    result = boto_iot.__states__["boto_iot.thing_type_present"](
        "thing type present",
        thingTypeName=GlobalConfig.thing_type_name,
        thingTypeDescription=GlobalConfig.thing_type_desc,
        searchableAttributesList=[GlobalConfig.thing_type_attr_1],
        **GlobalConfig.conn_parameters
    )
    assert result["result"]
    assert (
        result["changes"]["new"]["thing_type"]["thingTypeName"]
        == GlobalConfig.thing_type_name
    )


def test_present_when_thing_type_exists(session_instance):
    conn = MagicMock()
    session_instance.client.return_value = conn
    conn.describe_thing_type.return_value = GlobalConfig.thing_type_ret
    result = boto_iot.__states__["boto_iot.thing_type_present"](
        "thing type present",
        thingTypeName=GlobalConfig.thing_type_name,
        thingTypeDescription=GlobalConfig.thing_type_desc,
        searchableAttributesList=[GlobalConfig.thing_type_attr_1],
        **GlobalConfig.conn_parameters
    )
    assert result["result"]
    assert result["changes"] == {}
    assert conn.create_thing_type.call_count == 0


def test_present_with_failure(session_instance):
    conn = MagicMock()
    session_instance.client.return_value = conn
    conn.describe_thing_type.side_effect = [
        GlobalConfig.not_found_error,
        GlobalConfig.thing_type_ret,
    ]
    conn.create_thing_type.side_effect = botocore.exceptions.ClientError(
        GlobalConfig.error_content, "create_thing_type"
    )
    result = boto_iot.__states__["boto_iot.thing_type_present"](
        "thing type present",
        thingTypeName=GlobalConfig.thing_type_name,
        thingTypeDescription=GlobalConfig.thing_type_desc,
        searchableAttributesList=[GlobalConfig.thing_type_attr_1],
        **GlobalConfig.conn_parameters
    )
    assert not result["result"]
    assert "An error occurred" in result["comment"]


def test_absent_when_thing_type_does_not_exist(session_instance):
    conn = MagicMock()
    session_instance.client.return_value = conn
    conn.describe_thing_type.side_effect = GlobalConfig.not_found_error
    result = boto_iot.__states__["boto_iot.thing_type_absent"](
        "test", "mythingtype", **GlobalConfig.conn_parameters
    )
    assert result["result"]
    assert result["changes"] == {}


@pytest.mark.slow_test
def test_absent_when_thing_type_exists(session_instance):
    conn = MagicMock()
    session_instance.client.return_value = conn
    conn.describe_thing_type.return_value = GlobalConfig.deprecated_thing_type_ret
    result = boto_iot.__states__["boto_iot.thing_type_absent"](
        "test", GlobalConfig.thing_type_name, **GlobalConfig.conn_parameters
    )
    assert result["result"]
    assert result["changes"]["new"]["thing_type"] is None
    assert conn.deprecate_thing_type.call_count == 0


def test_absent_with_deprecate_failure(session_instance):
    conn = MagicMock()
    session_instance.client.return_value = conn
    conn.describe_thing_type.return_value = GlobalConfig.thing_type_ret
    conn.deprecate_thing_type.side_effect = botocore.exceptions.ClientError(
        GlobalConfig.error_content, "deprecate_thing_type"
    )
    result = boto_iot.__states__["boto_iot.thing_type_absent"](
        "test", GlobalConfig.thing_type_name, **GlobalConfig.conn_parameters
    )
    assert not result["result"]
    assert "An error occurred" in result["comment"]
    assert "deprecate_thing_type" in result["comment"]
    assert conn.delete_thing_type.call_count == 0


def test_absent_with_delete_failure(session_instance):
    conn = MagicMock()
    session_instance.client.return_value = conn
    conn.describe_thing_type.return_value = GlobalConfig.deprecated_thing_type_ret
    conn.delete_thing_type.side_effect = botocore.exceptions.ClientError(
        GlobalConfig.error_content, "delete_thing_type"
    )
    result = boto_iot.__states__["boto_iot.thing_type_absent"](
        "test", GlobalConfig.thing_type_name, **GlobalConfig.conn_parameters
    )
    assert not result["result"]
    assert "An error occurred" in result["comment"]
    assert "delete_thing_type" in result["comment"]
    assert conn.deprecate_thing_type.call_count == 0


def test_present_when_policy_does_not_exist(session_instance):
    conn = MagicMock()
    session_instance.client.return_value = conn
    conn.get_policy.side_effect = [
        GlobalConfig.not_found_error,
        GlobalConfig.policy_ret,
    ]
    conn.create_policy.return_value = GlobalConfig.policy_ret
    result = boto_iot.__states__["boto_iot.policy_present"](
        "policy present",
        policyName=GlobalConfig.policy_ret["policyName"],
        policyDocument=GlobalConfig.policy_ret["policyDocument"],
    )

    assert result["result"]
    assert (
        result["changes"]["new"]["policy"]["policyName"]
        == GlobalConfig.policy_ret["policyName"]
    )


def test_present_when_policy_exists(session_instance):
    conn = MagicMock()
    session_instance.client.return_value = conn
    conn.get_policy.return_value = GlobalConfig.policy_ret
    conn.create_policy_version.return_value = GlobalConfig.policy_ret
    result = boto_iot.__states__["boto_iot.policy_present"](
        "policy present",
        policyName=GlobalConfig.policy_ret["policyName"],
        policyDocument=GlobalConfig.policy_ret["policyDocument"],
    )
    assert result["result"]
    assert result["changes"] == {}


def test_present_again_with_failure(session_instance):
    conn = MagicMock()
    session_instance.client.return_value = conn
    conn.get_policy.side_effect = [
        GlobalConfig.not_found_error,
        GlobalConfig.policy_ret,
    ]
    conn.create_policy.side_effect = botocore.exceptions.ClientError(
        GlobalConfig.error_content, "create_policy"
    )
    result = boto_iot.__states__["boto_iot.policy_present"](
        "policy present",
        policyName=GlobalConfig.policy_ret["policyName"],
        policyDocument=GlobalConfig.policy_ret["policyDocument"],
    )
    assert not result["result"]
    assert "An error occurred" in result["comment"]


def test_absent_when_policy_does_not_exist(session_instance):
    conn = MagicMock()
    session_instance.client.return_value = conn
    conn.get_policy.side_effect = GlobalConfig.not_found_error
    result = boto_iot.__states__["boto_iot.policy_absent"]("test", "mypolicy")
    assert result["result"]
    assert result["changes"] == {}


def test_absent_when_policy_exists(session_instance):
    conn = MagicMock()
    session_instance.client.return_value = conn
    conn.get_policy.return_value = GlobalConfig.policy_ret
    conn.list_policy_versions.return_value = {"policyVersions": []}
    result = boto_iot.__states__["boto_iot.policy_absent"](
        "test", GlobalConfig.policy_ret["policyName"]
    )
    assert result["result"]
    assert result["changes"]["new"]["policy"] is None


def test_absent_with_failure(session_instance):
    conn = MagicMock()
    session_instance.client.return_value = conn
    conn.get_policy.return_value = GlobalConfig.policy_ret
    conn.list_policy_versions.return_value = {"policyVersions": []}
    conn.delete_policy.side_effect = botocore.exceptions.ClientError(
        GlobalConfig.error_content, "delete_policy"
    )
    result = boto_iot.__states__["boto_iot.policy_absent"](
        "test", GlobalConfig.policy_ret["policyName"]
    )
    assert not result["result"]
    assert "An error occurred" in result["comment"]


def test_attached_when_policy_not_attached(session_instance):
    conn = MagicMock()
    session_instance.client.return_value = conn
    conn.list_principal_policies.return_value = {"policies": []}
    result = boto_iot.__states__["boto_iot.policy_attached"](
        "test", "myfunc", GlobalConfig.principal
    )
    assert result["result"]
    assert result["changes"]["new"]["attached"]


def test_attached_when_policy_attached(session_instance):
    conn = MagicMock()
    session_instance.client.return_value = conn
    conn.list_principal_policies.return_value = {"policies": [GlobalConfig.policy_ret]}
    result = boto_iot.__states__["boto_iot.policy_attached"](
        "test", GlobalConfig.policy_ret["policyName"], GlobalConfig.principal
    )
    assert result["result"]
    assert result["changes"] == {}


def test_attached_with_failure(session_instance):
    conn = MagicMock()
    session_instance.client.return_value = conn
    conn.list_principal_policies.return_value = {"policies": []}
    conn.attach_principal_policy.side_effect = botocore.exceptions.ClientError(
        GlobalConfig.error_content, "attach_principal_policy"
    )
    result = boto_iot.__states__["boto_iot.policy_attached"](
        "test", GlobalConfig.policy_ret["policyName"], GlobalConfig.principal
    )
    assert not result["result"]
    assert result["changes"] == {}


def test_detached_when_policy_not_detached(session_instance):
    conn = MagicMock()
    session_instance.client.return_value = conn
    conn.list_principal_policies.return_value = {"policies": [GlobalConfig.policy_ret]}
    result = boto_iot.__states__["boto_iot.policy_detached"](
        "test", GlobalConfig.policy_ret["policyName"], GlobalConfig.principal
    )
    assert result["result"]
    log.warning(result)
    assert not result["changes"]["new"]["attached"]


def test_detached_when_policy_detached(session_instance):
    conn = MagicMock()
    session_instance.client.return_value = conn
    conn.list_principal_policies.return_value = {"policies": []}
    result = boto_iot.__states__["boto_iot.policy_detached"](
        "test", GlobalConfig.policy_ret["policyName"], GlobalConfig.principal
    )
    assert result["result"]
    assert result["changes"] == {}


def test_detached_with_failure(session_instance):
    conn = MagicMock()
    session_instance.client.return_value = conn
    conn.list_principal_policies.return_value = {"policies": [GlobalConfig.policy_ret]}
    conn.detach_principal_policy.side_effect = botocore.exceptions.ClientError(
        GlobalConfig.error_content, "detach_principal_policy"
    )
    result = boto_iot.__states__["boto_iot.policy_detached"](
        "test", GlobalConfig.policy_ret["policyName"], GlobalConfig.principal
    )
    assert not result["result"]
    assert result["changes"] == {}


def test_present_when_topic_rule_does_not_exist(session_instance):
    conn = MagicMock()
    session_instance.client.return_value = conn
    conn.get_topic_rule.side_effect = [
        GlobalConfig.topic_rule_not_found_error,
        {"rule": GlobalConfig.topic_rule_ret},
    ]
    conn.create_topic_rule.return_value = {"created": True}
    result = boto_iot.__states__["boto_iot.topic_rule_present"](
        "topic rule present",
        ruleName=GlobalConfig.topic_rule_ret["ruleName"],
        sql=GlobalConfig.topic_rule_ret["sql"],
        description=GlobalConfig.topic_rule_ret["description"],
        actions=GlobalConfig.topic_rule_ret["actions"],
        ruleDisabled=GlobalConfig.topic_rule_ret["ruleDisabled"],
    )

    assert result["result"]
    assert (
        result["changes"]["new"]["rule"]["ruleName"]
        == GlobalConfig.topic_rule_ret["ruleName"]
    )


def test_present_when_next_policy_exists(session_instance):
    conn = MagicMock()
    session_instance.client.return_value = conn
    conn.get_topic_rule.return_value = {"rule": GlobalConfig.topic_rule_ret}
    conn.create_topic_rule.return_value = {"created": True}
    result = boto_iot.__states__["boto_iot.topic_rule_present"](
        "topic rule present",
        ruleName=GlobalConfig.topic_rule_ret["ruleName"],
        sql=GlobalConfig.topic_rule_ret["sql"],
        description=GlobalConfig.topic_rule_ret["description"],
        actions=GlobalConfig.topic_rule_ret["actions"],
        ruleDisabled=GlobalConfig.topic_rule_ret["ruleDisabled"],
    )
    assert result["result"]
    assert result["changes"] == {}


def test_present_next_with_failure(session_instance):
    conn = MagicMock()
    session_instance.client.return_value = conn
    conn.get_topic_rule.side_effect = [
        GlobalConfig.topic_rule_not_found_error,
        {"rule": GlobalConfig.topic_rule_ret},
    ]
    conn.create_topic_rule.side_effect = botocore.exceptions.ClientError(
        GlobalConfig.error_content, "create_topic_rule"
    )
    result = boto_iot.__states__["boto_iot.topic_rule_present"](
        "topic rule present",
        ruleName=GlobalConfig.topic_rule_ret["ruleName"],
        sql=GlobalConfig.topic_rule_ret["sql"],
        description=GlobalConfig.topic_rule_ret["description"],
        actions=GlobalConfig.topic_rule_ret["actions"],
        ruleDisabled=GlobalConfig.topic_rule_ret["ruleDisabled"],
    )
    assert not result["result"]
    assert "An error occurred" in result["comment"]


def test_absent_when_topic_rule_does_not_exist(session_instance):
    conn = MagicMock()
    session_instance.client.return_value = conn
    conn.get_topic_rule.side_effect = GlobalConfig.topic_rule_not_found_error
    result = boto_iot.__states__["boto_iot.topic_rule_absent"]("test", "myrule")
    assert result["result"]
    assert result["changes"] == {}


def test_absent_when_topic_rule_exists(session_instance):
    conn = MagicMock()
    session_instance.client.return_value = conn
    conn.get_topic_rule.return_value = GlobalConfig.topic_rule_ret
    result = boto_iot.__states__["boto_iot.topic_rule_absent"](
        "test", GlobalConfig.topic_rule_ret["ruleName"]
    )
    assert result["result"]
    assert result["changes"]["new"]["rule"] is None


def test_absent_next_with_failure(session_instance):
    conn = MagicMock()
    session_instance.client.return_value = conn
    conn.get_topic_rule.return_value = GlobalConfig.topic_rule_ret
    conn.delete_topic_rule.side_effect = botocore.exceptions.ClientError(
        GlobalConfig.error_content, "delete_topic_rule"
    )
    result = boto_iot.__states__["boto_iot.topic_rule_absent"](
        "test", GlobalConfig.topic_rule_ret["ruleName"]
    )
    assert not result["result"]
    assert "An error occurred" in result["comment"]
