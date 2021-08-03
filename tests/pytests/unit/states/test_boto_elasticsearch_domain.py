import logging
import random
import string

import pytest
import salt.config
import salt.loader
import salt.states.boto_elasticsearch_domain as boto_elasticsearch_domain
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
    error_content = {"Error": {"Code": 101, "Message": "Test-defined error"}}
    domain_ret = dict(
        DomainName="testdomain",
        ElasticsearchClusterConfig={},
        EBSOptions={},
        AccessPolicies={},
        SnapshotOptions={},
        AdvancedOptions={},
        ElasticsearchVersion="1.5",
    )


@pytest.fixture
def configure_loader_modules():
    opts = salt.config.DEFAULT_MINION_OPTS.copy()
    opts["grains"] = salt.loader.grains(opts)
    ctx = {}
    utils = salt.loader.utils(
        opts,
        whitelist=["boto3", "args", "systemd", "path", "platform"],
        context=ctx,
    )
    serializers = salt.loader.serializers(opts)
    funcs = funcs = salt.loader.minion_mods(
        opts, context=ctx, utils=utils, whitelist=["boto_elasticsearch_domain"]
    )
    salt_states = salt.loader.states(
        opts=opts,
        functions=funcs,
        utils=utils,
        whitelist=["boto_elasticsearch_domain"],
        serializers=serializers,
    )
    return {
        boto_elasticsearch_domain: {
            "__opts__": opts,
            "__salt__": funcs,
            "__utils__": utils,
            "__states__": salt_states,
            "__serializers__": serializers,
        }
    }


def test_present_when_domain_does_not_exist():
    GlobalConfig.conn_parameters["key"] = "".join(
        random.choice(string.ascii_lowercase + string.digits) for _ in range(50)
    )
    patcher = patch("boto3.session.Session")
    mock_session = patcher.start()
    session_instance = mock_session.return_value
    conn = MagicMock()
    session_instance.client.return_value = conn
    conn.describe_elasticsearch_domain.side_effect = GlobalConfig.not_found_error
    conn.describe_elasticsearch_domain_config.return_value = {
        "DomainConfig": GlobalConfig.domain_ret
    }
    conn.create_elasticsearch_domain.return_value = {
        "DomainStatus": GlobalConfig.domain_ret
    }
    result = boto_elasticsearch_domain.__states__["boto_elasticsearch_domain.present"](
        "domain present", **GlobalConfig.domain_ret
    )

    assert result["result"]
    assert result["changes"]["new"]["domain"]["ElasticsearchClusterConfig"] is None


def test_present_when_domain_exists():
    GlobalConfig.conn_parameters["key"] = "".join(
        random.choice(string.ascii_lowercase + string.digits) for _ in range(50)
    )
    patcher = patch("boto3.session.Session")
    mock_session = patcher.start()
    session_instance = mock_session.return_value
    conn = MagicMock()
    session_instance.client.return_value = conn
    conn.describe_elasticsearch_domain.return_value = {
        "DomainStatus": GlobalConfig.domain_ret
    }
    cfg = {}
    for k, v in GlobalConfig.domain_ret.items():
        cfg[k] = {"Options": v}
    cfg["AccessPolicies"] = {"Options": '{"a": "b"}'}
    conn.describe_elasticsearch_domain_config.return_value = {"DomainConfig": cfg}
    conn.update_elasticsearch_domain_config.return_value = {"DomainConfig": cfg}
    result = boto_elasticsearch_domain.__states__["boto_elasticsearch_domain.present"](
        "domain present", **GlobalConfig.domain_ret
    )
    assert result["result"]
    assert result["changes"] == {
        "new": {"AccessPolicies": {}},
        "old": {"AccessPolicies": {"a": "b"}},
    }


def test_present_with_failure():
    GlobalConfig.conn_parameters["key"] = "".join(
        random.choice(string.ascii_lowercase + string.digits) for _ in range(50)
    )
    patcher = patch("boto3.session.Session")
    mock_session = patcher.start()
    session_instance = mock_session.return_value
    conn = MagicMock()
    session_instance.client.return_value = conn
    conn.describe_elasticsearch_domain.side_effect = GlobalConfig.not_found_error
    conn.describe_elasticsearch_domain_config.return_value = {
        "DomainConfig": GlobalConfig.domain_ret
    }
    conn.create_elasticsearch_domain.side_effect = botocore.exceptions.ClientError(
        GlobalConfig.error_content, "create_domain"
    )
    result = boto_elasticsearch_domain.__states__["boto_elasticsearch_domain.present"](
        "domain present", **GlobalConfig.domain_ret
    )
    assert not result["result"]
    assert "An error occurred" in result["comment"]


def test_absent_when_domain_does_not_exist():
    """
    Tests absent on a domain that does not exist.
    """
    GlobalConfig.conn_parameters["key"] = "".join(
        random.choice(string.ascii_lowercase + string.digits) for _ in range(50)
    )
    patcher = patch("boto3.session.Session")
    mock_session = patcher.start()
    session_instance = mock_session.return_value
    conn = MagicMock()
    session_instance.client.return_value = conn
    conn.describe_elasticsearch_domain.side_effect = GlobalConfig.not_found_error
    result = boto_elasticsearch_domain.__states__["boto_elasticsearch_domain.absent"](
        "test", "mydomain"
    )
    assert result["result"]
    assert result["changes"] == {}


def test_absent_when_domain_exists():
    GlobalConfig.conn_parameters["key"] = "".join(
        random.choice(string.ascii_lowercase + string.digits) for _ in range(50)
    )
    patcher = patch("boto3.session.Session")
    mock_session = patcher.start()
    session_instance = mock_session.return_value
    conn = MagicMock()
    session_instance.client.return_value = conn
    conn.describe_elasticsearch_domain.return_value = {
        "DomainStatus": GlobalConfig.domain_ret
    }
    conn.describe_elasticsearch_domain_config.return_value = {
        "DomainConfig": GlobalConfig.domain_ret
    }
    result = boto_elasticsearch_domain.__states__["boto_elasticsearch_domain.absent"](
        "test", GlobalConfig.domain_ret["DomainName"]
    )
    assert result["result"]
    assert result["changes"]["new"]["domain"] is None


def test_absent_with_failure():
    GlobalConfig.conn_parameters["key"] = "".join(
        random.choice(string.ascii_lowercase + string.digits) for _ in range(50)
    )
    patcher = patch("boto3.session.Session")
    mock_session = patcher.start()
    session_instance = mock_session.return_value
    conn = MagicMock()
    session_instance.client.return_value = conn
    conn.describe_elasticsearch_domain.return_value = {
        "DomainStatus": GlobalConfig.domain_ret
    }
    conn.describe_elasticsearch_domain_config.return_value = {
        "DomainConfig": GlobalConfig.domain_ret
    }
    conn.delete_elasticsearch_domain.side_effect = botocore.exceptions.ClientError(
        GlobalConfig.error_content, "delete_domain"
    )
    result = boto_elasticsearch_domain.__states__["boto_elasticsearch_domain.absent"](
        "test", GlobalConfig.domain_ret["DomainName"]
    )
    assert not result["result"]
    assert "An error occurred" in result["comment"]
