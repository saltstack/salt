# -*- coding: utf-8 -*-

# Import Python libs
from __future__ import absolute_import, print_function, unicode_literals

import logging
import random
import string

# Import Salt libs
import salt.config
import salt.loader
import salt.modules.boto_cloudwatch_event as boto_cloudwatch_event
from salt.ext.six.moves import range  # pylint: disable=import-error,redefined-builtin

# Import Salt Testing libs
from tests.support.mixins import LoaderModuleMockMixin
from tests.support.mock import MagicMock, patch
from tests.support.unit import TestCase, skipIf

# Import 3rd-party libs
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
    create_rule_ret = dict(Name=rule_name,)
    target_ret = dict(Id="target1",)


class BotoCloudWatchEventTestCaseBase(TestCase, LoaderModuleMockMixin):
    conn = None

    def setup_loader_modules(self):
        self.opts = opts = salt.config.DEFAULT_MINION_OPTS.copy()
        utils = salt.loader.utils(
            opts, whitelist=["boto3", "args", "systemd", "path", "platform"], context={}
        )
        return {boto_cloudwatch_event: {"__utils__": utils}}

    def setUp(self):
        super(BotoCloudWatchEventTestCaseBase, self).setUp()
        boto_cloudwatch_event.__init__(self.opts)
        del self.opts

        # Set up MagicMock to replace the boto3 session
        # connections keep getting cached from prior tests, can't find the
        # correct context object to clear it. So randomize the cache key, to prevent any
        # cache hits
        conn_parameters["key"] = "".join(
            random.choice(string.ascii_lowercase + string.digits) for _ in range(50)
        )

        self.patcher = patch("boto3.session.Session")
        self.addCleanup(self.patcher.stop)
        self.addCleanup(delattr, self, "patcher")
        mock_session = self.patcher.start()

        session_instance = mock_session.return_value
        self.conn = MagicMock()
        self.addCleanup(delattr, self, "conn")
        session_instance.client.return_value = self.conn


class BotoCloudWatchEventTestCaseMixin(object):
    pass


@skipIf(HAS_BOTO is False, "The boto module must be installed.")
class BotoCloudWatchEventTestCase(
    BotoCloudWatchEventTestCaseBase, BotoCloudWatchEventTestCaseMixin
):
    """
    TestCase for salt.modules.boto_cloudwatch_event module
    """

    def test_that_when_checking_if_a_rule_exists_and_a_rule_exists_the_rule_exists_method_returns_true(
        self,
    ):
        """
        Tests checking event existence when the event already exists
        """
        self.conn.list_rules.return_value = {"Rules": [rule_ret]}
        result = boto_cloudwatch_event.exists(Name=rule_name, **conn_parameters)

        self.assertTrue(result["exists"])

    def test_that_when_checking_if_a_rule_exists_and_a_rule_does_not_exist_the_exists_method_returns_false(
        self,
    ):
        """
        Tests checking rule existence when the rule does not exist
        """
        self.conn.list_rules.return_value = {"Rules": []}
        result = boto_cloudwatch_event.exists(Name=rule_name, **conn_parameters)

        self.assertFalse(result["exists"])

    def test_that_when_checking_if_a_rule_exists_and_boto3_returns_an_error_the_rule_exists_method_returns_error(
        self,
    ):
        """
        Tests checking rule existence when boto returns an error
        """
        self.conn.list_rules.side_effect = ClientError(error_content, "list_rules")
        result = boto_cloudwatch_event.exists(Name=rule_name, **conn_parameters)

        self.assertEqual(
            result.get("error", {}).get("message"), error_message.format("list_rules")
        )

    def test_that_when_describing_rule_and_rule_exists_the_describe_rule_method_returns_rule(
        self,
    ):
        """
        Tests describe rule for an existing rule
        """
        self.conn.describe_rule.return_value = rule_ret
        result = boto_cloudwatch_event.describe(Name=rule_name, **conn_parameters)

        self.assertEqual(result.get("rule"), rule_ret)

    def test_that_when_describing_rule_and_rule_does_not_exists_the_describe_method_returns_none(
        self,
    ):
        """
        Tests describe rule for an non existent rule
        """
        self.conn.describe_rule.side_effect = not_found_error
        result = boto_cloudwatch_event.describe(Name=rule_name, **conn_parameters)

        self.assertNotEqual(result.get("error"), None)

    def test_that_when_describing_rule_and_boto3_returns_error_the_describe_method_returns_error(
        self,
    ):
        self.conn.describe_rule.side_effect = ClientError(
            error_content, "describe_rule"
        )
        result = boto_cloudwatch_event.describe(Name=rule_name, **conn_parameters)

        self.assertEqual(
            result.get("error", {}).get("message"),
            error_message.format("describe_rule"),
        )

    def test_that_when_creating_a_rule_succeeds_the_create_rule_method_returns_true(
        self,
    ):
        """
        tests True when rule created
        """
        self.conn.put_rule.return_value = create_rule_ret
        result = boto_cloudwatch_event.create_or_update(
            Name=rule_name,
            Description=rule_desc,
            ScheduleExpression=rule_sched,
            **conn_parameters
        )
        self.assertTrue(result["created"])

    def test_that_when_creating_a_rule_fails_the_create_method_returns_error(self):
        """
        tests False when rule not created
        """
        self.conn.put_rule.side_effect = ClientError(error_content, "put_rule")
        result = boto_cloudwatch_event.create_or_update(
            Name=rule_name,
            Description=rule_desc,
            ScheduleExpression=rule_sched,
            **conn_parameters
        )
        self.assertEqual(
            result.get("error", {}).get("message"), error_message.format("put_rule")
        )

    def test_that_when_deleting_a_rule_succeeds_the_delete_method_returns_true(self):
        """
        tests True when delete rule succeeds
        """
        self.conn.delete_rule.return_value = {}
        result = boto_cloudwatch_event.delete(Name=rule_name, **conn_parameters)

        self.assertTrue(result.get("deleted"))
        self.assertEqual(result.get("error"), None)

    def test_that_when_deleting_a_rule_fails_the_delete_method_returns_error(self):
        """
        tests False when delete rule fails
        """
        self.conn.delete_rule.side_effect = ClientError(error_content, "delete_rule")
        result = boto_cloudwatch_event.delete(Name=rule_name, **conn_parameters)
        self.assertFalse(result.get("deleted"))
        self.assertEqual(
            result.get("error", {}).get("message"), error_message.format("delete_rule")
        )

    def test_that_when_listing_targets_and_rule_exists_the_list_targets_method_returns_targets(
        self,
    ):
        """
        Tests listing targets for an existing rule
        """
        self.conn.list_targets_by_rule.return_value = {"Targets": [target_ret]}
        result = boto_cloudwatch_event.list_targets(Rule=rule_name, **conn_parameters)

        self.assertEqual(result.get("targets"), [target_ret])

    def test_that_when_listing_targets_and_rule_does_not_exist_the_list_targets_method_returns_error(
        self,
    ):
        """
        Tests list targets for an non existent rule
        """
        self.conn.list_targets_by_rule.side_effect = not_found_error
        result = boto_cloudwatch_event.list_targets(Rule=rule_name, **conn_parameters)

        self.assertNotEqual(result.get("error"), None)

    def test_that_when_putting_targets_succeeds_the_put_target_method_returns_no_failures(
        self,
    ):
        """
        tests None when targets added
        """
        self.conn.put_targets.return_value = {"FailedEntryCount": 0}
        result = boto_cloudwatch_event.put_targets(
            Rule=rule_name, Targets=[], **conn_parameters
        )
        self.assertIsNone(result["failures"])

    def test_that_when_putting_targets_fails_the_put_targets_method_returns_error(self):
        """
        tests False when thing type not created
        """
        self.conn.put_targets.side_effect = ClientError(error_content, "put_targets")
        result = boto_cloudwatch_event.put_targets(
            Rule=rule_name, Targets=[], **conn_parameters
        )
        self.assertEqual(
            result.get("error", {}).get("message"), error_message.format("put_targets")
        )

    def test_that_when_removing_targets_succeeds_the_remove_targets_method_returns_true(
        self,
    ):
        """
        tests True when remove targets succeeds
        """
        self.conn.remove_targets.return_value = {"FailedEntryCount": 0}
        result = boto_cloudwatch_event.remove_targets(
            Rule=rule_name, Ids=[], **conn_parameters
        )

        self.assertIsNone(result["failures"])
        self.assertEqual(result.get("error"), None)

    def test_that_when_removing_targets_fails_the_remove_targets_method_returns_error(
        self,
    ):
        """
        tests False when remove targets fails
        """
        self.conn.remove_targets.side_effect = ClientError(
            error_content, "remove_targets"
        )
        result = boto_cloudwatch_event.remove_targets(
            Rule=rule_name, Ids=[], **conn_parameters
        )
        self.assertEqual(
            result.get("error", {}).get("message"),
            error_message.format("remove_targets"),
        )
