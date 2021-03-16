import logging
import random
import string

import pytest
import salt.config
import salt.loader
import salt.states.boto_elasticsearch_domain as boto_elasticsearch_domain
from salt.utils.versions import LooseVersion
from tests.support.mock import MagicMock, patch

# pylint: disable=import-error,no-name-in-module,unused-import
try:
    import boto
    import boto3
    from botocore.exceptions import ClientError

    HAS_BOTO = True
except ImportError:
    HAS_BOTO = False

# pylint: enable=import-error,no-name-in-module,unused-import

# the boto_elasticsearch_domain module relies on the connect_to_region() method
# which was added in boto 2.8.0
# https://github.com/boto/boto/commit/33ac26b416fbb48a60602542b4ce15dcc7029f12
required_boto3_version = "1.2.1"

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
        opts, whitelist=["boto3", "args", "systemd", "path", "platform"], context=ctx,
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


@pytest.mark.skipif(HAS_BOTO is False, reason="The boto module must be installed.")
@pytest.mark.skipIf(
    _has_required_boto() is False,
    reason="The boto3 module must be greater than"
    " or equal to version {}".format(required_boto3_version),
)
def test_present_when_domain_does_not_exist():
    """
    Tests present on a domain that does not exist.
    """
    conn_parameters["key"] = "".join(
        random.choice(string.ascii_lowercase + string.digits) for _ in range(50)
    )
    patcher = patch("boto3.session.Session")
    mock_session = patcher.start()
    session_instance = mock_session.return_value
    conn = MagicMock()
    session_instance.client.return_value = conn
    conn.describe_elasticsearch_domain.side_effect = not_found_error
    conn.describe_elasticsearch_domain_config.return_value = {
        "DomainConfig": domain_ret
    }
    conn.create_elasticsearch_domain.return_value = {"DomainStatus": domain_ret}
    result = boto_elasticsearch_domain.__states__["boto_elasticsearch_domain.present"](
        "domain present", **domain_ret
    )

    assert result["result"]
    assert result["changes"]["new"]["domain"]["ElasticsearchClusterConfig"] is None


def test_present_when_domain_exists():
    conn_parameters["key"] = "".join(
        random.choice(string.ascii_lowercase + string.digits) for _ in range(50)
    )
    patcher = patch("boto3.session.Session")
    mock_session = patcher.start()
    session_instance = mock_session.return_value
    conn = MagicMock()
    session_instance.client.return_value = conn
    conn.describe_elasticsearch_domain.return_value = {"DomainStatus": domain_ret}
    cfg = {}
    for k, v in domain_ret.items():
        cfg[k] = {"Options": v}
    cfg["AccessPolicies"] = {"Options": '{"a": "b"}'}
    conn.describe_elasticsearch_domain_config.return_value = {"DomainConfig": cfg}
    conn.update_elasticsearch_domain_config.return_value = {"DomainConfig": cfg}
    result = boto_elasticsearch_domain.__states__["boto_elasticsearch_domain.present"](
        "domain present", **domain_ret
    )
    assert result["result"]
    assert result["changes"] == {
        "new": {"AccessPolicies": {}},
        "old": {"AccessPolicies": {"a": "b"}},
    }


def test_present_with_failure():
    conn_parameters["key"] = "".join(
        random.choice(string.ascii_lowercase + string.digits) for _ in range(50)
    )
    patcher = patch("boto3.session.Session")
    mock_session = patcher.start()
    session_instance = mock_session.return_value
    conn = MagicMock()
    session_instance.client.return_value = conn
    conn.describe_elasticsearch_domain.side_effect = not_found_error
    conn.describe_elasticsearch_domain_config.return_value = {
        "DomainConfig": domain_ret
    }
    conn.create_elasticsearch_domain.side_effect = ClientError(
        error_content, "create_domain"
    )
    result = boto_elasticsearch_domain.__states__["boto_elasticsearch_domain.present"](
        "domain present", **domain_ret
    )
    assert not result["result"]
    assert "An error occurred" in result["comment"]


def test_absent_when_domain_does_not_exist():
    """
    Tests absent on a domain that does not exist.
    """
    conn_parameters["key"] = "".join(
        random.choice(string.ascii_lowercase + string.digits) for _ in range(50)
    )
    patcher = patch("boto3.session.Session")
    mock_session = patcher.start()
    session_instance = mock_session.return_value
    conn = MagicMock()
    session_instance.client.return_value = conn
    conn.describe_elasticsearch_domain.side_effect = not_found_error
    result = boto_elasticsearch_domain.__states__["boto_elasticsearch_domain.absent"](
        "test", "mydomain"
    )
    assert result["result"]
    assert result["changes"] == {}


def test_absent_when_domain_exists():
    conn_parameters["key"] = "".join(
        random.choice(string.ascii_lowercase + string.digits) for _ in range(50)
    )
    patcher = patch("boto3.session.Session")
    mock_session = patcher.start()
    session_instance = mock_session.return_value
    conn = MagicMock()
    session_instance.client.return_value = conn
    conn.describe_elasticsearch_domain.return_value = {"DomainStatus": domain_ret}
    conn.describe_elasticsearch_domain_config.return_value = {
        "DomainConfig": domain_ret
    }
    result = boto_elasticsearch_domain.__states__["boto_elasticsearch_domain.absent"](
        "test", domain_ret["DomainName"]
    )
    assert result["result"]
    assert result["changes"]["new"]["domain"] is None


def test_absent_with_failure():
    conn_parameters["key"] = "".join(
        random.choice(string.ascii_lowercase + string.digits) for _ in range(50)
    )
    patcher = patch("boto3.session.Session")
    mock_session = patcher.start()
    session_instance = mock_session.return_value
    conn = MagicMock()
    session_instance.client.return_value = conn
    conn.describe_elasticsearch_domain.return_value = {"DomainStatus": domain_ret}
    conn.describe_elasticsearch_domain_config.return_value = {
        "DomainConfig": domain_ret
    }
    conn.delete_elasticsearch_domain.side_effect = ClientError(
        error_content, "delete_domain"
    )
    result = boto_elasticsearch_domain.__states__["boto_elasticsearch_domain.absent"](
        "test", domain_ret["DomainName"]
    )
    assert not result["result"]
    assert "An error occurred" in result["comment"]
