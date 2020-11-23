# -*- coding: utf-8 -*-
'''
Unit tests for salt.utils.aws
'''

# Import python libs
from __future__ import absolute_import, print_function, unicode_literals

import salt.utils.aws

# Import Salt Testing libs
from tests.support.unit import TestCase


class AWSMaxRetriesCase(TestCase):
    def test_max_retries(self):
        # TODO:
        # - patch away sig2 (it fails if calling salt.utils.aws.query with default parameters)
        # - mock requests.get (line 499) returning an error repeatedly
        # - run until the AWS_MAX_RETRIES handler
        salt.utils.aws.query()
