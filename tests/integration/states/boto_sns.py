# -*- coding: utf-8 -*-
"""
Tests for the boto_sns state
"""
from salttesting import skipIf
from salttesting.helpers import ensure_in_syspath
ensure_in_syspath('../../')

import integration

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
        self.run_function('boto_sns.delete', name='my-state-test-topic')

    def tearDown(self):
        self.run_function('boto_sns.delete', name='my-state-test-topic')

    def test_present_not_exist(self):
        ret = self.run_state('boto_sns.present',
                             name='my-state-test-topic')
        self.assertSaltTrueReturn(ret)
        self.assertInSaltReturn('my-state-test-topic', ret, 'name')
        self.assertInSaltComment('AWS SNS topic my-state-test-topic created.',
                                 ret)
        self.assertSaltStateChangesEqual(
            ret, {'old': None, 'new': {'topic': 'my-state-test-topic'}}
        )

    def test_present_already_exist(self):
        self.run_state('boto_sns.present',
                       name='my-state-test-topic')
        ret = self.run_state('boto_sns.present',
                             name='my-state-test-topic')
        self.assertSaltTrueReturn(ret)
        self.assertInSaltReturn('my-state-test-topic', ret, 'name')
        self.assertInSaltComment('AWS SNS topic my-state-test-topic present.',
                                 ret)
        self.assertSaltStateChangesEqual(ret, {})

    def test_present_test_mode(self):
        ret = self.run_state('boto_sns.present',
                             name='my-state-test-topic',
                             test=True)
        self.assertSaltNoneReturn(ret)
        self.assertInSaltReturn('my-state-test-topic', ret, 'name')
        self.assertInSaltComment(
            'AWS SNS topic my-state-test-topic is set to be created.', ret)
        self.assertSaltStateChangesEqual(ret, {})
        ret = self.run_function('boto_sns.exists', name='my-state-test-topic')
        self.assertFalse(ret)

    def test_absent_not_exist(self):
        ret = self.run_state('boto_sns.absent',
                             name='my-state-test-topic')
        self.assertSaltTrueReturn(ret)
        self.assertInSaltReturn('my-state-test-topic', ret, 'name')
        self.assertInSaltComment(
            'AWS SNS topic my-state-test-topic does not exist.', ret)
        self.assertSaltStateChangesEqual(ret, {})

    def test_absent_already_exists(self):
        self.run_state('boto_sns.present',
                       name='my-state-test-topic')
        ret = self.run_state('boto_sns.absent',
                             name='my-state-test-topic')
        self.assertSaltTrueReturn(ret)
        self.assertInSaltReturn('my-state-test-topic', ret, 'name')
        self.assertInSaltComment(
            'AWS SNS topic my-state-test-topic does not exist.', ret)
        self.assertSaltStateChangesEqual(
            ret, {'new': None, 'old': {'topic': 'my-state-test-topic'}})

    def test_absent_test_mode(self):
        self.run_state('boto_sns.present', name='my-state-test-topic')
        ret = self.run_state('boto_sns.absent',
                             name='my-state-test-topic',
                             test=True)
        self.assertSaltNoneReturn(ret)
        self.assertInSaltReturn('my-state-test-topic', ret, 'name')
        self.assertInSaltComment(
            'AWS SNS topic my-state-test-topic is set to be removed.', ret)
        self.assertSaltStateChangesEqual(ret, {})
        ret = self.run_function('boto_sns.exists', name='my-state-test-topic')
        self.assertTrue(ret)
