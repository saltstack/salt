# -*- coding: utf-8 -*-
'''
    :codeauthor: :email:`Jayesh Kariya <jayeshk@saltstack.com>`
'''
# Import Python libs
from __future__ import absolute_import
import copy

# Import Salt Testing Libs
from tests.support.mixins import LoaderModuleMockMixin
from tests.support.unit import skipIf, TestCase
from tests.support.mock import (
    NO_MOCK,
    NO_MOCK_REASON,
    Mock,
    patch)

# Import Salt Libs
import salt.states.boto_cloudwatch_alarm as boto_cloudwatch_alarm


@skipIf(NO_MOCK, NO_MOCK_REASON)
class BotoCloudwatchAlarmTestCase(TestCase, LoaderModuleMockMixin):
    '''
    Test cases for salt.states.boto_cloudwatch_alarm
    '''
    def setup_loader_modules(self):
        return {boto_cloudwatch_alarm: {}}

    @classmethod
    def setUpClass(cls):
        cls.name = 'my_test_alarm'
        cls.alarms = ['alarm-1', 'alarm-2', 'alarm-3']
        cls.base_ret = {'name': cls.name, 'changes': {}}

    @classmethod
    def tearDownClass(cls):
        del cls.name
        del cls.alarms
        del cls.base_ret

    def base_ret_with(self, extra_ret):
        new_ret = copy.deepcopy(self.base_ret)
        new_ret.update(extra_ret)
        return new_ret

    def test_present(self):
        '''
        Test to ensure the cloudwatch alarm exists.
        '''
        name = 'my test alarm'
        attributes = {'metric': 'ApproximateNumberOfMessagesVisible',
                      'namespace': 'AWS/SQS'}

        ret = {'name': name,
               'result': None,
               'changes': {},
               'comment': ''}

        mock = Mock(side_effect=[['ok_actions'], [], []])
        mock_bool = Mock(return_value=True)
        with patch.dict(boto_cloudwatch_alarm.__salt__,
                        {'boto_cloudwatch.get_alarm': mock,
                         'boto_cloudwatch.create_or_update_alarm': mock_bool}):
            with patch.dict(boto_cloudwatch_alarm.__opts__, {'test': True}):
                comt = ('alarm my test alarm is to be created/updated.')
                ret.update({'comment': comt})
                self.assertDictEqual(boto_cloudwatch_alarm.present(name,
                                                                   attributes),
                                     ret)

                comt = ('alarm my test alarm is to be created/updated.')
                ret.update({'comment': comt})
                self.assertDictEqual(boto_cloudwatch_alarm.present(name,
                                                                   attributes),
                                     ret)

            with patch.dict(boto_cloudwatch_alarm.__opts__, {'test': False}):
                changes = {'new':
                           {'metric': 'ApproximateNumberOfMessagesVisible',
                            'namespace': 'AWS/SQS'}}
                comt = ('alarm my test alarm is to be created/updated.')
                ret.update({'changes': changes, 'comment': '', 'result': True})
                self.assertDictEqual(boto_cloudwatch_alarm.present(name,
                                                                   attributes),
                                     ret)

    def test_absent_noop(self):
        '''
        Test for boto_cloudwatch_alarm.absent when no changes are needed.
        '''
        mock_get_failure = Mock(return_value={'error': 'get_alarms error'})
        with patch.multiple(boto_cloudwatch_alarm,
            __salt__={'boto_cloudwatch.get_alarms': mock_get_failure},
            __opts__={'test': True},
        ):
            comment = 'Failed to check Cloudwatch alarms: get_alarms error'
            self.assertDictEqual(
                boto_cloudwatch_alarm.absent(self.name),
                self.base_ret_with({'result': False, 'comment': comment}),
            )

        mock_get_empty = Mock(return_value={'result': []})
        with patch.multiple(boto_cloudwatch_alarm,
            __salt__={'boto_cloudwatch.get_alarms': mock_get_empty},
            __opts__={'test': True},
        ):
            comment = 'Cloudwatch alarms are already absent.'
            # Single alarm
            self.assertDictEqual(
                boto_cloudwatch_alarm.absent(self.name),
                self.base_ret_with({'result': True, 'comment': comment})
            )
            # Multiple alarms
            self.assertDictEqual(
                boto_cloudwatch_alarm.absent(self.name, alarms=self.alarms),
                self.base_ret_with({'result': True, 'comment': comment})
            )

    def test_absent_changes(self):
        '''
        Test for boto_cloudwatch_alarm.absent when actually deleting alarms.
        Note that we start with some alarms already missing,
        to ensure that state handles partial deletions properly.
        '''
        # The tests (try to) delete 2 alarms to test name concatenation.
        # Ensure we have enough alarms so that some can be already missing.
        self.assertGreater(
            len(self.alarms),
            2,
            msg='Do not have enough test alarms',
        )

        mock_get_success = Mock(return_value={'result': self.alarms[:2]})
        with patch.multiple(boto_cloudwatch_alarm,
            __salt__={'boto_cloudwatch.get_alarms': mock_get_success},
            __opts__={'test': True},
        ):
            comment = 'Cloudwatch alarms {0} are set to be removed.'
            self.assertDictEqual(
                boto_cloudwatch_alarm.absent(self.name, self.alarms),
                self.base_ret_with({
                    'result': None,
                    'comment': comment.format(','.join(self.alarms[:2])),
                    'pchanges': {'new': [], 'old': self.alarms[:2]},
                }),
            )

        mock_delete_failure = Mock(return_value={'error': 'delete error'})
        with patch.multiple(boto_cloudwatch_alarm,
            __salt__={
                'boto_cloudwatch.get_alarms': mock_get_success,
                'boto_cloudwatch.delete_alarms': mock_delete_failure,
            },
            __opts__={'test': False},
        ):
            comment = 'Failed to delete Cloudwatch alarms: delete error'
            self.assertDictEqual(
                boto_cloudwatch_alarm.absent(self.name),
                self.base_ret_with({
                    'result': False,
                    'comment': comment.format(self.name),
                }),
            )

        mock_delete_success = Mock(return_value={'result': True})
        with patch.multiple(boto_cloudwatch_alarm,
            __salt__={
                'boto_cloudwatch.get_alarms': mock_get_success,
                'boto_cloudwatch.delete_alarms': mock_delete_success,
            },
            __opts__={'test': False},
        ):
            # Uses native list formatting
            comment = 'Deleted Cloudwatch alarms {0}.'
            self.assertDictEqual(
                boto_cloudwatch_alarm.absent(self.name, self.alarms),
                self.base_ret_with({
                    'result': True,
                    'comment': comment.format(','.join(self.alarms[:2])),
                    'changes': {'new': [], 'old': self.alarms[:2]},
                }),
            )
