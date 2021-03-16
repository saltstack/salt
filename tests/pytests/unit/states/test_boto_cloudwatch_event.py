import logging
import random
import string

import pytest
import salt.config
import salt.loader
import salt.states.boto_cloudwatch_event as boto_cloudwatch_event
from tests.support.mock import MagicMock, patch

# pylint: disable=unused-import
try:
    import boto3
    from botocore.exceptions import ClientError

    HAS_BOTO = True
except ImportError:
    HAS_BOTO = False
# pylint: enable=unused-import


# pylint: enable=import-error,no-name-in-module

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
error_content = {"Error": {"Code": 101, "Message": "Test-defined error"}}
if HAS_BOTO:
    not_found_error = ClientError(
        {
            "Error": {
                "Code": "ResourceNotFoundException",
                "Message": "Test-defined error",
            }
        },
        "msg",
    )
rule_name = "test_thing_type"
rule_desc = "test_thing_type_desc"
rule_sched = "rate(20 min)"
rule_arn = "arn:::::rule/arn"
rule_ret = dict(
    Arn=rule_arn,
    Description=rule_desc,
    EventPattern=None,
    Name=rule_name,
    RoleArn=None,
    ScheduleExpression=rule_sched,
    State="ENABLED",
)


log = logging.getLogger(__name__)


def _has_required_boto():
    """
    Returns True/False boolean depending on if Boto is installed and correct
    version.
    """
    if not HAS_BOTO:
        return False
    else:
        return True


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
        opts, context=ctx, utils=utils, whitelist=["boto_cloudwatch_event"]
    )
    salt_states = salt.loader.states(
        opts=opts,
        functions=funcs,
        utils=utils,
        whitelist=["boto_cloudwatch_event"],
        serializers=serializers,
    )
    return {
        boto_cloudwatch_event: {
            "__opts__": opts,
            "__salt__": funcs,
            "__utils__": utils,
            "__states__": salt_states,
            "__serializers__": serializers,
        }
    }


@pytest.mark.skipif(HAS_BOTO is False, reason="The boto module must be installed.")
def test_present_when_failing_to_describe_rule():
    """
    Tests exceptions when checking rule existence
    """
    conn_parameters["key"] = "".join(
        random.choice(string.ascii_lowercase + string.digits) for _ in range(50)
    )
    patcher = patch("boto3.session.Session")
    mock_session = patcher.start()
    session_instance = mock_session.return_value
    conn = MagicMock()
    session_instance.client.return_value = conn
    conn.list_rules.side_effect = ClientError(error_content, "error on list rules")
    result = boto_cloudwatch_event.__states__["boto_cloudwatch_event.present"](
        name="test present",
        Name=rule_name,
        Description=rule_desc,
        ScheduleExpression=rule_sched,
        Targets=[{"Id": "target1", "Arn": "arn::::::*"}],
        **conn_parameters
    )
    assert result.get("result") is False
    assert "error on list rules" in result.get("comment", {})


def test_present_when_failing_to_create_a_new_rule():
    """
    Tests present on a rule name that doesn't exist and
    an error is thrown on creation.
    """
    conn_parameters["key"] = "".join(
        random.choice(string.ascii_lowercase + string.digits) for _ in range(50)
    )
    patcher = patch("boto3.session.Session")
    mock_session = patcher.start()
    session_instance = mock_session.return_value
    conn = MagicMock()
    session_instance.client.return_value = conn
    conn.list_rules.return_value = {"Rules": []}
    conn.put_rule.side_effect = ClientError(error_content, "put_rule")
    result = boto_cloudwatch_event.__states__["boto_cloudwatch_event.present"](
        name="test present",
        Name=rule_name,
        Description=rule_desc,
        ScheduleExpression=rule_sched,
        Targets=[{"Id": "target1", "Arn": "arn::::::*"}],
        **conn_parameters
    )
    assert result.get("result") is False
    assert "put_rule" in result.get("comment", "")


def test_present_when_failing_to_describe_the_new_rule():
    """
    Tests present on a rule name that doesn't exist and
    an error is thrown when adding targets.
    """
    conn_parameters["key"] = "".join(
        random.choice(string.ascii_lowercase + string.digits) for _ in range(50)
    )
    patcher = patch("boto3.session.Session")
    mock_session = patcher.start()
    session_instance = mock_session.return_value
    conn = MagicMock()
    session_instance.client.return_value = conn
    conn.list_rules.return_value = {"Rules": []}
    conn.put_rule.return_value = rule_ret
    conn.describe_rule.side_effect = ClientError(error_content, "describe_rule")
    result = boto_cloudwatch_event.__states__["boto_cloudwatch_event.present"](
        name="test present",
        Name=rule_name,
        Description=rule_desc,
        ScheduleExpression=rule_sched,
        Targets=[{"Id": "target1", "Arn": "arn::::::*"}],
        **conn_parameters
    )
    assert result.get("result") is False
    assert "describe_rule" in result.get("comment", "")


def test_present_when_failing_to_create_a_new_rules_targets():
    """
    Tests present on a rule name that doesn't exist and
    an error is thrown when adding targets.
    """
    conn_parameters["key"] = "".join(
        random.choice(string.ascii_lowercase + string.digits) for _ in range(50)
    )
    patcher = patch("boto3.session.Session")
    mock_session = patcher.start()
    session_instance = mock_session.return_value
    conn = MagicMock()
    session_instance.client.return_value = conn
    conn.list_rules.return_value = {"Rules": []}
    conn.put_rule.return_value = rule_ret
    conn.describe_rule.return_value = rule_ret
    conn.put_targets.side_effect = ClientError(error_content, "put_targets")
    result = boto_cloudwatch_event.__states__["boto_cloudwatch_event.present"](
        name="test present",
        Name=rule_name,
        Description=rule_desc,
        ScheduleExpression=rule_sched,
        Targets=[{"Id": "target1", "Arn": "arn::::::*"}],
        **conn_parameters
    )
    assert result.get("result") is False
    assert "put_targets" in result.get("comment", "")


def test_present_when_rule_does_not_exist():
    """
    Tests the successful case of creating a new rule, and updating its
    targets
    """
    conn_parameters["key"] = "".join(
        random.choice(string.ascii_lowercase + string.digits) for _ in range(50)
    )
    patcher = patch("boto3.session.Session")
    mock_session = patcher.start()
    session_instance = mock_session.return_value
    conn = MagicMock()
    session_instance.client.return_value = conn
    conn.list_rules.return_value = {"Rules": []}
    conn.put_rule.return_value = rule_ret
    conn.describe_rule.return_value = rule_ret
    conn.put_targets.return_value = {"FailedEntryCount": 0}
    result = boto_cloudwatch_event.__states__["boto_cloudwatch_event.present"](
        name="test present",
        Name=rule_name,
        Description=rule_desc,
        ScheduleExpression=rule_sched,
        Targets=[{"Id": "target1", "Arn": "arn::::::*"}],
        **conn_parameters
    )
    assert result.get("result") is True


def test_present_when_failing_to_update_an_existing_rule():
    """
    Tests present on an existing rule where an error is thrown on updating the pool properties.
    """
    conn_parameters["key"] = "".join(
        random.choice(string.ascii_lowercase + string.digits) for _ in range(50)
    )
    patcher = patch("boto3.session.Session")
    mock_session = patcher.start()
    session_instance = mock_session.return_value
    conn = MagicMock()
    session_instance.client.return_value = conn
    conn.list_rules.return_value = {"Rules": [rule_ret]}
    conn.describe_rule.side_effect = ClientError(error_content, "describe_rule")
    result = boto_cloudwatch_event.__states__["boto_cloudwatch_event.present"](
        name="test present",
        Name=rule_name,
        Description=rule_desc,
        ScheduleExpression=rule_sched,
        Targets=[{"Id": "target1", "Arn": "arn::::::*"}],
        **conn_parameters
    )
    assert result.get("result") is False
    assert "describe_rule" in result.get("comment", "")


def test_present_when_failing_to_get_targets():
    """
    Tests present on an existing rule where put_rule succeeded, but an error
    is thrown on getting targets
    """
    conn_parameters["key"] = "".join(
        random.choice(string.ascii_lowercase + string.digits) for _ in range(50)
    )
    patcher = patch("boto3.session.Session")
    mock_session = patcher.start()
    session_instance = mock_session.return_value
    conn = MagicMock()
    session_instance.client.return_value = conn
    conn.list_rules.return_value = {"Rules": [rule_ret]}
    conn.put_rule.return_value = rule_ret
    conn.describe_rule.return_value = rule_ret
    conn.list_targets_by_rule.side_effect = ClientError(error_content, "list_targets")
    result = boto_cloudwatch_event.__states__["boto_cloudwatch_event.present"](
        name="test present",
        Name=rule_name,
        Description=rule_desc,
        ScheduleExpression=rule_sched,
        Targets=[{"Id": "target1", "Arn": "arn::::::*"}],
        **conn_parameters
    )
    assert result.get("result") is False
    assert "list_targets" in result.get("comment", "")


def test_present_when_failing_to_put_targets():
    """
    Tests present on an existing rule where put_rule succeeded, but an error
    is thrown on putting targets
    """
    conn_parameters["key"] = "".join(
        random.choice(string.ascii_lowercase + string.digits) for _ in range(50)
    )
    patcher = patch("boto3.session.Session")
    mock_session = patcher.start()
    session_instance = mock_session.return_value
    conn = MagicMock()
    session_instance.client.return_value = conn
    conn.list_rules.return_value = {"Rules": []}
    conn.put_rule.return_value = rule_ret
    conn.describe_rule.return_value = rule_ret
    conn.list_targets.return_value = {"Targets": []}
    conn.put_targets.side_effect = ClientError(error_content, "put_targets")
    result = boto_cloudwatch_event.__states__["boto_cloudwatch_event.present"](
        name="test present",
        Name=rule_name,
        Description=rule_desc,
        ScheduleExpression=rule_sched,
        Targets=[{"Id": "target1", "Arn": "arn::::::*"}],
        **conn_parameters
    )
    assert result.get("result") is False
    assert "put_targets" in result.get("comment", "")


def test_present_when_putting_targets():
    """
    Tests present on an existing rule where put_rule succeeded, and targets
    must be added
    """
    conn_parameters["key"] = "".join(
        random.choice(string.ascii_lowercase + string.digits) for _ in range(50)
    )
    patcher = patch("boto3.session.Session")
    mock_session = patcher.start()
    session_instance = mock_session.return_value
    conn = MagicMock()
    session_instance.client.return_value = conn
    conn.list_rules.return_value = {"Rules": []}
    conn.put_rule.return_value = rule_ret
    conn.describe_rule.return_value = rule_ret
    conn.list_targets.return_value = {"Targets": []}
    conn.put_targets.return_value = {"FailedEntryCount": 0}
    result = boto_cloudwatch_event.__states__["boto_cloudwatch_event.present"](
        name="test present",
        Name=rule_name,
        Description=rule_desc,
        ScheduleExpression=rule_sched,
        Targets=[{"Id": "target1", "Arn": "arn::::::*"}],
        **conn_parameters
    )
    assert result.get("result") is True


def test_present_when_removing_targets():
    """
    Tests present on an existing rule where put_rule succeeded, and targets
    must be removed
    """
    conn_parameters["key"] = "".join(
        random.choice(string.ascii_lowercase + string.digits) for _ in range(50)
    )
    patcher = patch("boto3.session.Session")
    mock_session = patcher.start()
    session_instance = mock_session.return_value
    conn = MagicMock()
    session_instance.client.return_value = conn
    conn.list_rules.return_value = {"Rules": []}
    conn.put_rule.return_value = rule_ret
    conn.describe_rule.return_value = rule_ret
    conn.list_targets.return_value = {"Targets": [{"Id": "target1"}, {"Id": "target2"}]}
    conn.put_targets.return_value = {"FailedEntryCount": 0}
    result = boto_cloudwatch_event.__states__["boto_cloudwatch_event.present"](
        name="test present",
        Name=rule_name,
        Description=rule_desc,
        ScheduleExpression=rule_sched,
        Targets=[{"Id": "target1", "Arn": "arn::::::*"}],
        **conn_parameters
    )
    assert result.get("result") is True


def test_absent_when_failing_to_describe_rule():
    """
    Tests exceptions when checking rule existence
    """
    conn_parameters["key"] = "".join(
        random.choice(string.ascii_lowercase + string.digits) for _ in range(50)
    )
    patcher = patch("boto3.session.Session")
    mock_session = patcher.start()
    session_instance = mock_session.return_value
    conn = MagicMock()
    session_instance.client.return_value = conn
    conn.list_rules.side_effect = ClientError(error_content, "error on list rules")
    result = boto_cloudwatch_event.__states__["boto_cloudwatch_event.absent"](
        name="test present", Name=rule_name, **conn_parameters
    )
    assert result.get("result") is False
    assert "error on list rules" in result.get("comment", {})


def test_absent_when_rule_does_not_exist():
    """
    Tests absent on an non-existing rule
    """
    conn_parameters["key"] = "".join(
        random.choice(string.ascii_lowercase + string.digits) for _ in range(50)
    )
    patcher = patch("boto3.session.Session")
    mock_session = patcher.start()
    session_instance = mock_session.return_value
    conn = MagicMock()
    session_instance.client.return_value = conn
    conn.list_rules.return_value = {"Rules": []}
    result = boto_cloudwatch_event.__states__["boto_cloudwatch_event.absent"](
        name="test absent", Name=rule_name, **conn_parameters
    )
    assert result.get("result") is True
    assert result["changes"] == {}


def test_absent_when_failing_to_list_targets():
    """
    Tests absent on an rule when the list_targets call fails
    """
    conn_parameters["key"] = "".join(
        random.choice(string.ascii_lowercase + string.digits) for _ in range(50)
    )
    patcher = patch("boto3.session.Session")
    mock_session = patcher.start()
    session_instance = mock_session.return_value
    conn = MagicMock()
    session_instance.client.return_value = conn
    conn.list_rules.return_value = {"Rules": [rule_ret]}
    conn.list_targets_by_rule.side_effect = ClientError(error_content, "list_targets")
    result = boto_cloudwatch_event.__states__["boto_cloudwatch_event.absent"](
        name="test absent", Name=rule_name, **conn_parameters
    )
    assert result.get("result") is False
    assert "list_targets" in result.get("comment", "")


def test_absent_when_failing_to_remove_targets_exception():
    """
    Tests absent on an rule when the remove_targets call fails
    """
    conn_parameters["key"] = "".join(
        random.choice(string.ascii_lowercase + string.digits) for _ in range(50)
    )
    patcher = patch("boto3.session.Session")
    mock_session = patcher.start()
    session_instance = mock_session.return_value
    conn = MagicMock()
    session_instance.client.return_value = conn
    conn.list_rules.return_value = {"Rules": [rule_ret]}
    conn.list_targets_by_rule.return_value = {"Targets": [{"Id": "target1"}]}
    conn.remove_targets.side_effect = ClientError(error_content, "remove_targets")
    result = boto_cloudwatch_event.__states__["boto_cloudwatch_event.absent"](
        name="test absent", Name=rule_name, **conn_parameters
    )
    assert result.get("result") is False
    assert "remove_targets" in result.get("comment", "")


def test_absent_when_failing_to_remove_targets_nonexception():
    """
    Tests absent on an rule when the remove_targets call fails
    """
    conn_parameters["key"] = "".join(
        random.choice(string.ascii_lowercase + string.digits) for _ in range(50)
    )
    patcher = patch("boto3.session.Session")
    mock_session = patcher.start()
    session_instance = mock_session.return_value
    conn = MagicMock()
    session_instance.client.return_value = conn
    conn.list_rules.return_value = {"Rules": [rule_ret]}
    conn.list_targets_by_rule.return_value = {"Targets": [{"Id": "target1"}]}
    conn.remove_targets.return_value = {"FailedEntryCount": 1}
    result = boto_cloudwatch_event.__states__["boto_cloudwatch_event.absent"](
        name="test absent", Name=rule_name, **conn_parameters
    )
    assert result.get("result") is False


def test_absent_when_failing_to_delete_rule():
    """
    Tests absent on an rule when the delete_rule call fails
    """
    conn_parameters["key"] = "".join(
        random.choice(string.ascii_lowercase + string.digits) for _ in range(50)
    )
    patcher = patch("boto3.session.Session")
    mock_session = patcher.start()
    session_instance = mock_session.return_value
    conn = MagicMock()
    session_instance.client.return_value = conn
    conn.list_rules.return_value = {"Rules": [rule_ret]}
    conn.list_targets_by_rule.return_value = {"Targets": [{"Id": "target1"}]}
    conn.remove_targets.return_value = {"FailedEntryCount": 0}
    conn.delete_rule.side_effect = ClientError(error_content, "delete_rule")
    result = boto_cloudwatch_event.__states__["boto_cloudwatch_event.absent"](
        name="test absent", Name=rule_name, **conn_parameters
    )
    assert result.get("result") is False
    assert "delete_rule" in result.get("comment", "")


def test_absent():
    """
    Tests absent on an rule
    """
    conn_parameters["key"] = "".join(
        random.choice(string.ascii_lowercase + string.digits) for _ in range(50)
    )
    patcher = patch("boto3.session.Session")
    mock_session = patcher.start()
    session_instance = mock_session.return_value
    conn = MagicMock()
    session_instance.client.return_value = conn
    conn.list_rules.return_value = {"Rules": [rule_ret]}
    conn.list_targets_by_rule.return_value = {"Targets": [{"Id": "target1"}]}
    conn.remove_targets.return_value = {"FailedEntryCount": 0}
    result = boto_cloudwatch_event.__states__["boto_cloudwatch_event.absent"](
        name="test absent", Name=rule_name, **conn_parameters
    )
    assert result.get("result") is True
