import logging
import random
import string

import pytest
import salt.config
import salt.loader
import salt.states.boto_iot as boto_iot
from salt.utils.versions import LooseVersion
from tests.support.mock import MagicMock, patch

# pylint: disable=import-error,no-name-in-module,unused-import
try:
    import boto
    import boto3
    from botocore.exceptions import ClientError
    from botocore import __version__ as found_botocore_version

    HAS_BOTO = True
except ImportError:
    HAS_BOTO = False

# pylint: enable=import-error,no-name-in-module,unused-import

# the boto_iot module relies on the connect_to_region() method
# which was added in boto 2.8.0
# https://github.com/boto/boto/commit/33ac26b416fbb48a60602542b4ce15dcc7029f12
required_boto3_version = "1.2.1"
required_botocore_version = "1.4.41"

log = logging.getLogger(__name__)


def _has_required_boto():
    """
    Returns True/False boolean depending on if Boto is installed and correct
    version.
    """
    if not HAS_BOTO:
        return False
    elif LooseVersion(boto3.__version__) < LooseVersion(required_boto3_version):
        return False
    elif LooseVersion(found_botocore_version) < LooseVersion(required_botocore_version):
        return False
    else:
        return True


if _has_required_boto():
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
    not_found_error = ClientError(
        {
            "Error": {
                "Code": "ResourceNotFoundException",
                "Message": "Test-defined error",
            }
        },
        "msg",
    )
    topic_rule_not_found_error = ClientError(
        {"Error": {"Code": "UnauthorizedException", "Message": "Test-defined error"}},
        "msg",
    )
    error_content = {"Error": {"Code": 101, "Message": "Test-defined error"}}
    policy_ret = dict(
        policyName="testpolicy",
        policyDocument='{"Version": "2012-10-17", "Statement": [{"Action": ["iot:Publish"], "Resource": ["*"], "Effect": "Allow"}]}',
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


@pytest.mark.skipif(HAS_BOTO is False, reason="The boto module must be installed.")
@pytest.mark.skipIf(
    _has_required_boto() is False,
    reason="The boto3 module must be greater than"
    " or equal to version {}".format(required_boto3_version),
)
@pytest.fixture
def configure_loader_modules():
    opts = salt.config.DEFAULT_MINION_OPTS.copy()
    opts["grains"] = salt.loader.grains(opts)
    ctx = {}
    utils = salt.loader.utils(
        opts, whitelist=["boto3", "args", "systemd", "path", "platform"], context=ctx,
    )
    serializers = salt.loader.serializers(opts)
    funcs = funcs = salt.loader.minion_mods(
        opts, context=ctx, utils=utils, whitelist=["boto_iot"]
    )
    salt_states = salt.loader.states(
        opts=opts,
        functions=funcs,
        utils=utils,
        whitelist=["boto_iot"],
        serializers=serializers,
    )
    return {
        boto_iot: {
            "__opts__": opts,
            "__salt__": funcs,
            "__utils__": utils,
            "__states__": salt_states,
            "__serializers__": serializers,
        }
    }


def test_present_when_thing_type_does_not_exist():
    """
    tests present on a thing type that does not exist.
    """
    conn_parameters["key"] = "".join(
        random.choice(string.ascii_lowercase + string.digits) for _ in range(50)
    )
    patcher = patch("boto3.session.Session")
    mock_session = patcher.start()
    session_instance = mock_session.return_value
    conn = MagicMock()
    session_instance.client.return_value = conn
    conn.describe_thing_type.side_effect = [not_found_error, thing_type_ret]
    conn.create_thing_type.return_value = create_thing_type_ret
    result = boto_iot.__states__["boto_iot.thing_type_present"](
        "thing type present",
        thingTypeName=thing_type_name,
        thingTypeDescription=thing_type_desc,
        searchableAttributesList=[thing_type_attr_1],
        **conn_parameters
    )
    assert result["result"]
    assert result["changes"]["new"]["thing_type"]["thingTypeName"] == thing_type_name


def test_present_when_thing_type_exists():
    conn_parameters["key"] = "".join(
        random.choice(string.ascii_lowercase + string.digits) for _ in range(50)
    )
    patcher = patch("boto3.session.Session")
    mock_session = patcher.start()
    session_instance = mock_session.return_value
    conn = MagicMock()
    session_instance.client.return_value = conn
    conn.describe_thing_type.return_value = thing_type_ret
    result = boto_iot.__states__["boto_iot.thing_type_present"](
        "thing type present",
        thingTypeName=thing_type_name,
        thingTypeDescription=thing_type_desc,
        searchableAttributesList=[thing_type_attr_1],
        **conn_parameters
    )
    assert result["result"]
    assert result["changes"] == {}
    assert conn.create_thing_type.call_count == 0


def test_present_with_failure():
    conn_parameters["key"] = "".join(
        random.choice(string.ascii_lowercase + string.digits) for _ in range(50)
    )
    patcher = patch("boto3.session.Session")
    mock_session = patcher.start()
    session_instance = mock_session.return_value
    conn = MagicMock()
    session_instance.client.return_value = conn
    conn.describe_thing_type.side_effect = [not_found_error, thing_type_ret]
    conn.create_thing_type.side_effect = ClientError(error_content, "create_thing_type")
    result = boto_iot.__states__["boto_iot.thing_type_present"](
        "thing type present",
        thingTypeName=thing_type_name,
        thingTypeDescription=thing_type_desc,
        searchableAttributesList=[thing_type_attr_1],
        **conn_parameters
    )
    assert not result["result"]
    assert "An error occurred" in result["comment"]


def test_absent_when_thing_type_does_not_exist():
    """
    Tests absent on a thing type does not exist
    """
    conn_parameters["key"] = "".join(
        random.choice(string.ascii_lowercase + string.digits) for _ in range(50)
    )
    patcher = patch("boto3.session.Session")
    mock_session = patcher.start()
    session_instance = mock_session.return_value
    conn = MagicMock()
    session_instance.client.return_value = conn
    conn.describe_thing_type.side_effect = not_found_error
    result = boto_iot.__states__["boto_iot.thing_type_absent"](
        "test", "mythingtype", **conn_parameters
    )
    assert result["result"]
    assert result["changes"] == {}


@pytest.mark.slow_test
def test_absent_when_thing_type_exists():
    """
    Tests absent on a thing type
    """
    conn_parameters["key"] = "".join(
        random.choice(string.ascii_lowercase + string.digits) for _ in range(50)
    )
    patcher = patch("boto3.session.Session")
    mock_session = patcher.start()
    session_instance = mock_session.return_value
    conn = MagicMock()
    session_instance.client.return_value = conn
    conn.describe_thing_type.return_value = deprecated_thing_type_ret
    result = boto_iot.__states__["boto_iot.thing_type_absent"](
        "test", thing_type_name, **conn_parameters
    )
    assert result["result"]
    assert result["changes"]["new"]["thing_type"] is None
    assert conn.deprecate_thing_type.call_count == 0


def test_absent_with_deprecate_failure():
    conn_parameters["key"] = "".join(
        random.choice(string.ascii_lowercase + string.digits) for _ in range(50)
    )
    patcher = patch("boto3.session.Session")
    mock_session = patcher.start()
    session_instance = mock_session.return_value
    conn = MagicMock()
    session_instance.client.return_value = conn
    conn.describe_thing_type.return_value = thing_type_ret
    conn.deprecate_thing_type.side_effect = ClientError(
        error_content, "deprecate_thing_type"
    )
    result = boto_iot.__states__["boto_iot.thing_type_absent"](
        "test", thing_type_name, **conn_parameters
    )
    assert not result["result"]
    assert "An error occurred" in result["comment"]
    assert "deprecate_thing_type" in result["comment"]
    assert conn.delete_thing_type.call_count == 0


def test_absent_with_delete_failure():
    conn_parameters["key"] = "".join(
        random.choice(string.ascii_lowercase + string.digits) for _ in range(50)
    )
    patcher = patch("boto3.session.Session")
    mock_session = patcher.start()
    session_instance = mock_session.return_value
    conn = MagicMock()
    session_instance.client.return_value = conn
    conn.describe_thing_type.return_value = deprecated_thing_type_ret
    conn.delete_thing_type.side_effect = ClientError(error_content, "delete_thing_type")
    result = boto_iot.__states__["boto_iot.thing_type_absent"](
        "test", thing_type_name, **conn_parameters
    )
    assert not result["result"]
    assert "An error occurred" in result["comment"]
    assert "delete_thing_type" in result["comment"]
    assert conn.deprecate_thing_type.call_count == 0


def test_present_when_policy_does_not_exist():
    """
    Tests present on a policy that does not exist.
    """
    conn_parameters["key"] = "".join(
        random.choice(string.ascii_lowercase + string.digits) for _ in range(50)
    )
    patcher = patch("boto3.session.Session")
    mock_session = patcher.start()
    session_instance = mock_session.return_value
    conn = MagicMock()
    session_instance.client.return_value = conn
    conn.get_policy.side_effect = [not_found_error, policy_ret]
    conn.create_policy.return_value = policy_ret
    result = boto_iot.__states__["boto_iot.policy_present"](
        "policy present",
        policyName=policy_ret["policyName"],
        policyDocument=policy_ret["policyDocument"],
    )

    assert result["result"]
    assert result["changes"]["new"]["policy"]["policyName"] == policy_ret["policyName"]


def test_present_when_policy_exists():
    conn_parameters["key"] = "".join(
        random.choice(string.ascii_lowercase + string.digits) for _ in range(50)
    )
    patcher = patch("boto3.session.Session")
    mock_session = patcher.start()
    session_instance = mock_session.return_value
    conn = MagicMock()
    session_instance.client.return_value = conn
    conn.get_policy.return_value = policy_ret
    conn.create_policy_version.return_value = policy_ret
    result = boto_iot.__states__["boto_iot.policy_present"](
        "policy present",
        policyName=policy_ret["policyName"],
        policyDocument=policy_ret["policyDocument"],
    )
    assert result["result"]
    assert result["changes"] == {}


def test_present_again_with_failure():
    conn_parameters["key"] = "".join(
        random.choice(string.ascii_lowercase + string.digits) for _ in range(50)
    )
    patcher = patch("boto3.session.Session")
    mock_session = patcher.start()
    session_instance = mock_session.return_value
    conn = MagicMock()
    session_instance.client.return_value = conn
    conn.get_policy.side_effect = [not_found_error, policy_ret]
    conn.create_policy.side_effect = ClientError(error_content, "create_policy")
    result = boto_iot.__states__["boto_iot.policy_present"](
        "policy present",
        policyName=policy_ret["policyName"],
        policyDocument=policy_ret["policyDocument"],
    )
    assert not result["result"]
    assert "An error occurred" in result["comment"]


def test_absent_when_policy_does_not_exist():
    """
    Tests absent on a policy that does not exist.
    """
    conn_parameters["key"] = "".join(
        random.choice(string.ascii_lowercase + string.digits) for _ in range(50)
    )
    patcher = patch("boto3.session.Session")
    mock_session = patcher.start()
    session_instance = mock_session.return_value
    conn = MagicMock()
    session_instance.client.return_value = conn
    conn.get_policy.side_effect = not_found_error
    result = boto_iot.__states__["boto_iot.policy_absent"]("test", "mypolicy")
    assert result["result"]
    assert result["changes"] == {}


def test_absent_when_policy_exists():
    conn_parameters["key"] = "".join(
        random.choice(string.ascii_lowercase + string.digits) for _ in range(50)
    )
    patcher = patch("boto3.session.Session")
    mock_session = patcher.start()
    session_instance = mock_session.return_value
    conn = MagicMock()
    session_instance.client.return_value = conn
    conn.get_policy.return_value = policy_ret
    conn.list_policy_versions.return_value = {"policyVersions": []}
    result = boto_iot.__states__["boto_iot.policy_absent"](
        "test", policy_ret["policyName"]
    )
    assert result["result"]
    assert result["changes"]["new"]["policy"] is None


def test_absent_with_failure():
    conn_parameters["key"] = "".join(
        random.choice(string.ascii_lowercase + string.digits) for _ in range(50)
    )
    patcher = patch("boto3.session.Session")
    mock_session = patcher.start()
    session_instance = mock_session.return_value
    conn = MagicMock()
    session_instance.client.return_value = conn
    conn.get_policy.return_value = policy_ret
    conn.list_policy_versions.return_value = {"policyVersions": []}
    conn.delete_policy.side_effect = ClientError(error_content, "delete_policy")
    result = boto_iot.__states__["boto_iot.policy_absent"](
        "test", policy_ret["policyName"]
    )
    assert not result["result"]
    assert "An error occurred" in result["comment"]


def test_attached_when_policy_not_attached():
    """
    Tests attached on a policy that is not attached.
    """
    conn_parameters["key"] = "".join(
        random.choice(string.ascii_lowercase + string.digits) for _ in range(50)
    )
    patcher = patch("boto3.session.Session")
    mock_session = patcher.start()
    session_instance = mock_session.return_value
    conn = MagicMock()
    session_instance.client.return_value = conn
    conn.list_principal_policies.return_value = {"policies": []}
    result = boto_iot.__states__["boto_iot.policy_attached"](
        "test", "myfunc", principal
    )
    assert result["result"]
    assert result["changes"]["new"]["attached"]


def test_attached_when_policy_attached():
    """
    Tests attached on a policy that is attached.
    """
    conn_parameters["key"] = "".join(
        random.choice(string.ascii_lowercase + string.digits) for _ in range(50)
    )
    patcher = patch("boto3.session.Session")
    mock_session = patcher.start()
    session_instance = mock_session.return_value
    conn = MagicMock()
    session_instance.client.return_value = conn
    conn.list_principal_policies.return_value = {"policies": [policy_ret]}
    result = boto_iot.__states__["boto_iot.policy_attached"](
        "test", policy_ret["policyName"], principal
    )
    assert result["result"]
    assert result["changes"] == {}


def test_attached_with_failure():
    """
    Tests attached on a policy that is attached.
    """
    conn_parameters["key"] = "".join(
        random.choice(string.ascii_lowercase + string.digits) for _ in range(50)
    )
    patcher = patch("boto3.session.Session")
    mock_session = patcher.start()
    session_instance = mock_session.return_value
    conn = MagicMock()
    session_instance.client.return_value = conn
    conn.list_principal_policies.return_value = {"policies": []}
    conn.attach_principal_policy.side_effect = ClientError(
        error_content, "attach_principal_policy"
    )
    result = boto_iot.__states__["boto_iot.policy_attached"](
        "test", policy_ret["policyName"], principal
    )
    assert not result["result"]
    assert result["changes"] == {}


def test_detached_when_policy_not_detached():
    """
    Tests detached on a policy that is not detached.
    """
    conn_parameters["key"] = "".join(
        random.choice(string.ascii_lowercase + string.digits) for _ in range(50)
    )
    patcher = patch("boto3.session.Session")
    mock_session = patcher.start()
    session_instance = mock_session.return_value
    conn = MagicMock()
    session_instance.client.return_value = conn
    conn.list_principal_policies.return_value = {"policies": [policy_ret]}
    result = boto_iot.__states__["boto_iot.policy_detached"](
        "test", policy_ret["policyName"], principal
    )
    assert result["result"]
    log.warning(result)
    assert not result["changes"]["new"]["attached"]


def test_detached_when_policy_detached():
    """
    Tests detached on a policy that is detached.
    """
    conn_parameters["key"] = "".join(
        random.choice(string.ascii_lowercase + string.digits) for _ in range(50)
    )
    patcher = patch("boto3.session.Session")
    mock_session = patcher.start()
    session_instance = mock_session.return_value
    conn = MagicMock()
    session_instance.client.return_value = conn
    conn.list_principal_policies.return_value = {"policies": []}
    result = boto_iot.__states__["boto_iot.policy_detached"](
        "test", policy_ret["policyName"], principal
    )
    assert result["result"]
    assert result["changes"] == {}


def test_detached_with_failure():
    """
    Tests detached on a policy that is detached.
    """
    conn_parameters["key"] = "".join(
        random.choice(string.ascii_lowercase + string.digits) for _ in range(50)
    )
    patcher = patch("boto3.session.Session")
    mock_session = patcher.start()
    session_instance = mock_session.return_value
    conn = MagicMock()
    session_instance.client.return_value = conn
    conn.list_principal_policies.return_value = {"policies": [policy_ret]}
    conn.detach_principal_policy.side_effect = ClientError(
        error_content, "detach_principal_policy"
    )
    result = boto_iot.__states__["boto_iot.policy_detached"](
        "test", policy_ret["policyName"], principal
    )
    assert not result["result"]
    assert result["changes"] == {}


def test_present_when_topic_rule_does_not_exist():
    """
    Tests present on a topic_rule that does not exist.
    """
    conn_parameters["key"] = "".join(
        random.choice(string.ascii_lowercase + string.digits) for _ in range(50)
    )
    patcher = patch("boto3.session.Session")
    mock_session = patcher.start()
    session_instance = mock_session.return_value
    conn = MagicMock()
    session_instance.client.return_value = conn
    conn.get_topic_rule.side_effect = [
        topic_rule_not_found_error,
        {"rule": topic_rule_ret},
    ]
    conn.create_topic_rule.return_value = {"created": True}
    result = boto_iot.__states__["boto_iot.topic_rule_present"](
        "topic rule present",
        ruleName=topic_rule_ret["ruleName"],
        sql=topic_rule_ret["sql"],
        description=topic_rule_ret["description"],
        actions=topic_rule_ret["actions"],
        ruleDisabled=topic_rule_ret["ruleDisabled"],
    )

    assert result["result"]
    assert result["changes"]["new"]["rule"]["ruleName"] == topic_rule_ret["ruleName"]


def test_present_when_next_policy_exists():
    conn_parameters["key"] = "".join(
        random.choice(string.ascii_lowercase + string.digits) for _ in range(50)
    )
    patcher = patch("boto3.session.Session")
    mock_session = patcher.start()
    session_instance = mock_session.return_value
    conn = MagicMock()
    session_instance.client.return_value = conn
    conn.get_topic_rule.return_value = {"rule": topic_rule_ret}
    conn.create_topic_rule.return_value = {"created": True}
    result = boto_iot.__states__["boto_iot.topic_rule_present"](
        "topic rule present",
        ruleName=topic_rule_ret["ruleName"],
        sql=topic_rule_ret["sql"],
        description=topic_rule_ret["description"],
        actions=topic_rule_ret["actions"],
        ruleDisabled=topic_rule_ret["ruleDisabled"],
    )
    assert result["result"]
    assert result["changes"] == {}


def test_present_next_with_failure():
    conn_parameters["key"] = "".join(
        random.choice(string.ascii_lowercase + string.digits) for _ in range(50)
    )
    patcher = patch("boto3.session.Session")
    mock_session = patcher.start()
    session_instance = mock_session.return_value
    conn = MagicMock()
    session_instance.client.return_value = conn
    conn.get_topic_rule.side_effect = [
        topic_rule_not_found_error,
        {"rule": topic_rule_ret},
    ]
    conn.create_topic_rule.side_effect = ClientError(error_content, "create_topic_rule")
    result = boto_iot.__states__["boto_iot.topic_rule_present"](
        "topic rule present",
        ruleName=topic_rule_ret["ruleName"],
        sql=topic_rule_ret["sql"],
        description=topic_rule_ret["description"],
        actions=topic_rule_ret["actions"],
        ruleDisabled=topic_rule_ret["ruleDisabled"],
    )
    assert not result["result"]
    assert "An error occurred" in result["comment"]


def test_absent_when_topic_rule_does_not_exist():
    """
    Tests absent on a topic rule that does not exist.
    """
    conn_parameters["key"] = "".join(
        random.choice(string.ascii_lowercase + string.digits) for _ in range(50)
    )
    patcher = patch("boto3.session.Session")
    mock_session = patcher.start()
    session_instance = mock_session.return_value
    conn = MagicMock()
    session_instance.client.return_value = conn
    conn.get_topic_rule.side_effect = topic_rule_not_found_error
    result = boto_iot.__states__["boto_iot.topic_rule_absent"]("test", "myrule")
    assert result["result"]
    assert result["changes"] == {}


def test_absent_when_topic_rule_exists():
    conn_parameters["key"] = "".join(
        random.choice(string.ascii_lowercase + string.digits) for _ in range(50)
    )
    patcher = patch("boto3.session.Session")
    mock_session = patcher.start()
    session_instance = mock_session.return_value
    conn = MagicMock()
    session_instance.client.return_value = conn
    conn.get_topic_rule.return_value = topic_rule_ret
    result = boto_iot.__states__["boto_iot.topic_rule_absent"](
        "test", topic_rule_ret["ruleName"]
    )
    assert result["result"]
    assert result["changes"]["new"]["rule"] is None


def test_absent_next_with_failure():
    conn_parameters["key"] = "".join(
        random.choice(string.ascii_lowercase + string.digits) for _ in range(50)
    )
    patcher = patch("boto3.session.Session")
    mock_session = patcher.start()
    session_instance = mock_session.return_value
    conn = MagicMock()
    session_instance.client.return_value = conn
    conn.get_topic_rule.return_value = topic_rule_ret
    conn.delete_topic_rule.side_effect = ClientError(error_content, "delete_topic_rule")
    result = boto_iot.__states__["boto_iot.topic_rule_absent"](
        "test", topic_rule_ret["ruleName"]
    )
    assert not result["result"]
    assert "An error occurred" in result["comment"]
