# -*- coding: utf-8 -*-
'''
    :codeauthor: :email:`Jayesh Kariya <jayeshk@saltstack.com>`
'''
# Import Python libs
from __future__ import absolute_import

# Import Salt Testing Libs
from salttesting import skipIf, TestCase
from salttesting.mock import (
    NO_MOCK,
    NO_MOCK_REASON,
    MagicMock,
    patch)

from salttesting.helpers import ensure_in_syspath

ensure_in_syspath('../../')

# Import Salt Libs
from salt.states import boto_sqs

boto_sqs.__salt__ = {}
boto_sqs.__opts__ = {}


@skipIf(NO_MOCK, NO_MOCK_REASON)
class BotoSqsTestCase(TestCase):
    '''
    Test cases for salt.states.boto_sqs
    '''
    # 'present' function tests: 1

    def test_present(self):
        '''
        Test to ensure the SQS queue exists.
        '''
        name = 'mysqs'
        attributes = {'ReceiveMessageWaitTimeSeconds': 20}

        ret = {'name': name,
               'result': False,
               'changes': {},
               'comment': ''}

        mock = MagicMock(side_effect=[False, False, True, True])
        mock_bool = MagicMock(return_value=False)
        mock_attr = MagicMock(return_value={})
        with patch.dict(boto_sqs.__salt__,
                        {'boto_sqs.exists': mock,
                         'boto_sqs.create': mock_bool,
                         'boto_sqs.get_attributes': mock_attr}):
            with patch.dict(boto_sqs.__opts__, {'test': False}):
                comt = ('Failed to create {0} AWS queue'.format(name))
                ret.update({'comment': comt})
                self.assertDictEqual(boto_sqs.present(name), ret)

            with patch.dict(boto_sqs.__opts__, {'test': True}):
                comt = ('AWS SQS queue {0} is set to be created.'.format(name))
                ret.update({'comment': comt, 'result': None})
                self.assertDictEqual(boto_sqs.present(name), ret)

                comt = ('Attribute(s) ReceiveMessageWaitTimeSeconds'
                        ' to be set on mysqs.')
                ret.update({'comment': comt})
                self.assertDictEqual(boto_sqs.present(name, attributes), ret)

            comt = ('mysqs present. Attributes set.')
            ret.update({'comment': comt, 'result': True})
            self.assertDictEqual(boto_sqs.present(name), ret)

    # 'absent' function tests: 1

    def test_absent(self):
        '''
        Test to ensure the named sqs queue is deleted.
        '''
        name = 'test.example.com.'

        ret = {'name': name,
               'result': True,
               'changes': {},
               'comment': ''}

        mock = MagicMock(side_effect=[False, True])
        with patch.dict(boto_sqs.__salt__,
                        {'boto_sqs.exists': mock}):
            comt = ('{0} does not exist in None.'.format(name))
            ret.update({'comment': comt})
            self.assertDictEqual(boto_sqs.absent(name), ret)

            with patch.dict(boto_sqs.__opts__, {'test': True}):
                comt = ('AWS SQS queue {0} is set to be removed.'.format(name))
                ret.update({'comment': comt, 'result': None})
                self.assertDictEqual(boto_sqs.absent(name), ret)


if __name__ == '__main__':
    from integration import run_tests
    run_tests(BotoSqsTestCase, needs_daemon=False)
