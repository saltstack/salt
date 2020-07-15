# -*- coding: utf-8 -*-
"""
    :codeauthor: Jayesh Kariya <jayeshk@saltstack.com>
"""
# Import Python libs
from __future__ import absolute_import, print_function, unicode_literals

# Import Salt Libs
import salt.states.aws_sqs as aws_sqs

# Import Salt Testing Libs
from tests.support.mixins import LoaderModuleMockMixin
from tests.support.mock import MagicMock, patch
from tests.support.unit import TestCase


class AwsSqsTestCase(TestCase, LoaderModuleMockMixin):
    """
    Test cases for salt.states.aws_sqs
    """

    def setup_loader_modules(self):
        return {aws_sqs: {}}

    # 'exists' function tests: 1

    def test_exists(self):
        """
        Test to ensure the SQS queue exists.
        """
        name = "myqueue"
        region = "eu-west-1"

        ret = {"name": name, "result": None, "changes": {}, "comment": ""}

        mock = MagicMock(side_effect=[False, True])
        with patch.dict(aws_sqs.__salt__, {"aws_sqs.queue_exists": mock}):
            comt = "AWS SQS queue {0} is set to be created".format(name)
            ret.update({"comment": comt})
            with patch.dict(aws_sqs.__opts__, {"test": True}):
                self.assertDictEqual(aws_sqs.exists(name, region), ret)

            comt = "{0} exists in {1}".format(name, region)
            ret.update({"comment": comt, "result": True})
            self.assertDictEqual(aws_sqs.exists(name, region), ret)

    # 'absent' function tests: 1

    def test_absent(self):
        """
        Test to remove the named SQS queue if it exists.
        """
        name = "myqueue"
        region = "eu-west-1"

        ret = {"name": name, "result": None, "changes": {}, "comment": ""}

        mock = MagicMock(side_effect=[True, False])
        with patch.dict(aws_sqs.__salt__, {"aws_sqs.queue_exists": mock}):
            comt = "AWS SQS queue {0} is set to be removed".format(name)
            ret.update({"comment": comt})
            with patch.dict(aws_sqs.__opts__, {"test": True}):
                self.assertDictEqual(aws_sqs.absent(name, region), ret)

            comt = "{0} does not exist in {1}".format(name, region)
            ret.update({"comment": comt, "result": True})
            self.assertDictEqual(aws_sqs.absent(name, region), ret)
