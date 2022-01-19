"""
    Tests for salt.modules.boto3_elasticsearch
"""


import datetime
import random
import string
import textwrap

import salt.loader
import salt.modules.boto3_elasticsearch as boto3_elasticsearch
from salt.utils.versions import LooseVersion
from tests.support.mixins import LoaderModuleMockMixin
from tests.support.mock import MagicMock, patch
from tests.support.unit import TestCase, skipIf

try:
    import boto3
    from botocore.exceptions import ClientError

    HAS_BOTO3 = True
except ImportError:
    HAS_BOTO3 = False

# the boto3_elasticsearch module relies on the connect_to_region() method
# which was added in boto 2.8.0
# https://github.com/boto/boto/commit/33ac26b416fbb48a60602542b4ce15dcc7029f12
REQUIRED_BOTO3_VERSION = "1.2.1"


def __virtual__():
    """
    Returns True/False boolean depending on if Boto3 is installed and correct
    version.
    """
    if not HAS_BOTO3:
        return False
    if LooseVersion(boto3.__version__) < LooseVersion(REQUIRED_BOTO3_VERSION):
        return (
            False,
            "The boto3 module must be greater or equal to version {}".format(
                REQUIRED_BOTO3_VERSION
            ),
        )
    return True


REGION = "us-east-1"
ACCESS_KEY = "GKTADJGHEIQSXMKKRBJ08H"
SECRET_KEY = "askdjghsdfjkghWupUjasdflkdfklgjsdfjajkghs"
CONN_PARAMETERS = {
    "region": REGION,
    "key": ACCESS_KEY,
    "keyid": SECRET_KEY,
    "profile": {},
}
ERROR_MESSAGE = (
    "An error occurred ({}) when calling the {} operation: Test-defined error"
)
ERROR_CONTENT = {"Error": {"Code": 101, "Message": "Test-defined error"}}
NOT_FOUND_ERROR = ClientError(
    {"Error": {"Code": "ResourceNotFoundException", "Message": "Test-defined error"}},
    "msg",
)
DOMAIN_RET = {
    "DomainId": "accountno/testdomain",
    "DomainName": "testdomain",
    "ARN": "arn:aws:es:region:accountno:domain/testdomain",
    "Created": True,
    "Deleted": False,
    "Endpoints": {"vpc": "vpc-testdomain-1234567890.region.es.amazonaws.com"},
    "Processing": False,
    "UpgradeProcessing": False,
    "ElasticsearchVersion": "6.3",
    "ElasticsearchClusterConfig": {
        "InstanceType": "t2.medium.elasticsearch",
        "InstanceCount": 1,
        "DedicatedMasterEnabled": False,
        "ZoneAwarenessEnabled": False,
    },
    "EBSOptions": {
        "EBSEnabled": True,
        "VolumeType": "gp2",
        "VolumeSize": 123,
        "Iops": 12,
    },
    "AccessPolicies": textwrap.dedent(
        """
        {"Version":"2012-10-17","Statement":[{"Effect":"Allow",
        "Principal":{"AWS":"*"},"Action":"es:*",
        "Resource":"arn:aws:es:region:accountno:domain/testdomain/*"}]}"""
    ),
    "SnapshotOptions": {"AutomatedSnapshotStartHour": 1},
    "VPCOptions": {
        "VPCId": "vpc-12345678",
        "SubnetIds": ["subnet-deadbeef"],
        "AvailabilityZones": ["regiona"],
        "SecurityGroupIds": ["sg-87654321"],
    },
    "CognitoOptions": {"Enabled": False},
    "EncryptionAtRestOptions": {"Enabled": False},
    "NodeToNodeEncryptionOptions": {"Enabled": False},
    "AdvancedOptions": {"rest.action.multi.allow_explicit_index": "true"},
    "ServiceSoftwareOptions": {
        "CurrentVersion": "R20190221-P1",
        "NewVersion": "R20190418",
        "UpdateAvailable": True,
        "Cancellable": False,
        "UpdateStatus": "ELIGIBLE",
        "Description": (
            "A newer release R20190418 is available. This release "
            "will be automatically deployed after somedate"
        ),
        "AutomatedUpdateDate": None,
    },
}


@skipIf(HAS_BOTO3 is False, "The boto module must be installed.")
@skipIf(
    LooseVersion(boto3.__version__) < LooseVersion(REQUIRED_BOTO3_VERSION),
    "The boto3 module must be greater or equal to version {}".format(
        REQUIRED_BOTO3_VERSION
    ),
)
class Boto3ElasticsearchTestCase(TestCase, LoaderModuleMockMixin):
    """
    TestCase for salt.modules.boto3_elasticsearch module
    """

    conn = None

    def setup_loader_modules(self):
        self.opts = salt.config.DEFAULT_MINION_OPTS.copy()
        utils = salt.loader.utils(
            self.opts,
            whitelist=["boto3", "args", "systemd", "path", "platform"],
            context={},
        )
        return {boto3_elasticsearch: {"__utils__": utils}}

    def setUp(self):
        super().setUp()
        boto3_elasticsearch.__init__(self.opts)
        del self.opts

        # Set up MagicMock to replace the boto3 session
        # connections keep getting cached from prior tests, can't find the
        # correct context object to clear it. So randomize the cache key, to prevent any
        # cache hits
        CONN_PARAMETERS["key"] = "".join(
            random.choice(string.ascii_lowercase + string.digits) for _ in range(50)
        )

        self.conn = MagicMock()
        self.addCleanup(delattr, self, "conn")
        self.patcher = patch("boto3.session.Session")
        self.addCleanup(self.patcher.stop)
        self.addCleanup(delattr, self, "patcher")
        mock_session = self.patcher.start()
        session_instance = mock_session.return_value
        session_instance.configure_mock(client=MagicMock(return_value=self.conn))
        self.paginator = MagicMock()
        self.addCleanup(delattr, self, "paginator")
        self.conn.configure_mock(get_paginator=MagicMock(return_value=self.paginator))

    def test_describe_elasticsearch_domain_positive(self):
        """
        Test that when describing a domain when the domain actually exists,
        the .exists method returns a dict with 'result': True
        and 'response' with the domain status information.
        """
        # The patch below is not neccesary per se,
        # as .exists returns positive as long as no exception is raised.
        with patch.object(
            self.conn,
            "describe_elasticsearch_domain",
            return_value={"DomainStatus": DOMAIN_RET},
        ):
            self.assertEqual(
                boto3_elasticsearch.describe_elasticsearch_domain(
                    domain_name="testdomain", **CONN_PARAMETERS
                ),
                {"result": True, "response": DOMAIN_RET},
            )

    def test_describe_elasticsearch_domain_error(self):
        """
        Test that when describing a domain when the domain does not exist,
        the .exists method returns a dict with 'result': False
        and 'error' with boto's ResourceNotFoundException.
        """
        with patch.object(
            self.conn, "describe_elasticsearch_domain", side_effect=NOT_FOUND_ERROR
        ):
            result = boto3_elasticsearch.describe_elasticsearch_domain(
                domain_name="testdomain", **CONN_PARAMETERS
            )
            self.assertEqual(
                result.get("error", ""),
                ERROR_MESSAGE.format("ResourceNotFoundException", "msg"),
            )
            self.assertFalse(result["result"])

    def test_create_elasticsearch_domain_positive(self):
        """
        Test that when creating a domain, and it succeeds,
        the .create method returns a dict with 'result': True
        and 'response' with the newly created domain's status information.
        """
        with patch.object(
            self.conn,
            "create_elasticsearch_domain",
            return_value={"DomainStatus": DOMAIN_RET},
        ):
            kwargs = {
                "elasticsearch_version": DOMAIN_RET["ElasticsearchVersion"],
                "elasticsearch_cluster_config": DOMAIN_RET[
                    "ElasticsearchClusterConfig"
                ],
                "ebs_options": DOMAIN_RET["EBSOptions"],
                "access_policies": DOMAIN_RET["AccessPolicies"],
                "snapshot_options": DOMAIN_RET["SnapshotOptions"],
                "vpc_options": DOMAIN_RET["VPCOptions"],
                "cognito_options": DOMAIN_RET["CognitoOptions"],
                "encryption_at_rest_options": DOMAIN_RET["EncryptionAtRestOptions"],
                "advanced_options": DOMAIN_RET["AdvancedOptions"],
            }
            kwargs.update(CONN_PARAMETERS)
            self.assertEqual(
                boto3_elasticsearch.create_elasticsearch_domain(
                    domain_name="testdomain", **kwargs
                ),
                {"result": True, "response": DOMAIN_RET},
            )

    def test_create_elasticsearch_domain_error(self):
        """
        Test that when creating a domain, and boto3 returns an error,
        the .create method returns a dict with 'result': False
        and 'error' with the error reported by boto3.
        """
        with patch.object(
            self.conn,
            "create_elasticsearch_domain",
            side_effect=ClientError(ERROR_CONTENT, "create_domain"),
        ):
            kwargs = {
                "elasticsearch_version": DOMAIN_RET["ElasticsearchVersion"],
                "elasticsearch_cluster_config": DOMAIN_RET[
                    "ElasticsearchClusterConfig"
                ],
                "ebs_options": DOMAIN_RET["EBSOptions"],
                "access_policies": DOMAIN_RET["AccessPolicies"],
                "snapshot_options": DOMAIN_RET["SnapshotOptions"],
                "vpc_options": DOMAIN_RET["VPCOptions"],
                "cognito_options": DOMAIN_RET["CognitoOptions"],
                "encryption_at_rest_options": DOMAIN_RET["EncryptionAtRestOptions"],
                "advanced_options": DOMAIN_RET["AdvancedOptions"],
            }
            kwargs.update(CONN_PARAMETERS)
            result = boto3_elasticsearch.create_elasticsearch_domain(
                "testdomain", **kwargs
            )
            self.assertEqual(
                result.get("error", ""), ERROR_MESSAGE.format(101, "create_domain")
            )

    def test_delete_domain_positive(self):
        """
        Test that when deleting a domain, and it succeeds,
        the .delete method returns {'result': True}.
        """
        with patch.object(self.conn, "delete_elasticsearch_domain"):
            self.assertEqual(
                boto3_elasticsearch.delete_elasticsearch_domain(
                    "testdomain", **CONN_PARAMETERS
                ),
                {"result": True},
            )

    def test_delete_domain_error(self):
        """
        Test that when deleting a domain, and boto3 returns an error,
        the .delete method returns {'result': False, 'error' :'the error'}.
        """
        with patch.object(
            self.conn,
            "delete_elasticsearch_domain",
            side_effect=ClientError(ERROR_CONTENT, "delete_domain"),
        ):
            result = boto3_elasticsearch.delete_elasticsearch_domain(
                "testdomain", **CONN_PARAMETERS
            )
            self.assertFalse(result["result"])
            self.assertEqual(
                result.get("error", ""), ERROR_MESSAGE.format(101, "delete_domain")
            )

    def test_update_domain_positive(self):
        """
        Test that when updating a domain succeeds, the .update method returns {'result': True}.
        """
        with patch.object(
            self.conn,
            "update_elasticsearch_domain_config",
            return_value={"DomainConfig": DOMAIN_RET},
        ):
            kwargs = {
                "elasticsearch_cluster_config": DOMAIN_RET[
                    "ElasticsearchClusterConfig"
                ],
                "ebs_options": DOMAIN_RET["EBSOptions"],
                "snapshot_options": DOMAIN_RET["SnapshotOptions"],
                "vpc_options": DOMAIN_RET["VPCOptions"],
                "cognito_options": DOMAIN_RET["CognitoOptions"],
                "advanced_options": DOMAIN_RET["AdvancedOptions"],
                "access_policies": DOMAIN_RET["AccessPolicies"],
                "log_publishing_options": {},
            }

            kwargs.update(CONN_PARAMETERS)
            self.assertEqual(
                boto3_elasticsearch.update_elasticsearch_domain_config(
                    "testdomain", **kwargs
                ),
                {"result": True, "response": DOMAIN_RET},
            )

    def test_update_domain_error(self):
        """
        Test that when updating a domain fails, and boto3 returns an error,
        the .update method returns the error.
        """
        with patch.object(
            self.conn,
            "update_elasticsearch_domain_config",
            side_effect=ClientError(ERROR_CONTENT, "update_domain"),
        ):
            kwargs = {
                "elasticsearch_cluster_config": DOMAIN_RET[
                    "ElasticsearchClusterConfig"
                ],
                "ebs_options": DOMAIN_RET["EBSOptions"],
                "snapshot_options": DOMAIN_RET["SnapshotOptions"],
                "vpc_options": DOMAIN_RET["VPCOptions"],
                "cognito_options": DOMAIN_RET["CognitoOptions"],
                "advanced_options": DOMAIN_RET["AdvancedOptions"],
                "access_policies": DOMAIN_RET["AccessPolicies"],
                "log_publishing_options": {},
            }
            kwargs.update(CONN_PARAMETERS)
            result = boto3_elasticsearch.update_elasticsearch_domain_config(
                "testdomain", **kwargs
            )
            self.assertEqual(
                result.get("error", ""), ERROR_MESSAGE.format(101, "update_domain")
            )

    def test_add_tags_positive(self):
        """
        Test that when adding tags is successful, the .add_tags method returns {'result': True}.
        """
        with patch.object(
            self.conn,
            "describe_elasticsearch_domain",
            return_value={"DomainStatus": DOMAIN_RET},
        ):
            self.assertEqual(
                boto3_elasticsearch.add_tags(
                    "testdomain", tags={"foo": "bar", "baz": "qux"}, **CONN_PARAMETERS
                ),
                {"result": True},
            )

    def test_add_tags_default(self):
        """
        Test that when tags are not provided, no error is raised.
        """
        with patch.object(
            self.conn,
            "describe_elasticsearch_domain",
            return_value={"DomainStatus": DOMAIN_RET},
        ):
            self.assertEqual(
                boto3_elasticsearch.add_tags("testdomain", **CONN_PARAMETERS),
                {"result": True},
            )

    def test_add_tags_error(self):
        """
        Test that when adding tags fails, and boto3 returns an error,
        the .add_tags function returns {'tagged': False, 'error': 'the error'}.
        """
        with patch.object(
            self.conn, "add_tags", side_effect=ClientError(ERROR_CONTENT, "add_tags")
        ), patch.object(
            self.conn,
            "describe_elasticsearch_domain",
            return_value={"DomainStatus": DOMAIN_RET},
        ):
            result = boto3_elasticsearch.add_tags(
                "testdomain", tags={"foo": "bar", "baz": "qux"}, **CONN_PARAMETERS
            )
            self.assertFalse(result["result"])
            self.assertEqual(
                result.get("error", ""), ERROR_MESSAGE.format(101, "add_tags")
            )

    def test_remove_tags_positive(self):
        """
        Test that when removing tags is successful, the .remove_tags method returns {'tagged': True}.
        """
        with patch.object(
            self.conn,
            "describe_elasticsearch_domain",
            return_value={"DomainStatus": DOMAIN_RET},
        ):
            self.assertEqual(
                boto3_elasticsearch.remove_tags(
                    tag_keys=["foo", "bar"], domain_name="testdomain", **CONN_PARAMETERS
                ),
                {"result": True},
            )

    def test_remove_tag_error(self):
        """
        Test that when removing tags fails, and boto3 returns an error,
        the .remove_tags method returns {'tagged': False, 'error': 'the error'}.
        """
        with patch.object(
            self.conn,
            "remove_tags",
            side_effect=ClientError(ERROR_CONTENT, "remove_tags"),
        ), patch.object(
            self.conn,
            "describe_elasticsearch_domain",
            return_value={"DomainStatus": DOMAIN_RET},
        ):
            result = boto3_elasticsearch.remove_tags(
                tag_keys=["foo", "bar"], domain_name="testdomain", **CONN_PARAMETERS
            )
            self.assertFalse(result["result"])
            self.assertEqual(
                result.get("error", ""), ERROR_MESSAGE.format(101, "remove_tags")
            )

    def test_list_tags_positive(self):
        """
        Test that when listing tags is successful,
        the .list_tags method returns a dict with key 'tags'.
        Also test that the tags returned are manipulated properly (i.e. transformed
        into a dict with tags).
        """
        with patch.object(
            self.conn,
            "describe_elasticsearch_domain",
            return_value={"DomainStatus": DOMAIN_RET},
        ), patch.object(
            self.conn,
            "list_tags",
            return_value={"TagList": [{"Key": "foo", "Value": "bar"}]},
        ):
            result = boto3_elasticsearch.list_tags(
                domain_name="testdomain", **CONN_PARAMETERS
            )
            self.assertEqual(result, {"result": True, "response": {"foo": "bar"}})

    def test_list_tags_error(self):
        """
        Test that when listing tags causes boto3 to return an error,
        the .list_tags method returns the error.
        """
        with patch.object(
            self.conn, "list_tags", side_effect=ClientError(ERROR_CONTENT, "list_tags")
        ), patch.object(
            self.conn,
            "describe_elasticsearch_domain",
            return_value={"DomainStatus": DOMAIN_RET},
        ):
            result = boto3_elasticsearch.list_tags(
                domain_name="testdomain", **CONN_PARAMETERS
            )
            self.assertFalse(result["result"])
            self.assertEqual(
                result.get("error", ""), ERROR_MESSAGE.format(101, "list_tags")
            )

    def test_cancel_elasticsearch_service_software_update_positive(self):
        """
        Test that when calling cancel_elasticsearch_service_software_update and
        it is successful, it returns {'result': True}.
        """
        retval = {
            "ServiceSoftwareOptions": {
                "CurrentVersion": "string",
                "NewVersion": "string",
                "UpdateAvailable": True,
                "Cancellable": True,
                "UpdateStatus": "ELIGIBLE",
                "Description": "string",
                "AutomatedUpdateDate": datetime.datetime(2015, 1, 1),
            }
        }
        with patch.object(
            self.conn,
            "cancel_elasticsearch_service_software_update",
            return_value=retval,
        ):
            result = boto3_elasticsearch.cancel_elasticsearch_service_software_update(
                domain_name="testdomain", **CONN_PARAMETERS
            )
            self.assertEqual(result, {"result": True})

    def test_cancel_elasticsearch_service_software_update_error(self):
        """
        Test that when calling cancel_elasticsearch_service_software_update and
        boto3 returns an error, it returns {'result': False, 'error': 'the error'}.
        """
        with patch.object(
            self.conn,
            "cancel_elasticsearch_service_software_update",
            side_effect=ClientError(
                ERROR_CONTENT, "cancel_elasticsearch_service_software_update"
            ),
        ):
            result = boto3_elasticsearch.cancel_elasticsearch_service_software_update(
                domain_name="testdomain", **CONN_PARAMETERS
            )
            self.assertFalse(result["result"])
            self.assertEqual(
                result.get("error", ""),
                ERROR_MESSAGE.format(
                    101, "cancel_elasticsearch_service_software_update"
                ),
            )

    def test_delete_elasticsearch_service_role_positive(self):
        """
        Test that when calling delete_elasticsearch_service_role and
        it is successful, it returns {'result': True}.
        """
        with patch.object(
            self.conn, "delete_elasticsearch_service_role", return_value=None
        ):
            result = boto3_elasticsearch.delete_elasticsearch_service_role(
                **CONN_PARAMETERS
            )
            self.assertEqual(result, {"result": True})

    def test_delete_elasticsearch_service_role_error(self):
        """
        Test that when calling delete_elasticsearch_service_role and boto3 returns
        an error, it returns {'result': False, 'error': 'the error'}.
        """
        with patch.object(
            self.conn,
            "delete_elasticsearch_service_role",
            side_effect=ClientError(ERROR_CONTENT, "delete_elasticsearch_service_role"),
        ):
            result = boto3_elasticsearch.delete_elasticsearch_service_role(
                **CONN_PARAMETERS
            )
            self.assertFalse(result["result"])
            self.assertEqual(
                result.get("error", ""),
                ERROR_MESSAGE.format(101, "delete_elasticsearch_service_role"),
            )

    def test_describe_elasticsearch_domain_config_positive(self):
        """
        Test that when calling describe_elasticsearch_domain_config and
        it is successful, it returns {'result': True}.
        """
        with patch.object(
            self.conn,
            "describe_elasticsearch_domain_config",
            return_value={"DomainConfig": DOMAIN_RET},
        ):
            self.assertEqual(
                boto3_elasticsearch.describe_elasticsearch_domain_config(
                    "testdomain", **CONN_PARAMETERS
                ),
                {"result": True, "response": DOMAIN_RET},
            )

    def test_describe_elasticsearch_domain_config_error(self):
        """
        Test that when calling describe_elasticsearch_domain_config and boto3 returns
        an error, it returns {'result': False, 'error': 'the error'}.
        """
        with patch.object(
            self.conn,
            "describe_elasticsearch_domain_config",
            side_effect=ClientError(
                ERROR_CONTENT, "describe_elasticsearch_domain_config"
            ),
        ):
            result = boto3_elasticsearch.describe_elasticsearch_domain_config(
                domain_name="testdomain", **CONN_PARAMETERS
            )
            self.assertFalse(result["result"])
            self.assertEqual(
                result.get("error", ""),
                ERROR_MESSAGE.format(101, "describe_elasticsearch_domain_config"),
            )

    def test_describe_elasticsearch_domains_positive(self):
        """
        Test that when calling describe_elasticsearch_domains and it is successful,
        it returns {'result': True, 'response': some_data}.
        """
        with patch.object(
            self.conn,
            "describe_elasticsearch_domains",
            return_value={"DomainStatusList": [DOMAIN_RET]},
        ):
            self.assertEqual(
                boto3_elasticsearch.describe_elasticsearch_domains(
                    domain_names=["test_domain"], **CONN_PARAMETERS
                ),
                {"result": True, "response": [DOMAIN_RET]},
            )

    def test_describe_elasticsearch_domains_error(self):
        """
        Test that when calling describe_elasticsearch_domains and boto3 returns
        an error, it returns {'result': False, 'error': 'the error'}.
        """
        with patch.object(
            self.conn,
            "describe_elasticsearch_domains",
            side_effect=ClientError(ERROR_CONTENT, "describe_elasticsearch_domains"),
        ):
            result = boto3_elasticsearch.describe_elasticsearch_domains(
                domain_names=["testdomain"], **CONN_PARAMETERS
            )
            self.assertFalse(result["result"])
            self.assertEqual(
                result.get("error", ""),
                ERROR_MESSAGE.format(101, "describe_elasticsearch_domains"),
            )

    def test_describe_elasticsearch_instance_type_limits_positive(self):
        """
        Test that when calling describe_elasticsearch_instance_type_limits and
        it succeeds, it returns {'result': True, 'response' some_value}.
        """
        ret_val = {
            "LimitsByRole": {
                "string": {
                    "StorageTypes": [
                        {
                            "StorageTypeName": "string",
                            "StorageSubTypeName": "string",
                            "StorageTypeLimits": [
                                {"LimitName": "string", "LimitValues": ["string"]}
                            ],
                        }
                    ],
                    "InstanceLimits": {
                        "InstanceCountLimits": {
                            "MinimumInstanceCount": 123,
                            "MaximumInstanceCount": 123,
                        }
                    },
                    "AdditionalLimits": [
                        {"LimitName": "string", "LimitValues": ["string"]}
                    ],
                }
            }
        }
        with patch.object(
            self.conn,
            "describe_elasticsearch_instance_type_limits",
            return_value=ret_val,
        ):
            self.assertEqual(
                boto3_elasticsearch.describe_elasticsearch_instance_type_limits(
                    domain_name="testdomain",
                    instance_type="foo",
                    elasticsearch_version="1.0",
                    **CONN_PARAMETERS
                ),
                {"result": True, "response": ret_val["LimitsByRole"]},
            )

    def test_describe_elasticsearch_instance_type_limits_error(self):
        """
        Test that when calling describe_elasticsearch_instance_type_limits and boto3 returns
        an error, it returns {'result': False, 'error': 'the error'}.
        """
        with patch.object(
            self.conn,
            "describe_elasticsearch_instance_type_limits",
            side_effect=ClientError(
                ERROR_CONTENT, "describe_elasticsearch_instance_type_limits"
            ),
        ):
            result = boto3_elasticsearch.describe_elasticsearch_instance_type_limits(
                domain_name="testdomain",
                instance_type="foo",
                elasticsearch_version="1.0",
                **CONN_PARAMETERS
            )
            self.assertFalse(result["result"])
            self.assertEqual(
                result.get("error", ""),
                ERROR_MESSAGE.format(
                    101, "describe_elasticsearch_instance_type_limits"
                ),
            )

    def test_describe_reserved_elasticsearch_instance_offerings_positive(self):
        """
        Test that when calling describe_reserved_elasticsearch_instance_offerings
        and it succeeds, it returns {'result': True, 'response': some_value}.
        """
        ret_val = {
            "NextToken": "string",
            "ReservedElasticsearchInstanceOfferings": [
                {
                    "ReservedElasticsearchInstanceOfferingId": "string",
                    "ElasticsearchInstanceType": "t2.medium.elasticsearch",
                    "Duration": 123,
                    "FixedPrice": 123.0,
                    "UsagePrice": 123.0,
                    "CurrencyCode": "string",
                    "PaymentOption": "NO_UPFRONT",
                    "RecurringCharges": [
                        {
                            "RecurringChargeAmount": 123.0,
                            "RecurringChargeFrequency": "string",
                        }
                    ],
                }
            ],
        }
        with patch.object(self.paginator, "paginate", return_value=[ret_val]):
            self.assertEqual(
                boto3_elasticsearch.describe_reserved_elasticsearch_instance_offerings(
                    reserved_elasticsearch_instance_offering_id="foo", **CONN_PARAMETERS
                ),
                {
                    "result": True,
                    "response": ret_val["ReservedElasticsearchInstanceOfferings"],
                },
            )

    def test_describe_reserved_elasticsearch_instance_offerings_error(self):
        """
        Test that when calling describe_reserved_elasticsearch_instance_offerings
        and boto3 returns an error, it returns {'result': False, 'error': 'the error'}.
        """
        with patch.object(
            self.paginator,
            "paginate",
            side_effect=ClientError(
                ERROR_CONTENT, "describe_reserved_elasticsearch_instance_offerings"
            ),
        ):
            result = (
                boto3_elasticsearch.describe_reserved_elasticsearch_instance_offerings(
                    reserved_elasticsearch_instance_offering_id="foo", **CONN_PARAMETERS
                )
            )
            self.assertFalse(result["result"])
            self.assertEqual(
                result.get("error", ""),
                ERROR_MESSAGE.format(
                    101, "describe_reserved_elasticsearch_instance_offerings"
                ),
            )

    def test_describe_reserved_elasticsearch_instances_positive(self):
        """
        Test that when calling describe_reserved_elasticsearch_instances and it
        succeeds, it returns {'result': True, 'response': some_value}.
        """
        ret_val = {
            "NextToken": "string",
            "ReservedElasticsearchInstances": [
                {
                    "ReservationName": "string",
                    "ReservedElasticsearchInstanceId": "string",
                    "ReservedElasticsearchInstanceOfferingId": "string",
                    "ElasticsearchInstanceType": "t2.medium.elasticsearch",
                    "StartTime": datetime.datetime(2015, 1, 1),
                    "Duration": 123,
                    "FixedPrice": 123.0,
                    "UsagePrice": 123.0,
                    "CurrencyCode": "string",
                    "ElasticsearchInstanceCount": 123,
                    "State": "string",
                    "PaymentOption": "ALL_UPFRONT",
                    "RecurringCharges": [
                        {
                            "RecurringChargeAmount": 123.0,
                            "RecurringChargeFrequency": "string",
                        },
                    ],
                },
            ],
        }
        with patch.object(self.paginator, "paginate", return_value=[ret_val]):
            self.assertEqual(
                boto3_elasticsearch.describe_reserved_elasticsearch_instances(
                    reserved_elasticsearch_instance_id="foo", **CONN_PARAMETERS
                ),
                {"result": True, "response": ret_val["ReservedElasticsearchInstances"]},
            )

    def test_describe_reserved_elasticsearch_instances_error(self):
        """
        Test that when calling describe_reserved_elasticsearch_instances and boto3
        returns an error, it returns {'result': False, 'error': 'the error'}.
        """
        with patch.object(
            self.paginator,
            "paginate",
            side_effect=ClientError(
                ERROR_CONTENT, "describe_reserved_elasticsearch_instances"
            ),
        ):
            result = boto3_elasticsearch.describe_reserved_elasticsearch_instances(
                reserved_elasticsearch_instance_id="foo", **CONN_PARAMETERS
            )
            self.assertFalse(result["result"])
            self.assertEqual(
                result.get("error", ""),
                ERROR_MESSAGE.format(101, "describe_reserved_elasticsearch_instances"),
            )

    def test_get_compatible_elasticsearch_versions_positive(self):
        """
        Test that when calling get_compatible_elasticsearch_versions and it
        succeeds, it returns {'result': True, 'response': some_value}.
        """
        ret_val = {
            "CompatibleElasticsearchVersions": [
                {"SourceVersion": "string", "TargetVersions": ["string"]}
            ]
        }
        with patch.object(
            self.conn, "get_compatible_elasticsearch_versions", return_value=ret_val
        ):
            self.assertEqual(
                boto3_elasticsearch.get_compatible_elasticsearch_versions(
                    domain_name="testdomain", **CONN_PARAMETERS
                ),
                {
                    "result": True,
                    "response": ret_val["CompatibleElasticsearchVersions"],
                },
            )

    def test_get_compatible_elasticsearch_versions_error(self):
        """
        Test that when calling get_compatible_elasticsearch_versions and boto3
        returns an error, it returns {'result': False, 'error': 'the error'}.
        """
        with patch.object(
            self.conn,
            "get_compatible_elasticsearch_versions",
            side_effect=ClientError(
                ERROR_CONTENT, "get_compatible_elasticsearch_versions"
            ),
        ):
            result = boto3_elasticsearch.get_compatible_elasticsearch_versions(
                domain_name="testdomain", **CONN_PARAMETERS
            )
            self.assertFalse(result["result"])
            self.assertEqual(
                result.get("error", ""),
                ERROR_MESSAGE.format(101, "get_compatible_elasticsearch_versions"),
            )

    def test_get_upgrade_history_positive(self):
        """
        Test that when calling get_upgrade_history and it
        succeeds, it returns {'result': True, 'response': some_value}.
        """
        ret_val = {
            "UpgradeHistories": [
                {
                    "UpgradeName": "string",
                    "StartTimestamp": datetime.datetime(2015, 1, 1),
                    "UpgradeStatus": "IN_PROGRESS",
                    "StepsList": [
                        {
                            "UpgradeStep": "PRE_UPGRADE_CHECK",
                            "UpgradeStepStatus": "IN_PROGRESS",
                            "Issues": ["string"],
                            "ProgressPercent": 123.0,
                        }
                    ],
                }
            ],
            "NextToken": "string",
        }
        with patch.object(self.paginator, "paginate", return_value=[ret_val]):
            self.assertEqual(
                boto3_elasticsearch.get_upgrade_history(
                    domain_name="testdomain", **CONN_PARAMETERS
                ),
                {"result": True, "response": ret_val["UpgradeHistories"]},
            )

    def test_get_upgrade_history_error(self):
        """
        Test that when calling get_upgrade_history and boto3
        returns an error, it returns {'result': False, 'error': 'the error'}.
        """
        with patch.object(
            self.paginator,
            "paginate",
            side_effect=ClientError(ERROR_CONTENT, "get_upgrade_history"),
        ):
            result = boto3_elasticsearch.get_upgrade_history(
                domain_name="testdomain", **CONN_PARAMETERS
            )
            self.assertFalse(result["result"])
            self.assertEqual(
                result.get("error", ""),
                ERROR_MESSAGE.format(101, "get_upgrade_history"),
            )

    def test_get_upgrade_status_positive(self):
        """
        Test that when calling get_upgrade_status and it
        succeeds, it returns {'result': True, 'response': some_value}.
        """
        ret_val = {
            "UpgradeStep": "PRE_UPGRADE_CHECK",
            "StepStatus": "IN_PROGRESS",
            "UpgradeName": "string",
            "ResponseMetadata": None,
        }
        with patch.object(self.conn, "get_upgrade_status", return_value=ret_val):
            self.assertEqual(
                boto3_elasticsearch.get_upgrade_status(
                    domain_name="testdomain", **CONN_PARAMETERS
                ),
                {"result": True, "response": ret_val},
            )

    def test_get_upgrade_status_error(self):
        """
        Test that when calling get_upgrade_status and boto3
        returns an error, it returns {'result': False, 'error': 'the error'}.
        """
        with patch.object(
            self.conn,
            "get_upgrade_status",
            side_effect=ClientError(ERROR_CONTENT, "get_upgrade_status"),
        ):
            result = boto3_elasticsearch.get_upgrade_status(
                domain_name="testdomain", **CONN_PARAMETERS
            )
            self.assertFalse(result["result"])
            self.assertEqual(
                result.get("error", ""), ERROR_MESSAGE.format(101, "get_upgrade_status")
            )

    def test_list_domain_names_positive(self):
        """
        Test that when calling list_domain_names and it
        succeeds, it returns {'result': True, 'response': some_value}.
        """
        ret_val = {"DomainNames": [{"DomainName": "string"}]}
        with patch.object(self.conn, "list_domain_names", return_value=ret_val):
            self.assertEqual(
                boto3_elasticsearch.list_domain_names(**CONN_PARAMETERS),
                {
                    "result": True,
                    "response": [item["DomainName"] for item in ret_val["DomainNames"]],
                },
            )

    def test_list_domain_names_error(self):
        """
        Test that when calling list_domain_names and boto3
        returns an error, it returns {'result': False, 'error': 'the error'}.
        """
        with patch.object(
            self.conn,
            "list_domain_names",
            side_effect=ClientError(ERROR_CONTENT, "list_domain_names"),
        ):
            result = boto3_elasticsearch.list_domain_names(**CONN_PARAMETERS)
            self.assertFalse(result["result"])
            self.assertEqual(
                result.get("error", ""), ERROR_MESSAGE.format(101, "list_domain_names")
            )

    def test_list_elasticsearch_instance_types_positive(self):
        """
        Test that when calling list_elasticsearch_instance_types and it
        succeeds, it returns {'result': True, 'response': some_value}.
        """
        ret_val = {
            "ElasticsearchInstanceTypes": [
                "m3.medium.elasticsearch",
                "m3.large.elasticsearch",
                "m3.xlarge.elasticsearch",
                "m3.2xlarge.elasticsearch",
                "m4.large.elasticsearch",
                "m4.xlarge.elasticsearch",
                "m4.2xlarge.elasticsearch",
                "m4.4xlarge.elasticsearch",
                "m4.10xlarge.elasticsearch",
                "t2.micro.elasticsearch",
                "t2.small.elasticsearch",
                "t2.medium.elasticsearch",
                "r3.large.elasticsearch",
                "r3.xlarge.elasticsearch",
                "r3.2xlarge.elasticsearch",
                "r3.4xlarge.elasticsearch",
                "r3.8xlarge.elasticsearch",
                "i2.xlarge.elasticsearch",
                "i2.2xlarge.elasticsearch",
                "d2.xlarge.elasticsearch",
                "d2.2xlarge.elasticsearch",
                "d2.4xlarge.elasticsearch",
                "d2.8xlarge.elasticsearch",
                "c4.large.elasticsearch",
                "c4.xlarge.elasticsearch",
                "c4.2xlarge.elasticsearch",
                "c4.4xlarge.elasticsearch",
                "c4.8xlarge.elasticsearch",
                "r4.large.elasticsearch",
                "r4.xlarge.elasticsearch",
                "r4.2xlarge.elasticsearch",
                "r4.4xlarge.elasticsearch",
                "r4.8xlarge.elasticsearch",
                "r4.16xlarge.elasticsearch",
                "i3.large.elasticsearch",
                "i3.xlarge.elasticsearch",
                "i3.2xlarge.elasticsearch",
                "i3.4xlarge.elasticsearch",
                "i3.8xlarge.elasticsearch",
                "i3.16xlarge.elasticsearch",
            ],
            "NextToken": "string",
        }
        with patch.object(self.paginator, "paginate", return_value=[ret_val]):
            self.assertEqual(
                boto3_elasticsearch.list_elasticsearch_instance_types(
                    elasticsearch_version="1.0", **CONN_PARAMETERS
                ),
                {"result": True, "response": ret_val["ElasticsearchInstanceTypes"]},
            )

    def test_list_elasticsearch_instance_types_error(self):
        """
        Test that when calling list_elasticsearch_instance_types and boto3
        returns an error, it returns {'result': False, 'error': 'the error'}.
        """
        with patch.object(
            self.paginator,
            "paginate",
            side_effect=ClientError(ERROR_CONTENT, "list_elasticsearch_instance_types"),
        ):
            result = boto3_elasticsearch.list_elasticsearch_instance_types(
                elasticsearch_version="1.0", **CONN_PARAMETERS
            )
            self.assertFalse(result["result"])
            self.assertEqual(
                result.get("error", ""),
                ERROR_MESSAGE.format(101, "list_elasticsearch_instance_types"),
            )

    def test_list_elasticsearch_versions_positive(self):
        """
        Test that when calling list_elasticsearch_versions and it
        succeeds, it returns {'result': True, 'response': some_value}.
        """
        ret_val = {"ElasticsearchVersions": ["string"], "NextToken": "string"}
        with patch.object(self.paginator, "paginate", return_value=[ret_val]):
            self.assertEqual(
                boto3_elasticsearch.list_elasticsearch_versions(**CONN_PARAMETERS),
                {"result": True, "response": ret_val["ElasticsearchVersions"]},
            )

    def test_list_elasticsearch_versions_error(self):
        """
        Test that when calling list_elasticsearch_versions and boto3
        returns an error, it returns {'result': False, 'error': 'the error'}.
        """
        with patch.object(
            self.paginator,
            "paginate",
            side_effect=ClientError(ERROR_CONTENT, "list_elasticsearch_versions"),
        ):
            result = boto3_elasticsearch.list_elasticsearch_versions(**CONN_PARAMETERS)
            self.assertFalse(result["result"])
            self.assertEqual(
                result.get("error", ""),
                ERROR_MESSAGE.format(101, "list_elasticsearch_versions"),
            )

    def test_purchase_reserved_elasticsearch_instance_offering_positive(self):
        """
        Test that when calling purchase_reserved_elasticsearch_instance_offering and it
        succeeds, it returns {'result': True, 'response': some_value}.
        """
        ret_val = {
            "ReservedElasticsearchInstanceId": "string",
            "ReservationName": "string",
        }
        with patch.object(
            self.conn,
            "purchase_reserved_elasticsearch_instance_offering",
            return_value=ret_val,
        ):
            self.assertEqual(
                boto3_elasticsearch.purchase_reserved_elasticsearch_instance_offering(
                    reserved_elasticsearch_instance_offering_id="foo",
                    reservation_name="bar",
                    **CONN_PARAMETERS
                ),
                {"result": True, "response": ret_val},
            )

    def test_purchase_reserved_elasticsearch_instance_offering_error(self):
        """
        Test that when calling purchase_reserved_elasticsearch_instance_offering and boto3
        returns an error, it returns {'result': False, 'error': 'the error'}.
        """
        with patch.object(
            self.conn,
            "purchase_reserved_elasticsearch_instance_offering",
            side_effect=ClientError(
                ERROR_CONTENT, "purchase_reserved_elasticsearch_instance_offering"
            ),
        ):
            result = (
                boto3_elasticsearch.purchase_reserved_elasticsearch_instance_offering(
                    reserved_elasticsearch_instance_offering_id="foo",
                    reservation_name="bar",
                    **CONN_PARAMETERS
                )
            )
            self.assertFalse(result["result"])
            self.assertEqual(
                result.get("error", ""),
                ERROR_MESSAGE.format(
                    101, "purchase_reserved_elasticsearch_instance_offering"
                ),
            )

    def test_start_elasticsearch_service_software_update_positive(self):
        """
        Test that when calling start_elasticsearch_service_software_update and it
        succeeds, it returns {'result': True, 'response': some_value}.
        """
        ret_val = {
            "ServiceSoftwareOptions": {
                "CurrentVersion": "string",
                "NewVersion": "string",
                "UpdateAvailable": True,
                "Cancellable": True,
                "UpdateStatus": "PENDING_UPDATE",
                "Description": "string",
                "AutomatedUpdateDate": datetime.datetime(2015, 1, 1),
            }
        }
        with patch.object(
            self.conn,
            "start_elasticsearch_service_software_update",
            return_value=ret_val,
        ):
            self.assertEqual(
                boto3_elasticsearch.start_elasticsearch_service_software_update(
                    domain_name="testdomain", **CONN_PARAMETERS
                ),
                {"result": True, "response": ret_val["ServiceSoftwareOptions"]},
            )

    def test_start_elasticsearch_service_software_update_error(self):
        """
        Test that when calling start_elasticsearch_service_software_update and boto3
        returns an error, it returns {'result': False, 'error': 'the error'}.
        """
        with patch.object(
            self.conn,
            "start_elasticsearch_service_software_update",
            side_effect=ClientError(
                ERROR_CONTENT, "start_elasticsearch_service_software_update"
            ),
        ):
            result = boto3_elasticsearch.start_elasticsearch_service_software_update(
                domain_name="testdomain", **CONN_PARAMETERS
            )
            self.assertFalse(result["result"])
            self.assertEqual(
                result.get("error", ""),
                ERROR_MESSAGE.format(
                    101, "start_elasticsearch_service_software_update"
                ),
            )

    def test_upgrade_elasticsearch_domain_positive(self):
        """
        Test that when calling upgrade_elasticsearch_domain and it
        succeeds, it returns {'result': True, 'response': some_value}.
        """
        ret_val = {
            "DomainName": "string",
            "TargetVersion": "string",
            "PerformCheckOnly": True,
        }
        with patch.object(
            self.conn, "upgrade_elasticsearch_domain", return_value=ret_val
        ):
            self.assertEqual(
                boto3_elasticsearch.upgrade_elasticsearch_domain(
                    domain_name="testdomain", target_version="1.1", **CONN_PARAMETERS
                ),
                {"result": True, "response": ret_val},
            )

    def test_upgrade_elasticsearch_domain_error(self):
        """
        Test that when calling upgrade_elasticsearch_domain and boto3
        returns an error, it returns {'result': False, 'error': 'the error'}.
        """
        with patch.object(
            self.conn,
            "upgrade_elasticsearch_domain",
            side_effect=ClientError(ERROR_CONTENT, "upgrade_elasticsearch_domain"),
        ):
            result = boto3_elasticsearch.upgrade_elasticsearch_domain(
                domain_name="testdomain", target_version="1.1", **CONN_PARAMETERS
            )
            self.assertFalse(result["result"])
            self.assertEqual(
                result.get("error", ""),
                ERROR_MESSAGE.format(101, "upgrade_elasticsearch_domain"),
            )
