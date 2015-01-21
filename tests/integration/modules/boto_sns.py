# -*- coding: utf-8 -*-
'''
Validate the boto_sns module
'''
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
class BotoSNSTest(integration.ModuleCase):

    def test_exists(self):
        ret = self.run_function('boto_sns.exists', ['nonexistent'])
        self.assertFalse(ret)

    def test_create(self):
        ret = self.run_function('boto_sns.create', ['my-test-topic'])
        self.assertTrue(ret)

    def test_delete(self):
        ret = self.run_function('boto_sns.delete', ['my-test-topic'])
        self.assertTrue(ret)

    def test_get_all_topics(self):
        self.run_function('boto_sns.create', ['my-test-topic'])
        self.run_function('boto_sns.create', ['my-second-test-topic'])

        ret = self.run_function('boto_sns.get_all_topics')

        self.assertIn('my-test-topic', ret.keys())
        self.assertIn(self._get_arn('my-test-topic'), ret.values())
        self.assertIn('my-second-test-topic', ret.keys())
        self.assertIn(self._get_arn('my-second-test-topic'), ret.values())

    def _get_arn(self, name):
        return 'arn:aws:sns:us-east-1:{0}:{1}'.format(self.account_id, name)

    @property
    def account_id(self):
        if not hasattr(self, '_account_id'):
            account_id = self.run_function('boto_iam.get_account_id')
            setattr(self, '_account_id', account_id)
        return self._account_id
