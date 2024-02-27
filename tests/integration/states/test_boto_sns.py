"""
Tests for the boto_sns state
"""

import re

import pytest

from tests.support.case import ModuleCase
from tests.support.mixins import SaltReturnAssertsMixin

try:
    import boto

    NO_BOTO_MODULE = False
except ImportError:
    NO_BOTO_MODULE = True


@pytest.mark.skipif(
    NO_BOTO_MODULE,
    reason="Please install the boto library before running boto integration tests.",
)
class BotoSNSTest(ModuleCase, SaltReturnAssertsMixin):
    def setUp(self):
        try:
            boto.connect_iam()
        except boto.exception.NoAuthHandlerFound:
            self.skipTest(
                "Please setup boto AWS credentials before running boto integration"
                " tests."
            )
        # The name of the topic you want to create.
        # Constraints: Topic names must be made up of only uppercase and
        # lowercase ASCII letters, numbers, underscores, and hyphens,
        # and must be between 1 and 256 characters long.
        # http://docs.aws.amazon.com/sns/latest/api/API_CreateTopic.html
        self.topic_name = re.sub(r"[^a-zA-Z_-]", "_", self.id())[0:256]
        self.run_function("boto_sns.delete", name=self.topic_name)

    def tearDown(self):
        self.run_function("boto_sns.delete", name=self.topic_name)

    def test_present_new_topic_no_subscriptions(self):
        ret = self.run_state("boto_sns.present", name=self.topic_name)
        self.assertSaltTrueReturn(ret)
        self.assertInSaltReturn(self.topic_name, ret, "name")
        self.assertInSaltComment(f"AWS SNS topic {self.topic_name} created.", ret)
        self.assertSaltStateChangesEqual(
            ret, {"old": None, "new": {"topic": self.topic_name, "subscriptions": []}}
        )

    def test_present_new_topic_with_subscriptions(self):
        ret = self.run_state(
            "boto_sns.present",
            name=self.topic_name,
            subscriptions=[
                {
                    "protocol": "https",
                    "endpoint": "https://www.example.com/sns/endpoint",
                },
                {
                    "protocol": "https",
                    "endpoint": "https://www.example.com/sns/endpoint-2",
                },
            ],
        )
        self.assertSaltTrueReturn(ret)
        self.assertSaltStateChangesEqual(
            ret,
            {
                "old": None,
                "new": {
                    "topic": self.topic_name,
                    "subscriptions": [
                        {
                            "protocol": "https",
                            "endpoint": "https://www.example.com/sns/endpoint",
                        },
                        {
                            "protocol": "https",
                            "endpoint": "https://www.example.com/sns/endpoint-2",
                        },
                    ],
                },
            },
        )
        self.assertInSaltComment(
            "AWS SNS subscription https:https://www.example.com/sns/endpoint set on"
            " topic {}.".format(self.topic_name),
            ret,
        )
        self.assertInSaltComment(
            "AWS SNS subscription https:https://www.example.com/sns/endpoint-2 set on"
            " topic {}.".format(self.topic_name),
            ret,
        )
        self.assertSubscriptionInTopic(
            {"Protocol": "https", "Endpoint": "https://www.example.com/sns/endpoint"},
            self.topic_name,
        )
        self.assertSubscriptionInTopic(
            {"Protocol": "https", "Endpoint": "https://www.example.com/sns/endpoint-2"},
            self.topic_name,
        )

    def test_present_is_idempotent(self):
        self.run_state(
            "boto_sns.present",
            name=self.topic_name,
            subscriptions=[
                {
                    "protocol": "https",
                    "endpoint": "https://www.example.com/sns/endpoint",
                }
            ],
        )

        ret = self.run_state(
            "boto_sns.present",
            name=self.topic_name,
            subscriptions=[
                {
                    "protocol": "https",
                    "endpoint": "https://www.example.com/sns/endpoint",
                }
            ],
        )

        self.assertSaltTrueReturn(ret)
        self.assertInSaltReturn(self.topic_name, ret, "name")
        self.assertInSaltComment(f"AWS SNS topic {self.topic_name} present.", ret)
        self.assertInSaltComment(
            "AWS SNS subscription https:https://www.example.com/sns/endpoint already"
            " set on topic {}.".format(self.topic_name),
            ret,
        )
        self.assertSaltStateChangesEqual(ret, {})

    def test_present_add_subscription_to_existing_topic_with_no_subscription(self):
        self.run_state("boto_sns.present", name=self.topic_name)
        ret = self.run_state(
            "boto_sns.present",
            name=self.topic_name,
            subscriptions=[
                {
                    "protocol": "https",
                    "endpoint": "https://www.example.com/sns/endpoint",
                }
            ],
        )
        self.assertSaltTrueReturn(ret)
        self.assertSaltStateChangesEqual(
            ret,
            {
                "old": None,
                "new": {
                    "subscriptions": [
                        {
                            "protocol": "https",
                            "endpoint": "https://www.example.com/sns/endpoint",
                        }
                    ]
                },
            },
        )
        self.assertInSaltComment(
            "AWS SNS subscription https:https://www.example.com/sns/endpoint set on"
            " topic {}.".format(self.topic_name),
            ret,
        )

        self.assertSubscriptionInTopic(
            {"Protocol": "https", "Endpoint": "https://www.example.com/sns/endpoint"},
            self.topic_name,
        )

    def test_present_add_new_subscription_to_existing_topic_with_subscriptions(self):
        self.run_state(
            "boto_sns.present",
            name=self.topic_name,
            subscriptions=[
                {
                    "protocol": "https",
                    "endpoint": "https://www.example.com/sns/endpoint",
                }
            ],
        )
        ret = self.run_state(
            "boto_sns.present",
            name=self.topic_name,
            subscriptions=[
                {
                    "protocol": "https",
                    "endpoint": "https://www.example.com/sns/endpoint-2",
                }
            ],
        )
        self.assertSaltTrueReturn(ret)
        self.assertSaltStateChangesEqual(
            ret,
            {
                "old": None,
                "new": {
                    "subscriptions": [
                        {
                            "protocol": "https",
                            "endpoint": "https://www.example.com/sns/endpoint-2",
                        }
                    ]
                },
            },
        )
        self.assertInSaltComment(
            "AWS SNS subscription https:https://www.example.com/sns/endpoint-2 set on"
            " topic {}.".format(self.topic_name),
            ret,
        )

        self.assertSubscriptionInTopic(
            {"Protocol": "https", "Endpoint": "https://www.example.com/sns/endpoint"},
            self.topic_name,
        )
        self.assertSubscriptionInTopic(
            {"Protocol": "https", "Endpoint": "https://www.example.com/sns/endpoint-2"},
            self.topic_name,
        )

    def test_present_test_mode_no_subscriptions(self):
        ret = self.run_state("boto_sns.present", name=self.topic_name, test=True)
        self.assertSaltNoneReturn(ret)
        self.assertInSaltReturn(self.topic_name, ret, "name")
        self.assertInSaltComment(
            f"AWS SNS topic {self.topic_name} is set to be created.", ret
        )
        self.assertSaltStateChangesEqual(ret, {})
        ret = self.run_function("boto_sns.exists", name=self.topic_name)
        self.assertFalse(ret)

    def test_present_test_mode_with_subscriptions(self):
        self.run_state("boto_sns.present", name=self.topic_name)
        ret = self.run_state(
            "boto_sns.present",
            name=self.topic_name,
            subscriptions=[
                {
                    "protocol": "https",
                    "endpoint": "https://www.example.com/sns/endpoint",
                }
            ],
            test=True,
        )
        self.assertSaltNoneReturn(ret)
        self.assertSaltStateChangesEqual(ret, {})
        self.assertInSaltComment(
            "AWS SNS subscription https:https://www.example.com/sns/endpoint to be set"
            " on topic {}.".format(self.topic_name),
            ret,
        )
        ret = self.run_function(
            "boto_sns.get_all_subscriptions_by_topic", name=self.topic_name
        )
        self.assertEqual([], ret)

    def test_absent_not_exist(self):
        ret = self.run_state("boto_sns.absent", name=self.topic_name)
        self.assertSaltTrueReturn(ret)
        self.assertInSaltReturn(self.topic_name, ret, "name")
        self.assertInSaltComment(
            f"AWS SNS topic {self.topic_name} does not exist.", ret
        )
        self.assertSaltStateChangesEqual(ret, {})

    def test_absent_already_exists(self):
        self.run_state("boto_sns.present", name=self.topic_name)
        ret = self.run_state("boto_sns.absent", name=self.topic_name)
        self.assertSaltTrueReturn(ret)
        self.assertInSaltReturn(self.topic_name, ret, "name")
        self.assertInSaltComment(
            f"AWS SNS topic {self.topic_name} does not exist.", ret
        )
        self.assertSaltStateChangesEqual(
            ret, {"new": None, "old": {"topic": self.topic_name}}
        )

    def test_absent_test_mode(self):
        self.run_state("boto_sns.present", name=self.topic_name)
        ret = self.run_state("boto_sns.absent", name=self.topic_name, test=True)
        self.assertSaltNoneReturn(ret)
        self.assertInSaltReturn(self.topic_name, ret, "name")
        self.assertInSaltComment(
            f"AWS SNS topic {self.topic_name} is set to be removed.", ret
        )
        self.assertSaltStateChangesEqual(ret, {})
        ret = self.run_function("boto_sns.exists", name=self.topic_name)
        self.assertTrue(ret)

    def assertSubscriptionInTopic(self, subscription, topic_name):
        ret = self.run_function(
            "boto_sns.get_all_subscriptions_by_topic", name=topic_name
        )
        for _subscription in ret:
            try:
                self.assertDictContainsSubset(subscription, _subscription)
                return True
            except AssertionError:
                continue
        raise self.failureException(
            "Subscription {} not found in topic {} subscriptions: {}".format(
                subscription, topic_name, ret
            )
        )
