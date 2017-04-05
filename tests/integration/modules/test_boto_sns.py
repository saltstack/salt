# -*- coding: utf-8 -*-
'''
Validate the boto_sns module
'''

# Import Python libs
from __future__ import absolute_import
import re

# Import Salt Testing libs
from tests.support.case import ModuleCase
from tests.support.unit import skipIf

# Import 3rd-party libs
NO_BOTO_MODULE = True
BOTO_NOT_CONFIGURED = True
try:
    import boto
    NO_BOTO_MODULE = False
    try:
        boto.connect_iam()
        BOTO_NOT_CONFIGURED = False
    except boto.exception.NoAuthHandlerFound:
        pass
except ImportError:
    pass


@skipIf(
    NO_BOTO_MODULE,
    'Please install the boto library before running boto integration tests.'
)
@skipIf(
    BOTO_NOT_CONFIGURED,
    'Please setup boto AWS credentials before running boto integration tests.'
)
class BotoSNSTest(ModuleCase):

    def setUp(self):
        # The name of the topic you want to create.
        # Constraints: Topic names must be made up of only uppercase and
        # lowercase ASCII letters, numbers, underscores, and hyphens,
        # and must be between 1 and 256 characters long.
        # http://docs.aws.amazon.com/sns/latest/api/API_CreateTopic.html
        self.topic_name = re.sub(r'[^a-zA-Z_-]', '_', self.id())[0:256]
        self.topic_names = [self.topic_name]
        self.run_function('boto_sns.delete', name=self.topic_name)

    def tearDown(self):
        for topic in self.topic_names:
            self.run_function('boto_sns.delete', name=topic)

    def test_exists_non_existing(self):
        ret = self.run_function('boto_sns.exists', ['nonexistent'])
        self.assertSaltModuleFalseReturn(ret)

    def test_exists_existing(self):
        self.run_function('boto_sns.create', [self.topic_name])
        ret = self.run_function('boto_sns.exists', [self.topic_name])
        self.assertSaltModuleTrueReturn(ret)

    def test_create(self):
        ret = self.run_function('boto_sns.create', [self.topic_name])
        self.assertSaltModuleTrueReturn(ret)

        ret = self.run_function('boto_sns.get_all_topics')
        self.assertIn(self.topic_name, list(ret.keys()))
        self.assertIn(self._get_arn(self.topic_name), list(ret.values()))

    def test_delete_non_existing(self):
        ret = self.run_function('boto_sns.delete', [self.topic_name])
        self.assertSaltModuleTrueReturn(ret)

    def test_delete_existing(self):
        self.run_function('boto_sns.create', [self.topic_name])
        ret = self.run_function('boto_sns.delete', [self.topic_name])
        self.assertSaltModuleTrueReturn(ret)

        ret = self.run_function('boto_sns.get_all_topics')
        self.assertNotIn(self.topic_name, list(ret.keys()))
        self.assertNotIn(self._get_arn(self.topic_name), list(ret.values()))

    def test_get_all_topics(self):
        self.topic_names.append(self.topic_name + '-2')
        for topic in self.topic_names:
            self.run_function('boto_sns.create', [topic])

        ret = self.run_function('boto_sns.get_all_topics')

        for topic in self.topic_names:
            self.assertIn(topic, list(ret.keys()))
            self.assertIn(self._get_arn(topic), list(ret.values()))

    def test_subscribe_and_get_all_subscriptions_by_topic(self):
        topic_name = self.topic_name
        ret = self.run_function('boto_sns.create', [topic_name])

        ret = self.run_function(
            'boto_sns.subscribe',
            [topic_name, 'https', 'https://www.example.com/sns/endpoint']
        )
        self.assertSaltModuleTrueReturn(ret)

        ret = self.run_function('boto_sns.get_all_subscriptions_by_topic',
                                [topic_name])
        self.assertDictContainsSubset({
            'Protocol': 'https',
            'Endpoint': 'https://www.example.com/sns/endpoint'
        }, ret[0])

    def _get_arn(self, name):
        return 'arn:aws:sns:us-east-1:{0}:{1}'.format(self.account_id, name)

    @property
    def account_id(self):
        if not hasattr(self, '_account_id'):
            account_id = self.run_function('boto_iam.get_account_id')
            setattr(self, '_account_id', account_id)
        return self._account_id

    def assertSaltModuleTrueReturn(self, ret):
        self.assertIsInstance(ret, bool)
        self.assertTrue(ret)

    def assertSaltModuleFalseReturn(self, ret):
        self.assertIsInstance(ret, bool)
        self.assertFalse(ret)
