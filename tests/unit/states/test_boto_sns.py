# -*- coding: utf-8 -*-
'''
    :codeauthor: :email:`Jayesh Kariya <jayeshk@saltstack.com>`
'''
# Import Python libs
from __future__ import absolute_import

# Import Salt Testing Libs
from tests.support.unit import skipIf, TestCase
from tests.support.mock import (
    NO_MOCK,
    NO_MOCK_REASON,
    MagicMock,
    patch)

# Import Salt Libs
from salt.states import boto_sns

boto_sns.__salt__ = {}
boto_sns.__opts__ = {}


@skipIf(NO_MOCK, NO_MOCK_REASON)
class BotoSnsTestCase(TestCase):
    '''
    Test cases for salt.states.boto_sns
    '''
    # 'present' function tests: 1

    def test_present(self):
        '''
        Test to ensure the SNS topic exists.
        '''
        name = 'test.example.com.'

        ret = {'name': name,
               'result': True,
               'changes': {},
               'comment': ''}

        mock = MagicMock(side_effect=[True, False, False])
        mock_bool = MagicMock(return_value=False)
        with patch.dict(boto_sns.__salt__,
                        {'boto_sns.exists': mock,
                         'boto_sns.create': mock_bool}):
            comt = ('AWS SNS topic {0} present.'.format(name))
            ret.update({'comment': comt})
            self.assertDictEqual(boto_sns.present(name), ret)

            with patch.dict(boto_sns.__opts__, {'test': True}):
                comt = ('AWS SNS topic {0} is set to be created.'.format(name))
                ret.update({'comment': comt, 'result': None})
                self.assertDictEqual(boto_sns.present(name), ret)

            with patch.dict(boto_sns.__opts__, {'test': False}):
                comt = ('Failed to create {0} AWS SNS topic'.format(name))
                ret.update({'comment': comt, 'result': False})
                self.assertDictEqual(boto_sns.present(name), ret)

    # 'absent' function tests: 1

    def test_absent(self):
        '''
        Test to ensure the named sns topic is deleted.
        '''
        name = 'test.example.com.'

        ret = {'name': name,
               'result': True,
               'changes': {},
               'comment': ''}

        self.maxDiff = None

        exists_mock = MagicMock(side_effect=[False, True, True, True, True, True, True])
        with patch.dict(boto_sns.__salt__,
                        {'boto_sns.exists': exists_mock}):
            # tests topic already absent
            comt = ('AWS SNS topic {0} does not exist.'.format(name))
            ret.update({'comment': comt})
            self.assertDictEqual(boto_sns.absent(name), ret)

            with patch.dict(boto_sns.__opts__, {'test': True}):
                # tests topic present, test option, unsubscribe is False
                comt = ('AWS SNS topic {0} is set to be removed.  '
                        '0 subscription(s) will be removed.'.format(name))
                ret.update({'comment': comt, 'result': None})
                self.assertDictEqual(boto_sns.absent(name), ret)

            subscriptions = [dict(
                Endpoint='arn:aws:lambda:us-west-2:123456789:function:test',
                Owner=123456789,
                Protocol='Lambda',
                TopicArn='arn:aws:sns:us-west-2:123456789:test',
                SubscriptionArn='arn:aws:sns:us-west-2:123456789:test:some_uuid'
            )]
            with patch.dict(boto_sns.__opts__, {'test': True}):
                subs_mock = MagicMock(return_value=subscriptions)
                with patch.dict(boto_sns.__salt__,
                                {'boto_sns.get_all_subscriptions_by_topic': subs_mock}):
                    # tests topic present, 1 subscription, test option, unsubscribe is True
                    comt = ('AWS SNS topic {0} is set to be removed.  '
                            '1 subscription(s) will be removed.'.format(name))
                    ret.update({'comment': comt, 'result': None})
                    self.assertDictEqual(boto_sns.absent(name, unsubscribe=True), ret)

            subs_mock = MagicMock(return_value=subscriptions)
            unsubscribe_mock = MagicMock(side_effect=[True, False])
            with patch.dict(boto_sns.__salt__,
                            {'boto_sns.unsubscribe': unsubscribe_mock}):
                with patch.dict(boto_sns.__salt__,
                                {'boto_sns.get_all_subscriptions_by_topic': subs_mock}):
                    delete_mock = MagicMock(side_effect=[True, True, True, False])
                    with patch.dict(boto_sns.__salt__,
                                    {'boto_sns.delete': delete_mock}):
                        # tests topic present, unsubscribe flag True, unsubscribe succeeded,
                        # delete succeeded
                        comt = ('AWS SNS topic {0} deleted.'.format(name))
                        ret.update({'changes': {'new': None,
                                                'old': {'topic': name,
                                                        'subscriptions': subscriptions}},
                                    'result': True,
                                    'comment': comt})
                        self.assertDictEqual(boto_sns.absent(name, unsubscribe=True), ret)

                        # tests topic present, unsubscribe flag True, unsubscribe fails,
                        # delete succeeded
                        ret.update({'changes': {'new': {'subscriptions': subscriptions},
                                                'old': {'topic': name,
                                                        'subscriptions': subscriptions}},
                                    'result': True,
                                    'comment': comt})
                        self.assertDictEqual(boto_sns.absent(name, unsubscribe=True), ret)

                        # tests topic present, unsubscribe flag False, delete succeeded
                        ret.update({'changes': {'new': None,
                                                'old': {'topic': name}},
                                    'result': True,
                                    'comment': comt})
                        self.assertDictEqual(boto_sns.absent(name), ret)

                        # tests topic present, unsubscribe flag False, delete failed
                        comt = 'Failed to delete {0} AWS SNS topic.'.format(name)
                        ret.update({'changes': {},
                                    'result': False,
                                    'comment': comt})
                        self.assertDictEqual(boto_sns.absent(name), ret)
