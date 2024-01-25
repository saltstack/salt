import logging
import random
import string

import pytest

import salt.loader
import salt.states.boto_cloudwatch_event as boto_cloudwatch_event
from tests.support.mock import MagicMock, patch

boto = pytest.importorskip("boto")
boto3 = pytest.importorskip("boto3", "1.2.1")
botocore = pytest.importorskip("botocore", "1.4.41")

log = logging.getLogger(__name__)


pytestmark = [
    pytest.mark.slow_test,
    pytest.mark.skip_on_fips_enabled_platform,
]


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
    error_content = {"Error": {"Code": 101, "Message": "Test-defined error"}}
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


@pytest.fixture
def session_instance():
    with patch("boto3.session.Session") as patched_session:
        yield patched_session()


@pytest.fixture
def global_config():
    GlobalConfig.conn_parameters["key"] = "".join(
        random.choice(string.ascii_lowercase + string.digits) for _ in range(50)
    )
    params = GlobalConfig()
    return params


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
        minion_opts, context=ctx, utils=utils, whitelist=["boto_cloudwatch_event"]
    )
    salt_states = salt.loader.states(
        opts=minion_opts,
        functions=funcs,
        utils=utils,
        whitelist=["boto_cloudwatch_event"],
        serializers=serializers,
    )
    return {
        boto_cloudwatch_event: {
            "__opts__": minion_opts,
            "__salt__": funcs,
            "__utils__": utils,
            "__states__": salt_states,
            "__serializers__": serializers,
        }
    }


def test_present_when_failing_to_describe_rule(global_config, session_instance):
    """
    Tests exceptions when checking rule existence
    """
    conn = MagicMock()
    session_instance.client.return_value = conn
    conn.list_rules.side_effect = botocore.exceptions.ClientError(
        global_config.error_content, "error on list rules"
    )
    result = boto_cloudwatch_event.__states__["boto_cloudwatch_event.present"](
        name="test present",
        Name=global_config.rule_name,
        Description=global_config.rule_desc,
        ScheduleExpression=global_config.rule_sched,
        Targets=[{"Id": "target1", "Arn": "arn::::::*"}],
        **global_config.conn_parameters
    )
    assert result.get("result") is False
    assert "error on list rules" in result.get("comment", {})


def test_present_when_failing_to_create_a_new_rule(global_config, session_instance):
    """
    Tests present on a rule name that doesn't exist and
    an error is thrown on creation.
    """
    conn = MagicMock()
    session_instance.client.return_value = conn
    conn.list_rules.return_value = {"Rules": []}
    conn.put_rule.side_effect = botocore.exceptions.ClientError(
        global_config.error_content, "put_rule"
    )
    result = boto_cloudwatch_event.__states__["boto_cloudwatch_event.present"](
        name="test present",
        Name=global_config.rule_name,
        Description=global_config.rule_desc,
        ScheduleExpression=global_config.rule_sched,
        Targets=[{"Id": "target1", "Arn": "arn::::::*"}],
        **global_config.conn_parameters
    )
    assert result.get("result") is False
    assert "put_rule" in result.get("comment", "")


def test_present_when_failing_to_describe_the_new_rule(global_config, session_instance):
    """
    Tests present on a rule name that doesn't exist and
    an error is thrown when adding targets.
    """
    conn = MagicMock()
    session_instance.client.return_value = conn
    conn.list_rules.return_value = {"Rules": []}
    conn.put_rule.return_value = global_config.rule_ret
    conn.describe_rule.side_effect = botocore.exceptions.ClientError(
        global_config.error_content, "describe_rule"
    )
    result = boto_cloudwatch_event.__states__["boto_cloudwatch_event.present"](
        name="test present",
        Name=global_config.rule_name,
        Description=global_config.rule_desc,
        ScheduleExpression=global_config.rule_sched,
        Targets=[{"Id": "target1", "Arn": "arn::::::*"}],
        **global_config.conn_parameters
    )
    assert result.get("result") is False
    assert "describe_rule" in result.get("comment", "")


def test_present_when_failing_to_create_a_new_rules_targets(
    global_config, session_instance
):
    """
    Tests present on a rule name that doesn't exist and
    an error is thrown when adding targets.
    """
    conn = MagicMock()
    session_instance.client.return_value = conn
    conn.list_rules.return_value = {"Rules": []}
    conn.put_rule.return_value = global_config.rule_ret
    conn.describe_rule.return_value = global_config.rule_ret
    conn.put_targets.side_effect = botocore.exceptions.ClientError(
        global_config.error_content, "put_targets"
    )
    result = boto_cloudwatch_event.__states__["boto_cloudwatch_event.present"](
        name="test present",
        Name=global_config.rule_name,
        Description=global_config.rule_desc,
        ScheduleExpression=global_config.rule_sched,
        Targets=[{"Id": "target1", "Arn": "arn::::::*"}],
        **global_config.conn_parameters
    )
    assert result.get("result") is False
    assert "put_targets" in result.get("comment", "")


def test_present_when_rule_does_not_exist(global_config, session_instance):
    """
    Tests the successful case of creating a new rule, and updating its
    targets
    """
    conn = MagicMock()
    session_instance.client.return_value = conn
    conn.list_rules.return_value = {"Rules": []}
    conn.put_rule.return_value = global_config.rule_ret
    conn.describe_rule.return_value = global_config.rule_ret
    conn.put_targets.return_value = {"FailedEntryCount": 0}
    result = boto_cloudwatch_event.__states__["boto_cloudwatch_event.present"](
        name="test present",
        Name=global_config.rule_name,
        Description=global_config.rule_desc,
        ScheduleExpression=global_config.rule_sched,
        Targets=[{"Id": "target1", "Arn": "arn::::::*"}],
        **global_config.conn_parameters
    )
    assert result.get("result") is True


def test_present_when_failing_to_update_an_existing_rule(
    global_config, session_instance
):
    """
    Tests present on an existing rule where an error is thrown on updating the pool properties.
    """
    conn = MagicMock()
    session_instance.client.return_value = conn
    conn.list_rules.return_value = {"Rules": [global_config.rule_ret]}
    conn.describe_rule.side_effect = botocore.exceptions.ClientError(
        global_config.error_content, "describe_rule"
    )
    result = boto_cloudwatch_event.__states__["boto_cloudwatch_event.present"](
        name="test present",
        Name=global_config.rule_name,
        Description=global_config.rule_desc,
        ScheduleExpression=global_config.rule_sched,
        Targets=[{"Id": "target1", "Arn": "arn::::::*"}],
        **global_config.conn_parameters
    )
    assert result.get("result") is False
    assert "describe_rule" in result.get("comment", "")


def test_present_when_failing_to_get_targets(global_config, session_instance):
    """
    Tests present on an existing rule where put_rule succeeded, but an error
    is thrown on getting targets
    """
    conn = MagicMock()
    session_instance.client.return_value = conn
    conn.list_rules.return_value = {"Rules": [global_config.rule_ret]}
    conn.put_rule.return_value = global_config.rule_ret
    conn.describe_rule.return_value = global_config.rule_ret
    conn.list_targets_by_rule.side_effect = botocore.exceptions.ClientError(
        global_config.error_content, "list_targets"
    )
    result = boto_cloudwatch_event.__states__["boto_cloudwatch_event.present"](
        name="test present",
        Name=global_config.rule_name,
        Description=global_config.rule_desc,
        ScheduleExpression=global_config.rule_sched,
        Targets=[{"Id": "target1", "Arn": "arn::::::*"}],
        **global_config.conn_parameters
    )
    assert result.get("result") is False
    assert "list_targets" in result.get("comment", "")


def test_present_when_failing_to_put_targets(global_config, session_instance):
    """
    Tests present on an existing rule where put_rule succeeded, but an error
    is thrown on putting targets
    """
    conn = MagicMock()
    session_instance.client.return_value = conn
    conn.list_rules.return_value = {"Rules": []}
    conn.put_rule.return_value = global_config.rule_ret
    conn.describe_rule.return_value = global_config.rule_ret
    conn.list_targets.return_value = {"Targets": []}
    conn.put_targets.side_effect = botocore.exceptions.ClientError(
        global_config.error_content, "put_targets"
    )
    result = boto_cloudwatch_event.__states__["boto_cloudwatch_event.present"](
        name="test present",
        Name=global_config.rule_name,
        Description=global_config.rule_desc,
        ScheduleExpression=global_config.rule_sched,
        Targets=[{"Id": "target1", "Arn": "arn::::::*"}],
        **global_config.conn_parameters
    )
    assert result.get("result") is False
    assert "put_targets" in result.get("comment", "")


def test_present_when_putting_targets(global_config, session_instance):
    """
    Tests present on an existing rule where put_rule succeeded, and targets
    must be added
    """
    conn = MagicMock()
    session_instance.client.return_value = conn
    conn.list_rules.return_value = {"Rules": []}
    conn.put_rule.return_value = global_config.rule_ret
    conn.describe_rule.return_value = global_config.rule_ret
    conn.list_targets.return_value = {"Targets": []}
    conn.put_targets.return_value = {"FailedEntryCount": 0}
    result = boto_cloudwatch_event.__states__["boto_cloudwatch_event.present"](
        name="test present",
        Name=global_config.rule_name,
        Description=global_config.rule_desc,
        ScheduleExpression=global_config.rule_sched,
        Targets=[{"Id": "target1", "Arn": "arn::::::*"}],
        **global_config.conn_parameters
    )
    assert result.get("result") is True


def test_present_when_removing_targets(global_config, session_instance):
    """
    Tests present on an existing rule where put_rule succeeded, and targets
    must be removed
    """
    conn = MagicMock()
    session_instance.client.return_value = conn
    conn.list_rules.return_value = {"Rules": []}
    conn.put_rule.return_value = global_config.rule_ret
    conn.describe_rule.return_value = global_config.rule_ret
    conn.list_targets.return_value = {"Targets": [{"Id": "target1"}, {"Id": "target2"}]}
    conn.put_targets.return_value = {"FailedEntryCount": 0}
    result = boto_cloudwatch_event.__states__["boto_cloudwatch_event.present"](
        name="test present",
        Name=global_config.rule_name,
        Description=global_config.rule_desc,
        ScheduleExpression=global_config.rule_sched,
        Targets=[{"Id": "target1", "Arn": "arn::::::*"}],
        **global_config.conn_parameters
    )
    assert result.get("result") is True


def test_absent_when_failing_to_describe_rule(global_config, session_instance):
    """
    Tests exceptions when checking rule existence
    """
    conn = MagicMock()
    session_instance.client.return_value = conn
    conn.list_rules.side_effect = botocore.exceptions.ClientError(
        global_config.error_content, "error on list rules"
    )
    result = boto_cloudwatch_event.__states__["boto_cloudwatch_event.absent"](
        name="test present",
        Name=global_config.rule_name,
        **global_config.conn_parameters
    )
    assert result.get("result") is False
    assert "error on list rules" in result.get("comment", {})


def test_absent_when_rule_does_not_exist(global_config, session_instance):
    """
    Tests absent on an non-existing rule
    """
    conn = MagicMock()
    session_instance.client.return_value = conn
    conn.list_rules.return_value = {"Rules": []}
    result = boto_cloudwatch_event.__states__["boto_cloudwatch_event.absent"](
        name="test absent",
        Name=global_config.rule_name,
        **global_config.conn_parameters
    )
    assert result.get("result") is True
    assert result["changes"] == {}


def test_absent_when_failing_to_list_targets(global_config, session_instance):
    """
    Tests absent on an rule when the list_targets call fails
    """
    conn = MagicMock()
    session_instance.client.return_value = conn
    conn.list_rules.return_value = {"Rules": [global_config.rule_ret]}
    conn.list_targets_by_rule.side_effect = botocore.exceptions.ClientError(
        global_config.error_content, "list_targets"
    )
    result = boto_cloudwatch_event.__states__["boto_cloudwatch_event.absent"](
        name="test absent",
        Name=global_config.rule_name,
        **global_config.conn_parameters
    )
    assert result.get("result") is False
    assert "list_targets" in result.get("comment", "")


def test_absent_when_failing_to_remove_targets_exception(
    global_config, session_instance
):
    """
    Tests absent on an rule when the remove_targets call fails
    """
    conn = MagicMock()
    session_instance.client.return_value = conn
    conn.list_rules.return_value = {"Rules": [global_config.rule_ret]}
    conn.list_targets_by_rule.return_value = {"Targets": [{"Id": "target1"}]}
    conn.remove_targets.side_effect = botocore.exceptions.ClientError(
        global_config.error_content, "remove_targets"
    )
    result = boto_cloudwatch_event.__states__["boto_cloudwatch_event.absent"](
        name="test absent",
        Name=global_config.rule_name,
        **global_config.conn_parameters
    )
    assert result.get("result") is False
    assert "remove_targets" in result.get("comment", "")


def test_absent_when_failing_to_remove_targets_nonexception(
    global_config, session_instance
):
    """
    Tests absent on an rule when the remove_targets call fails
    """
    conn = MagicMock()
    session_instance.client.return_value = conn
    conn.list_rules.return_value = {"Rules": [global_config.rule_ret]}
    conn.list_targets_by_rule.return_value = {"Targets": [{"Id": "target1"}]}
    conn.remove_targets.return_value = {"FailedEntryCount": 1}
    result = boto_cloudwatch_event.__states__["boto_cloudwatch_event.absent"](
        name="test absent",
        Name=global_config.rule_name,
        **global_config.conn_parameters
    )
    assert result.get("result") is False


def test_absent_when_failing_to_delete_rule(global_config, session_instance):
    """
    Tests absent on an rule when the delete_rule call fails
    """
    conn = MagicMock()
    session_instance.client.return_value = conn
    conn.list_rules.return_value = {"Rules": [global_config.rule_ret]}
    conn.list_targets_by_rule.return_value = {"Targets": [{"Id": "target1"}]}
    conn.remove_targets.return_value = {"FailedEntryCount": 0}
    conn.delete_rule.side_effect = botocore.exceptions.ClientError(
        global_config.error_content, "delete_rule"
    )
    result = boto_cloudwatch_event.__states__["boto_cloudwatch_event.absent"](
        name="test absent",
        Name=global_config.rule_name,
        **global_config.conn_parameters
    )
    assert result.get("result") is False
    assert "delete_rule" in result.get("comment", "")


def test_absent(global_config, session_instance):
    """
    Tests absent on an rule
    """
    conn = MagicMock()
    session_instance.client.return_value = conn
    conn.list_rules.return_value = {"Rules": [global_config.rule_ret]}
    conn.list_targets_by_rule.return_value = {"Targets": [{"Id": "target1"}]}
    conn.remove_targets.return_value = {"FailedEntryCount": 0}
    result = boto_cloudwatch_event.__states__["boto_cloudwatch_event.absent"](
        name="test absent",
        Name=global_config.rule_name,
        **global_config.conn_parameters
    )
    assert result.get("result") is True
