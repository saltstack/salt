import random
import string
import uuid

import salt.config
import salt.modules.boto_sns as boto_sns
from tests.support.mixins import LoaderModuleMockMixin
from tests.support.unit import TestCase, skipIf

try:
    import boto3

    HAS_BOTO3 = True
except ImportError:
    HAS_BOTO3 = False

try:
    from moto import mock_sns

    HAS_MOTO = True
except ImportError:
    HAS_MOTO = False


REGION = "us-east-1"
ACCESS_KEY = "GKTADJGHEIQSXMKKRBJ08H"
SECRET_KEY = "askdjghsdfjkghWupUjasdflkdfklgjsdfjajkghs"
CONN_PARAMETERS = {
    "region": REGION,
    "key": ACCESS_KEY,
    "keyid": SECRET_KEY,
    "profile": {},
}


def _random_topic_name():
    topic_name = "boto3_topic-{}".format(
        "".join((random.choice(string.ascii_lowercase)) for char in range(12))
    )
    return topic_name


@skipIf(HAS_BOTO3 is False, "The boto3 module must be installed.")
@skipIf(HAS_MOTO is False, "The moto module must be installed.")
class BotoSnsTestCase(TestCase, LoaderModuleMockMixin):
    """
    TestCase for salt.modules.boto_sns module
    """

    conn = None

    def setup_loader_modules(self):
        self.opts = salt.config.DEFAULT_MINION_OPTS.copy()
        utils = salt.loader.utils(
            self.opts,
            whitelist=["boto3", "args", "systemd", "path", "platform"],
            context={},
        )
        return {boto_sns: {"__utils__": utils}}

    def setUp(self):
        super().setUp()
        boto_sns.__init__(self.opts)
        del self.opts

        self.mock = mock_sns()
        self.mock.start()
        self.session = boto3.session.Session(
            aws_access_key_id=ACCESS_KEY,
            aws_secret_access_key=SECRET_KEY,
            region_name=REGION,
        )
        self.conn = self.session.client("sns")

    def tearDown(self):
        self.mock.stop()

    def test_topic_exists_that_does_exist(self):
        name = _random_topic_name()
        resp = self.conn.create_topic(Name=name)
        self.assertTrue(boto_sns.exists(name, **CONN_PARAMETERS))

    def test_topic_exists_that_doesnt_exist(self):
        self.assertFalse(boto_sns.exists(_random_topic_name(), **CONN_PARAMETERS))

    def test_list_all_topics(self):
        topics = {}
        for count in range(1, 20):
            name = _random_topic_name()
            resp = self.conn.create_topic(Name=name)
            topics.update({name: resp["TopicArn"]})
        self.assertDictEqual(boto_sns.get_all_topics(**CONN_PARAMETERS), topics)

    def test_list_more_than_one_hundred_topics(self):
        topics = {}
        for count in range(1, 200):
            name = _random_topic_name()
            resp = self.conn.create_topic(Name=name)
            topics.update({name: resp["TopicArn"]})
        self.assertDictEqual(boto_sns.get_all_topics(**CONN_PARAMETERS), topics)

    def test_create_topic(self):
        self.assertTrue(boto_sns.create(_random_topic_name(), **CONN_PARAMETERS))

    def test_create_topic_that_already_exists(self):
        topic_name = _random_topic_name()
        resp = self.conn.create_topic(Name=topic_name)
        self.assertTrue(boto_sns.create(topic_name, **CONN_PARAMETERS))

    def test_delete_topic(self):
        resp = self.conn.create_topic(Name=_random_topic_name())
        self.assertTrue(boto_sns.delete(resp["TopicArn"], **CONN_PARAMETERS))

    def test_delete_topic_that_doesnt_exist(self):
        topic = "arn:aws:sns:{}:{}:{}".format(
            REGION, "0123456789", _random_topic_name()
        )
        self.assertTrue(boto_sns.delete(topic, **CONN_PARAMETERS))

    def test_list_subscriptions(self):
        resp = self.conn.create_topic(Name=_random_topic_name())
        sub = self.conn.subscribe(
            TopicArn=resp["TopicArn"], Protocol="http", Endpoint="http://127.0.0.1"
        )
        resp = boto_sns.get_all_subscriptions_by_topic(
            resp["TopicArn"], **CONN_PARAMETERS
        )
        self.assertIn(
            sub["SubscriptionArn"], [item["SubscriptionArn"] for item in resp]
        )

    def test_list_more_than_one_hundred_subscriptions(self):
        resp = self.conn.create_topic(Name=_random_topic_name())
        subscriptions = []
        for count in range(1, 200):
            endpoint = "http://127.0.0.{}".format(count)
            sub = self.conn.subscribe(
                TopicArn=resp["TopicArn"], Protocol="http", Endpoint=endpoint
            )
            subscriptions.append(sub["SubscriptionArn"])
        resp = boto_sns.get_all_subscriptions_by_topic(
            resp["TopicArn"], **CONN_PARAMETERS
        )
        self.assertListEqual(subscriptions, [item["SubscriptionArn"] for item in resp])

    def test_subscribe_to_topic_that_exists(self):
        resp = self.conn.create_topic(Name=_random_topic_name())
        self.assertTrue(
            boto_sns.subscribe(
                resp["TopicArn"], "http", "http://127.0.0.1", **CONN_PARAMETERS
            )
        )

    def test_subscribe_to_topic_that_doesnt_exist(self):
        topic = "arn:aws:sns:{}:{}:{}".format(
            REGION, "0123456789", _random_topic_name()
        )
        self.assertFalse(
            boto_sns.subscribe(topic, "http", "http://127.0.0.1", **CONN_PARAMETERS)
        )

    def test_unsubscribe_from_topic_subscribed_to(self):
        resp = self.conn.create_topic(Name=_random_topic_name())
        sub = self.conn.subscribe(
            TopicArn=resp["TopicArn"], Protocol="http", Endpoint="http://127.0.0.1"
        )
        self.assertTrue(
            boto_sns.unsubscribe(
                resp["TopicArn"], sub["SubscriptionArn"], **CONN_PARAMETERS
            )
        )

    def test_unsubscribe_from_topic_not_subscribed_to(self):
        resp = self.conn.create_topic(Name=_random_topic_name())
        sub_arn = "arn:aws:sns:{}:{}:{}-{}".format(
            REGION, "0123456789", _random_topic_name(), uuid.uuid4()
        )
        self.assertTrue(
            boto_sns.unsubscribe(resp["TopicArn"], sub_arn, **CONN_PARAMETERS)
        )

    def test_unsubscribe_from_invalid_topic(self):
        topic_arn = "arn:aws:sns:{}:{}:{}".format(
            REGION, "0123456789", _random_topic_name()
        )
        sub_arn = "{}-{}".format(topic_arn, uuid.uuid4())
        self.assertFalse(boto_sns.unsubscribe(topic_arn, sub_arn, **CONN_PARAMETERS))
