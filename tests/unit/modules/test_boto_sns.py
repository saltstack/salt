import random
import string
import uuid

import salt.config
import salt.modules.boto_sns as boto_sns
from tests.support.mixins import LoaderModuleMockMixin
from tests.support.unit import TestCase, skipIf

try:
    import boto

    HAS_BOTO = True
except ImportError:
    HAS_BOTO = False

try:
    from moto import mock_sns_deprecated

    HAS_MOTO = True
except ImportError:
    HAS_MOTO = False


def _random_topic_name():
    topic_name = "boto_topic-{}".format(
        "".join((random.choice(string.ascii_lowercase)) for char in range(12))
    )
    return topic_name


@skipIf(HAS_BOTO is False, "The boto module must be installed.")
@skipIf(HAS_MOTO is False, "The moto module must be installed.")
class BotoSnsTestCase(TestCase, LoaderModuleMockMixin):
    """
    TestCase for salt.modules.boto_sns module
    """

    region = "us-east-1"
    access_key = "GKTADJGHEIQSXMKKRBJ08H"
    secret_key = "askdjghsdfjkghWupUjasdflkdfklgjsdfjajkghs"

    conn = None

    def setup_loader_modules(self):
        self.opts = salt.config.DEFAULT_MINION_OPTS.copy()
        utils = salt.loader.utils(
            self.opts,
            whitelist=["boto", "args", "systemd", "path", "platform"],
            context={},
        )
        return {boto_sns: {"__utils__": utils}}

    def setUp(self):
        super().setUp()
        boto_sns.__init__(self.opts)
        del self.opts

        self.conn_parameters = {
            "region": self.region,
            "key": self.access_key,
            "keyid": self.secret_key,
            "profile": {},
        }

        self.mock = mock_sns_deprecated()
        self.mock.start()
        self.conn = boto.connect_sns()

    def tearDown(self):
        self.mock.stop()

    def test_topic_exists_that_does_exist(self):
        name = _random_topic_name()
        resp = self.conn.create_topic(name)
        self.assertTrue(boto_sns.exists(name, **self.conn_parameters))

    def test_topic_exists_that_doesnt_exist(self):
        self.assertFalse(boto_sns.exists(_random_topic_name(), **self.conn_parameters))

    def test_list_all_topics(self):
        topics = {}
        for count in range(1, 20):
            name = _random_topic_name()
            resp = self.conn.create_topic(name)
            topics.update(
                {name: resp["CreateTopicResponse"]["CreateTopicResult"]["TopicArn"]}
            )
        self.assertDictEqual(boto_sns.get_all_topics(**self.conn_parameters), topics)

    def test_list_more_than_one_hundred_topics(self):
        topics = {}
        for count in range(1, 200):
            name = _random_topic_name()
            resp = self.conn.create_topic(name)
            topics.update(
                {name: resp["CreateTopicResponse"]["CreateTopicResult"]["TopicArn"]}
            )
        self.assertDictEqual(boto_sns.get_all_topics(**self.conn_parameters), topics)

    def test_create_topic(self):
        self.assertTrue(boto_sns.create(_random_topic_name(), **self.conn_parameters))

    def test_create_topic_that_already_exists(self):
        topic_name = _random_topic_name()
        resp = self.conn.create_topic(topic_name)
        self.assertTrue(boto_sns.create(topic_name, **self.conn_parameters))

    def test_delete_topic(self):
        resp = self.conn.create_topic(_random_topic_name())
        self.assertTrue(
            boto_sns.delete(
                resp["CreateTopicResponse"]["CreateTopicResult"]["TopicArn"],
                **self.conn_parameters
            )
        )

    def test_delete_topic_that_doesnt_exist(self):
        topic = "arn:aws:sns:{}:{}:{}".format(
            self.region, "0123456789", _random_topic_name()
        )
        self.assertTrue(boto_sns.delete(topic, **self.conn_parameters))

    def test_list_subscriptions(self):
        resp = self.conn.create_topic(_random_topic_name())
        sub = self.conn.subscribe(
            resp["CreateTopicResponse"]["CreateTopicResult"]["TopicArn"],
            "http",
            "http://127.0.0.1",
        )
        resp = boto_sns.get_all_subscriptions_by_topic(
            resp["CreateTopicResponse"]["CreateTopicResult"]["TopicArn"],
            **self.conn_parameters
        )
        self.assertIn(
            sub["SubscribeResponse"]["SubscribeResult"]["SubscriptionArn"],
            [item["SubscriptionArn"] for item in resp],
        )

    def test_list_more_than_one_hundred_subscriptions(self):
        resp = self.conn.create_topic(_random_topic_name())
        subscriptions = []
        for count in range(1, 200):
            endpoint = "http://127.0.0.{}".format(count)
            sub = self.conn.subscribe(
                resp["CreateTopicResponse"]["CreateTopicResult"]["TopicArn"],
                "http",
                endpoint,
            )
            subscriptions.append(
                sub["SubscribeResponse"]["SubscribeResult"]["SubscriptionArn"]
            )
        resp = boto_sns.get_all_subscriptions_by_topic(
            resp["CreateTopicResponse"]["CreateTopicResult"]["TopicArn"],
            **self.conn_parameters
        )
        self.assertListEqual(subscriptions, [item["SubscriptionArn"] for item in resp])

    def test_subscribe_to_topic_that_exists(self):
        resp = self.conn.create_topic(_random_topic_name())
        self.assertTrue(
            boto_sns.subscribe(
                resp["CreateTopicResponse"]["CreateTopicResult"]["TopicArn"],
                "http",
                "http://127.0.0.1",
                **self.conn_parameters
            )
        )

    def test_subscribe_to_topic_that_doesnt_exist(self):
        topic = "arn:aws:sns:{}:{}:{}".format(
            self.region, "0123456789", _random_topic_name()
        )
        self.assertFalse(
            boto_sns.subscribe(
                topic, "http", "http://127.0.0.1", **self.conn_parameters
            )
        )

    def test_unsubscribe_from_topic_subscribed_to(self):
        resp = self.conn.create_topic(_random_topic_name())
        sub = self.conn.subscribe(
            resp["CreateTopicResponse"]["CreateTopicResult"]["TopicArn"],
            "http",
            "http://127.0.0.1",
        )
        self.assertTrue(
            boto_sns.unsubscribe(
                resp["CreateTopicResponse"]["CreateTopicResult"]["TopicArn"],
                sub["SubscribeResponse"]["SubscribeResult"]["SubscriptionArn"],
                **self.conn_parameters
            )
        )

    def test_unsubscribe_from_topic_not_subscribed_to(self):
        resp = self.conn.create_topic(_random_topic_name())
        sub_arn = "arn:aws:sns:{}:{}:{}-{}".format(
            self.region, "0123456789", _random_topic_name(), uuid.uuid4()
        )
        self.assertTrue(
            boto_sns.unsubscribe(
                resp["CreateTopicResponse"]["CreateTopicResult"]["TopicArn"],
                sub_arn,
                **self.conn_parameters
            )
        )

    def test_unsubscribe_from_invalid_topic(self):
        topic_arn = "arn:aws:sns:{}:{}:{}".format(
            self.region, "0123456789", _random_topic_name()
        )
        sub_arn = "{}-{}".format(topic_arn, uuid.uuid4())
        self.assertFalse(
            boto_sns.unsubscribe(topic_arn, sub_arn, **self.conn_parameters)
        )
