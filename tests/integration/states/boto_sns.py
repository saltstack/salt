# -*- coding: utf-8 -*-
"""
Tests for the boto_sns state
"""

# Import Python libs
from __future__ import absolute_import
import re

# Import Salt Testing libs
from salttesting import skipIf
from salttesting.helpers import ensure_in_syspath
ensure_in_syspath('../../')

# Import Salt libs
import integration

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
class BotoSNSTest(integration.ModuleCase,
                  integration.SaltReturnAssertsMixIn):

    def setUp(self):
        # The name of the topic you want to create.
        # Constraints: Topic names must be made up of only uppercase and
        # lowercase ASCII letters, numbers, underscores, and hyphens,
        # and must be between 1 and 256 characters long.
        # http://docs.aws.amazon.com/sns/latest/api/API_CreateTopic.html
        self.topic_name = re.sub(r'[^a-zA-Z_-]', '_', self.id())[0:256]
        self.run_function('boto_sns.delete', name=self.topic_name)

    def tearDown(self):
        self.run_function('boto_sns.delete', name=self.topic_name)

    def test_present_new_topic_no_subscriptions(self):
        ret = self.run_state('boto_sns.present',
                             name=self.topic_name)
        self.assertSaltTrueReturn(ret)
        self.assertInSaltReturn(self.topic_name, ret, 'name')
        self.assertInSaltComment(
            'AWS SNS topic {0} created.'.format(self.topic_name),
            ret
        )
        self.assertSaltStateChangesEqual(ret,
            {'old': None, 'new': {'topic': self.topic_name, 'subscriptions': []}})

    def test_present_new_topic_with_subscriptions(self):
        ret = self.run_state(
            'boto_sns.present',
            name=self.topic_name,
            subscriptions=[
                {'protocol': 'https',
                 'endpoint': 'https://www.example.com/sns/endpoint'
                },
                {'protocol': 'https',
                 'endpoint': 'https://www.example.com/sns/endpoint-2'
                }
            ]
        )
        self.assertSaltTrueReturn(ret)
        self.assertSaltStateChangesEqual(
            ret,
            {'old': None,
             'new': {
                'topic': self.topic_name,
                'subscriptions': [
                    {'protocol': 'https',
                     'endpoint': 'https://www.example.com/sns/endpoint'
                    },
                    {'protocol': 'https',
                     'endpoint': 'https://www.example.com/sns/endpoint-2'
                    }
                ]
             }
            }
        )
        self.assertInSaltComment(
            'AWS SNS subscription https:https://www.example.com/sns/endpoint set on topic {0}.'
            .format(self.topic_name),
            ret
        )
        self.assertInSaltComment(
            'AWS SNS subscription https:https://www.example.com/sns/endpoint-2 set on topic {0}.'
            .format(self.topic_name),
            ret
        )
        self.assertSubscriptionInTopic({
            'Protocol': 'https',
            'Endpoint': 'https://www.example.com/sns/endpoint'
        }, self.topic_name)
        self.assertSubscriptionInTopic({
            'Protocol': 'https',
            'Endpoint': 'https://www.example.com/sns/endpoint-2'
        }, self.topic_name)

    def test_present_is_idempotent(self):
        self.run_state(
            'boto_sns.present',
            name=self.topic_name,
            subscriptions=[
                {'protocol': 'https',
                 'endpoint': 'https://www.example.com/sns/endpoint'
                }
            ]
        )

        ret = self.run_state(
            'boto_sns.present',
            name=self.topic_name,
            subscriptions=[
                {'protocol': 'https',
                 'endpoint': 'https://www.example.com/sns/endpoint'
                }
            ]
        )

        self.assertSaltTrueReturn(ret)
        self.assertInSaltReturn(self.topic_name, ret, 'name')
        self.assertInSaltComment(
            'AWS SNS topic {0} present.'.format(self.topic_name),
            ret
        )
        self.assertInSaltComment(
            'AWS SNS subscription https:https://www.example.com/sns/endpoint already set on topic {0}.'
            .format(self.topic_name),
            ret
        )
        self.assertSaltStateChangesEqual(ret, {})

    def test_present_add_subscription_to_existing_topic_with_no_subscription(self):
        self.run_state('boto_sns.present', name=self.topic_name)
        ret = self.run_state(
            'boto_sns.present',
            name=self.topic_name,
            subscriptions=[
                {'protocol': 'https',
                 'endpoint': 'https://www.example.com/sns/endpoint'
                }
            ]
        )
        self.assertSaltTrueReturn(ret)
        self.assertSaltStateChangesEqual(
            ret,
            {'old': None,
             'new': {'subscriptions': [
                        {'protocol': 'https',
                         'endpoint': 'https://www.example.com/sns/endpoint'
                        }
                     ]
                    }
            }
        )
        self.assertInSaltComment(
            'AWS SNS subscription https:https://www.example.com/sns/endpoint set on topic {0}.'
            .format(self.topic_name),
            ret
        )

        self.assertSubscriptionInTopic({
            'Protocol': 'https',
            'Endpoint': 'https://www.example.com/sns/endpoint'
        }, self.topic_name)

    def test_present_add_new_subscription_to_existing_topic_with_subscriptions(self):
        self.run_state(
            'boto_sns.present',
            name=self.topic_name,
            subscriptions=[
                {'protocol': 'https',
                 'endpoint': 'https://www.example.com/sns/endpoint'
                }
            ]
        )
        ret = self.run_state(
            'boto_sns.present',
            name=self.topic_name,
            subscriptions=[
                {'protocol': 'https',
                 'endpoint': 'https://www.example.com/sns/endpoint-2'
                }
            ]
        )
        self.assertSaltTrueReturn(ret)
        self.assertSaltStateChangesEqual(
            ret,
            {'old': None,
             'new': {
                'subscriptions': [
                    {'protocol': 'https',
                     'endpoint': 'https://www.example.com/sns/endpoint-2'
                    }
                ]
             }
            }
        )
        self.assertInSaltComment(
            'AWS SNS subscription https:https://www.example.com/sns/endpoint-2 set on topic {0}.'
            .format(self.topic_name),
            ret
        )

        self.assertSubscriptionInTopic({
            'Protocol': 'https',
            'Endpoint': 'https://www.example.com/sns/endpoint'
        }, self.topic_name)
        self.assertSubscriptionInTopic({
            'Protocol': 'https',
            'Endpoint': 'https://www.example.com/sns/endpoint-2'
        }, self.topic_name)

    def test_present_test_mode_no_subscriptions(self):
        ret = self.run_state('boto_sns.present',
                             name=self.topic_name,
                             test=True)
        self.assertSaltNoneReturn(ret)
        self.assertInSaltReturn(self.topic_name, ret, 'name')
        self.assertInSaltComment(
            'AWS SNS topic {0} is set to be created.'.format(self.topic_name),
            ret
        )
        self.assertSaltStateChangesEqual(ret, {})
        ret = self.run_function('boto_sns.exists', name=self.topic_name)
        self.assertFalse(ret)

    def test_present_test_mode_with_subscriptions(self):
        self.run_state('boto_sns.present', name=self.topic_name)
        ret = self.run_state(
            'boto_sns.present',
            name=self.topic_name,
            subscriptions=[
                {'protocol': 'https',
                 'endpoint': 'https://www.example.com/sns/endpoint'
                }
            ],
            test=True
        )
        self.assertSaltNoneReturn(ret)
        self.assertSaltStateChangesEqual(ret, {})
        self.assertInSaltComment(
            'AWS SNS subscription https:https://www.example.com/sns/endpoint to be set on topic {0}.'
            .format(self.topic_name),
            ret
        )
        ret = self.run_function(
            'boto_sns.get_all_subscriptions_by_topic',
            name=self.topic_name
        )
        self.assertEqual([], ret)

    def test_absent_not_exist(self):
        ret = self.run_state('boto_sns.absent',
                             name=self.topic_name)
        self.assertSaltTrueReturn(ret)
        self.assertInSaltReturn(self.topic_name, ret, 'name')
        self.assertInSaltComment(
            'AWS SNS topic {0} does not exist.'.format(self.topic_name),
            ret
        )
        self.assertSaltStateChangesEqual(ret, {})

    def test_absent_already_exists(self):
        self.run_state('boto_sns.present',
                       name=self.topic_name)
        ret = self.run_state('boto_sns.absent',
                             name=self.topic_name)
        self.assertSaltTrueReturn(ret)
        self.assertInSaltReturn(self.topic_name, ret, 'name')
        self.assertInSaltComment(
            'AWS SNS topic {0} does not exist.'.format(self.topic_name),
            ret
        )
        self.assertSaltStateChangesEqual(
            ret, {'new': None, 'old': {'topic': self.topic_name}})

    def test_absent_test_mode(self):
        self.run_state('boto_sns.present', name=self.topic_name)
        ret = self.run_state('boto_sns.absent',
                             name=self.topic_name,
                             test=True)
        self.assertSaltNoneReturn(ret)
        self.assertInSaltReturn(self.topic_name, ret, 'name')
        self.assertInSaltComment(
            'AWS SNS topic {0} is set to be removed.'.format(self.topic_name),
            ret
        )
        self.assertSaltStateChangesEqual(ret, {})
        ret = self.run_function('boto_sns.exists', name=self.topic_name)
        self.assertTrue(ret)

    def assertSubscriptionInTopic(self, subscription, topic_name):
        ret = self.run_function(
            'boto_sns.get_all_subscriptions_by_topic',
            name=topic_name
        )
        for _subscription in ret:
            try:
                self.assertDictContainsSubset(subscription, _subscription)
                return True
            except AssertionError:
                continue
        raise self.failureException(
            'Subscription {0} not found in topic {1} subscriptions: {2}'
            .format(subscription, topic_name, ret)
        )
