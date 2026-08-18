import logging
import random
import string

import pytest

import salt.config
import salt.loader
import salt.states.boto_lambda as boto_lambda
import salt.utils.json
from tests.support.mock import MagicMock, patch

# pylint: disable=import-error,no-name-in-module
from tests.unit.modules.test_boto_lambda import TempZipFile

boto = pytest.importorskip("boto")
boto3 = pytest.importorskip("boto3", "1.2.1")
botocore = pytest.importorskip("botocore", "1.5.2")

log = logging.getLogger(__name__)


pytestmark = [
    pytest.mark.slow_test,
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
    function_ret = dict(
        FunctionName="testfunction",
        Runtime="python2.7",
        Role="arn:aws:iam::1234:role/functionrole",
        Handler="handler",
        Description="abcdefg",
        Timeout=5,
        MemorySize=128,
        CodeSha256="abcdef",
        CodeSize=199,
        FunctionArn="arn:lambda:us-east-1:1234:Something",
        LastModified="yes",
        VpcConfig={"SubnetIds": [], "SecurityGroupIds": []},
    )
    alias_ret = dict(
        AliasArn="arn:lambda:us-east-1:1234:Something",
        Name="testalias",
        FunctionVersion="3",
        Description="Alias description",
    )
    event_source_mapping_ret = dict(
        UUID="1234-1-123",
        BatchSize=123,
        EventSourceArn="arn:aws:dynamodb:us-east-1:1234::Something",
        FunctionArn="arn:aws:lambda:us-east-1:1234:function:myfunc",
        LastModified="yes",
        LastProcessingResult="SUCCESS",
        State="Enabled",
        StateTransitionReason="Random",
    )


@pytest.fixture
def global_config():
    GlobalConfig.conn_parameters["key"] = "".join(
        random.choice(string.ascii_lowercase + string.digits) for _ in range(50)
    )
    params = GlobalConfig()
    return params


@pytest.fixture
def session_instance():
    with patch("boto3.session.Session") as patched_session:
        yield patched_session()


@pytest.fixture
def configure_loader_modules(minion_opts):
    minion_opts["grains"] = salt.loader.grains(minion_opts)
    ctx = {}
    utils = salt.loader.utils(
        minion_opts,
        whitelist=["boto", "boto3", "args", "systemd", "path", "platform", "reg"],
        context=ctx,
    )
    serializers = salt.loader.serializers(minion_opts)
    funcs = salt.loader.minion_mods(
        minion_opts, context=ctx, utils=utils, whitelist=["boto_lambda"]
    )
    salt_states = salt.loader.states(
        opts=minion_opts,
        functions=funcs,
        utils=utils,
        whitelist=["boto_lambda"],
        serializers=serializers,
    )
    return {
        boto_lambda: {
            "__opts__": minion_opts,
            "__salt__": funcs,
            "__utils__": utils,
            "__states__": salt_states,
            "__serializers__": serializers,
        }
    }


@pytest.mark.slow_test
def test_present_when_function_does_not_exist_func(global_config, session_instance):
    """
    Tests present on a function that does not exist.
    """
    conn = MagicMock()
    session_instance.client.return_value = conn

    conn.list_functions.side_effect = [
        {"Functions": []},
        {"Functions": [global_config.function_ret]},
    ]
    conn.create_function.return_value = global_config.function_ret
    with patch.dict(
        boto_lambda.__salt__,
        {"boto_iam.get_account_id": MagicMock(return_value="1234")},
    ):
        with TempZipFile() as zipfile:
            result = boto_lambda.__states__["boto_lambda.function_present"](
                "function present",
                FunctionName=global_config.function_ret["FunctionName"],
                Runtime=global_config.function_ret["Runtime"],
                Role=global_config.function_ret["Role"],
                Handler=global_config.function_ret["Handler"],
                ZipFile=zipfile,
            )

    assert result["result"]
    assert (
        result["changes"]["new"]["function"]["FunctionName"]
        == global_config.function_ret["FunctionName"]
    )


@pytest.mark.slow_test
def test_present_when_function_exists_func(global_config, session_instance):
    conn = MagicMock()
    session_instance.client.return_value = conn

    conn.list_functions.return_value = {"Functions": [global_config.function_ret]}
    conn.update_function_code.return_value = global_config.function_ret

    with patch.dict(
        boto_lambda.__salt__,
        {"boto_iam.get_account_id": MagicMock(return_value="1234")},
    ):
        with TempZipFile() as zipfile:
            with patch("hashlib.sha256") as sha256:
                with patch("os.path.getsize", return_value=199):
                    sha = sha256()
                    digest = sha.digest()
                    encoded = sha.encode()
                    encoded.strip.return_value = global_config.function_ret[
                        "CodeSha256"
                    ]
                    result = boto_lambda.__states__["boto_lambda.function_present"](
                        "function present",
                        FunctionName=global_config.function_ret["FunctionName"],
                        Runtime=global_config.function_ret["Runtime"],
                        Role=global_config.function_ret["Role"],
                        Handler=global_config.function_ret["Handler"],
                        ZipFile=zipfile,
                        Description=global_config.function_ret["Description"],
                        Timeout=global_config.function_ret["Timeout"],
                    )
    assert result["result"]
    assert result["changes"] == {}


@pytest.mark.slow_test
def test_present_with_failure_func(global_config, session_instance):
    conn = MagicMock()
    session_instance.client.return_value = conn

    conn.list_functions.side_effect = [
        {"Functions": []},
        {"Functions": [global_config.function_ret]},
    ]
    conn.create_function.side_effect = botocore.exceptions.ClientError(
        global_config.error_content, "create_function"
    )
    with patch.dict(
        boto_lambda.__salt__,
        {"boto_iam.get_account_id": MagicMock(return_value="1234")},
    ):
        with TempZipFile() as zipfile:
            with patch("hashlib.sha256") as sha256:
                with patch("os.path.getsize", return_value=199):
                    sha = sha256()
                    digest = sha.digest()
                    encoded = sha.encode()
                    encoded.strip.return_value = global_config.function_ret[
                        "CodeSha256"
                    ]
                    result = boto_lambda.__states__["boto_lambda.function_present"](
                        "function present",
                        FunctionName=global_config.function_ret["FunctionName"],
                        Runtime=global_config.function_ret["Runtime"],
                        Role=global_config.function_ret["Role"],
                        Handler=global_config.function_ret["Handler"],
                        ZipFile=zipfile,
                        Description=global_config.function_ret["Description"],
                        Timeout=global_config.function_ret["Timeout"],
                    )
    assert not result["result"]
    assert "An error occurred" in result["comment"]


def test_absent_when_function_does_not_exist_func(global_config, session_instance):
    """
    Tests absent on a function that does not exist.
    """
    conn = MagicMock()
    session_instance.client.return_value = conn

    conn.list_functions.return_value = {"Functions": [global_config.function_ret]}
    result = boto_lambda.__states__["boto_lambda.function_absent"]("test", "myfunc")
    assert result["result"]
    assert result["changes"] == {}


def test_absent_when_function_exists_func(global_config, session_instance):
    conn = MagicMock()
    session_instance.client.return_value = conn

    conn.list_functions.return_value = {"Functions": [global_config.function_ret]}
    result = boto_lambda.__states__["boto_lambda.function_absent"](
        "test", global_config.function_ret["FunctionName"]
    )
    assert result["result"]
    assert result["changes"]["new"]["function"] is None


def test_absent_with_failure_func(global_config, session_instance):
    conn = MagicMock()
    session_instance.client.return_value = conn

    conn.list_functions.return_value = {"Functions": [global_config.function_ret]}
    conn.delete_function.side_effect = botocore.exceptions.ClientError(
        global_config.error_content, "delete_function"
    )
    result = boto_lambda.__states__["boto_lambda.function_absent"](
        "test", global_config.function_ret["FunctionName"]
    )
    assert not result["result"]
    assert "An error occurred" in result["comment"]


@pytest.mark.slow_test
def test_present_when_function_exists_and_permissions_func(
    global_config, session_instance
):
    conn = MagicMock()
    session_instance.client.return_value = conn

    conn.list_functions.return_value = {"Functions": [global_config.function_ret]}
    conn.update_function_code.return_value = global_config.function_ret
    conn.get_policy.return_value = {
        "Policy": salt.utils.json.dumps(
            {
                "Version": "2012-10-17",
                "Statement": [
                    {
                        "Condition": {
                            "ArnLike": {
                                "AWS:SourceArn": (
                                    "arn:aws:events:us-east-1:9999999999:rule/fooo"
                                )
                            }
                        },
                        "Action": "lambda:InvokeFunction",
                        "Resource": "arn:aws:lambda:us-east-1:999999999999:function:testfunction",
                        "Effect": "Allow",
                        "Principal": {"Service": "events.amazonaws.com"},
                        "Sid": "AWSEvents_foo-bar999999999999",
                    }
                ],
                "Id": "default",
            }
        )
    }

    with patch.dict(
        boto_lambda.__salt__,
        {"boto_iam.get_account_id": MagicMock(return_value="1234")},
    ):
        with TempZipFile() as zipfile:
            with patch("hashlib.sha256") as sha256:
                with patch("os.path.getsize", return_value=199):
                    sha = sha256()
                    digest = sha.digest()
                    encoded = sha.encode()
                    encoded.strip.return_value = global_config.function_ret[
                        "CodeSha256"
                    ]
                    result = boto_lambda.__states__["boto_lambda.function_present"](
                        "function present",
                        FunctionName=global_config.function_ret["FunctionName"],
                        Runtime=global_config.function_ret["Runtime"],
                        Role=global_config.function_ret["Role"],
                        Handler=global_config.function_ret["Handler"],
                        ZipFile=zipfile,
                        Description=global_config.function_ret["Description"],
                        Timeout=global_config.function_ret["Timeout"],
                    )
    assert result["result"]
    assert result["changes"] == {
        "old": {
            "Permissions": {
                "AWSEvents_foo-bar999999999999": {
                    "Action": "lambda:InvokeFunction",
                    "Principal": "events.amazonaws.com",
                    "SourceArn": "arn:aws:events:us-east-1:9999999999:rule/fooo",
                }
            }
        },
        "new": {"Permissions": {"AWSEvents_foo-bar999999999999": {}}},
    }


def test_present_when_alias_does_not_exist(global_config, session_instance):
    """
    Tests present on a alias that does not exist.
    """
    conn = MagicMock()
    session_instance.client.return_value = conn

    conn.list_aliases.side_effect = [
        {"Aliases": []},
        {"Aliases": [global_config.alias_ret]},
    ]
    conn.create_alias.return_value = global_config.alias_ret
    result = boto_lambda.__states__["boto_lambda.alias_present"](
        "alias present",
        FunctionName="testfunc",
        Name=global_config.alias_ret["Name"],
        FunctionVersion=global_config.alias_ret["FunctionVersion"],
    )

    assert result["result"]
    assert result["changes"]["new"]["alias"]["Name"] == global_config.alias_ret["Name"]


def test_present_when_alias_exists(global_config, session_instance):
    conn = MagicMock()
    session_instance.client.return_value = conn

    conn.list_aliases.return_value = {"Aliases": [global_config.alias_ret]}
    conn.create_alias.return_value = global_config.alias_ret
    result = boto_lambda.__states__["boto_lambda.alias_present"](
        "alias present",
        FunctionName="testfunc",
        Name=global_config.alias_ret["Name"],
        FunctionVersion=global_config.alias_ret["FunctionVersion"],
        Description=global_config.alias_ret["Description"],
    )
    assert result["result"]
    assert result["changes"] == {}


@pytest.mark.slow_test
def test_present_with_failure_glob(global_config, session_instance):
    conn = MagicMock()
    session_instance.client.return_value = conn

    conn.list_aliases.side_effect = [
        {"Aliases": []},
        {"Aliases": [global_config.alias_ret]},
    ]
    conn.create_alias.side_effect = botocore.exceptions.ClientError(
        global_config.error_content, "create_alias"
    )
    result = boto_lambda.__states__["boto_lambda.alias_present"](
        "alias present",
        FunctionName="testfunc",
        Name=global_config.alias_ret["Name"],
        FunctionVersion=global_config.alias_ret["FunctionVersion"],
    )
    assert not result["result"]
    assert "An error occurred" in result["comment"]


def test_absent_when_alias_does_not_exist(global_config, session_instance):
    """
    Tests absent on a alias that does not exist.
    """
    conn = MagicMock()
    session_instance.client.return_value = conn

    conn.list_aliases.return_value = {"Aliases": [global_config.alias_ret]}
    result = boto_lambda.__states__["boto_lambda.alias_absent"](
        "alias absent", FunctionName="testfunc", Name="myalias"
    )
    assert result["result"]
    assert result["changes"] == {}


def test_absent_when_alias_exists(global_config, session_instance):
    conn = MagicMock()
    session_instance.client.return_value = conn

    conn.list_aliases.return_value = {"Aliases": [global_config.alias_ret]}
    result = boto_lambda.__states__["boto_lambda.alias_absent"](
        "alias absent", FunctionName="testfunc", Name=global_config.alias_ret["Name"]
    )
    assert result["result"]
    assert result["changes"]["new"]["alias"] is None


def test_absent_with_failure(global_config, session_instance):
    conn = MagicMock()
    session_instance.client.return_value = conn

    conn.list_aliases.return_value = {"Aliases": [global_config.alias_ret]}
    conn.delete_alias.side_effect = botocore.exceptions.ClientError(
        global_config.error_content, "delete_alias"
    )
    result = boto_lambda.__states__["boto_lambda.alias_absent"](
        "alias absent", FunctionName="testfunc", Name=global_config.alias_ret["Name"]
    )
    assert not result["result"]
    assert "An error occurred" in result["comment"]


def test_present_when_event_source_mapping_does_not_exist(
    global_config, session_instance
):
    """
    Tests present on a event_source_mapping that does not exist.
    """
    conn = MagicMock()
    session_instance.client.return_value = conn

    conn.list_event_source_mappings.side_effect = [
        {"EventSourceMappings": []},
        {"EventSourceMappings": [global_config.event_source_mapping_ret]},
    ]
    conn.get_event_source_mapping.return_value = global_config.event_source_mapping_ret
    conn.create_event_source_mapping.return_value = (
        global_config.event_source_mapping_ret
    )
    result = boto_lambda.__states__["boto_lambda.event_source_mapping_present"](
        "event source mapping present",
        EventSourceArn=global_config.event_source_mapping_ret["EventSourceArn"],
        FunctionName="myfunc",
        StartingPosition="LATEST",
    )

    assert result["result"]
    assert (
        result["changes"]["new"]["event_source_mapping"]["UUID"]
        == global_config.event_source_mapping_ret["UUID"]
    )


def test_present_when_event_source_mapping_exists(global_config, session_instance):
    conn = MagicMock()
    session_instance.client.return_value = conn

    conn.list_event_source_mappings.return_value = {
        "EventSourceMappings": [global_config.event_source_mapping_ret]
    }
    conn.get_event_source_mapping.return_value = global_config.event_source_mapping_ret
    conn.create_event_source_mapping.return_value = (
        global_config.event_source_mapping_ret
    )
    result = boto_lambda.__states__["boto_lambda.event_source_mapping_present"](
        "event source mapping present",
        EventSourceArn=global_config.event_source_mapping_ret["EventSourceArn"],
        FunctionName=global_config.event_source_mapping_ret["FunctionArn"],
        StartingPosition="LATEST",
        BatchSize=global_config.event_source_mapping_ret["BatchSize"],
    )
    assert result["result"]
    assert result["changes"] == {}


@pytest.mark.slow_test
def test_present_with_failure(global_config, session_instance):
    conn = MagicMock()
    session_instance.client.return_value = conn

    conn.list_event_source_mappings.side_effect = [
        {"EventSourceMappings": []},
        {"EventSourceMappings": [global_config.event_source_mapping_ret]},
    ]
    conn.get_event_source_mapping.return_value = global_config.event_source_mapping_ret
    conn.create_event_source_mapping.side_effect = botocore.exceptions.ClientError(
        global_config.error_content, "create_event_source_mapping"
    )
    result = boto_lambda.__states__["boto_lambda.event_source_mapping_present"](
        "event source mapping present",
        EventSourceArn=global_config.event_source_mapping_ret["EventSourceArn"],
        FunctionName=global_config.event_source_mapping_ret["FunctionArn"],
        StartingPosition="LATEST",
        BatchSize=global_config.event_source_mapping_ret["BatchSize"],
    )
    assert not result["result"]
    assert "An error occurred" in result["comment"]


def test_absent_when_event_source_mapping_does_not_exist(
    global_config, session_instance
):
    """
    Tests absent on a event_source_mapping that does not exist.
    """
    conn = MagicMock()
    session_instance.client.return_value = conn

    conn.list_event_source_mappings.return_value = {"EventSourceMappings": []}
    result = boto_lambda.__states__["boto_lambda.event_source_mapping_absent"](
        "event source mapping absent",
        EventSourceArn=global_config.event_source_mapping_ret["EventSourceArn"],
        FunctionName="myfunc",
    )
    assert result["result"]
    assert result["changes"] == {}


def test_absent_when_event_source_mapping_exists(global_config, session_instance):
    conn = MagicMock()
    session_instance.client.return_value = conn

    conn.list_event_source_mappings.return_value = {
        "EventSourceMappings": [global_config.event_source_mapping_ret]
    }
    conn.get_event_source_mapping.return_value = global_config.event_source_mapping_ret
    result = boto_lambda.__states__["boto_lambda.event_source_mapping_absent"](
        "event source mapping absent",
        EventSourceArn=global_config.event_source_mapping_ret["EventSourceArn"],
        FunctionName="myfunc",
    )
    assert result["result"]
    assert result["changes"]["new"]["event_source_mapping"] is None


def test_absent_with_failure_glob(global_config, session_instance):
    conn = MagicMock()
    session_instance.client.return_value = conn

    conn.list_event_source_mappings.return_value = {
        "EventSourceMappings": [global_config.event_source_mapping_ret]
    }
    conn.get_event_source_mapping.return_value = global_config.event_source_mapping_ret
    conn.delete_event_source_mapping.side_effect = botocore.exceptions.ClientError(
        global_config.error_content, "delete_event_source_mapping"
    )
    result = boto_lambda.__states__["boto_lambda.event_source_mapping_absent"](
        "event source mapping absent",
        EventSourceArn=global_config.event_source_mapping_ret["EventSourceArn"],
        FunctionName="myfunc",
    )
    assert not result["result"]
    assert "An error occurred" in result["comment"]
