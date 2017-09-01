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
from tests.support.mock import NO_MOCK, NO_MOCK_REASON, Mock, patch

# Import Salt Libs
import salt.config
import salt.loader
import salt.states.boto_asg as boto_asg


@skipIf(NO_MOCK, NO_MOCK_REASON)
class BotoAsgTestCase(TestCase, LoaderModuleMockMixin):
    '''
    Test cases for salt.states.boto_asg
    '''
    # 'present' function tests: 1

    def setup_loader_modules(self):
        utils = salt.loader.utils(
            self.opts,
            whitelist=['dictupdate', 'state'],
            context={},
        )
        return {boto_asg: {'__utils__': utils}}

    @classmethod
    def setUpClass(cls):
        cls.opts = salt.config.DEFAULT_MINION_OPTS

        cls.name = 'my_asg'
        cls.base_ret = {'name': cls.name, 'changes': {}}

    @classmethod
    def tearDownClass(cls):
        del cls.opts

        del cls.name
        del cls.base_ret

    def base_ret_with(self, extra_ret):
        new_ret = copy.deepcopy(self.base_ret)
        new_ret.update(extra_ret)
        return new_ret

    maxSize = None

    def test_present(self):
        '''
        Test to ensure the autoscale group exists.
        '''
        name = 'myasg'
        launch_config_name = 'mylc'
        availability_zones = ['us-east-1a', 'us-east-1b']
        min_size = 1
        max_size = 1

        ret = {'name': name,
               'result': None,
               'changes': {},
               'comment': ''}

        mock = Mock(side_effect=[False, {'min_size': 2}, ['']])
        with patch.dict(boto_asg.__salt__, {'boto_asg.get_config': mock}):
            with patch.dict(boto_asg.__opts__, {'test': True}):
                comt = 'Autoscale group set to be created.'
                ret.update({'comment': comt})
                with patch.dict(boto_asg.__salt__,
                                {'config.option': Mock(return_value={})}):
                    self.assertDictEqual(
                        boto_asg.present(
                            name,
                            launch_config_name,
                            availability_zones,
                            min_size,
                            max_size
                        ),
                        ret
                    )

                def magic_side_effect(value):
                    if isinstance(value, int):
                        if value == 1:
                            return 4
                        return value
                    return ''

                comt = 'Autoscale group set to be updated.'
                ret.update({'comment': comt, 'result': None})
                ret.update({'changes': {'new': {'min_size': 4},
                                        'old': {'min_size': 2}}})
                utils_ordered_mock = Mock(
                    side_effect=magic_side_effect
                )
                with patch.dict(boto_asg.__salt__,
                                {'config.option': Mock(return_value={})}):
                    with patch.dict(boto_asg.__utils__,
                                    {'boto3.ordered': utils_ordered_mock}):
                        call_ret = boto_asg.present(
                            name,
                            launch_config_name,
                            availability_zones,
                            min_size,
                            max_size
                        )
                        self.assertDictEqual(call_ret, ret)

                with patch.dict(boto_asg.__salt__,
                                {'config.option': Mock(return_value={})}):
                    with patch.dict(boto_asg.__utils__,
                                    {'boto3.ordered': Mock(return_value='')}):
                        comt = 'Autoscale group present. '
                        ret.update({'comment': comt, 'result': True})
                        ret.update({'changes': {}})
                        self.assertDictEqual(
                            boto_asg.present(
                                name,
                                launch_config_name,
                                availability_zones,
                                min_size,
                                max_size
                            ),
                            ret
                        )

    def test_absent_alone(self):
        '''
        Test to ensure the named autoscale group is deleted,
        without examining subresources.
        '''
        with patch.multiple(boto_asg,
            __salt__={'boto_asg.get_config': Mock(return_value=False)},
            __opts__={'test': True},
        ):
            comment = [
                'Autoscale group {0} does not exist.'.format(self.name),
            ]
            self.assertDictEqual(
                boto_asg.absent(self.name),
                self.base_ret_with({'result': True, 'comment': comment}),
            )

        with patch.multiple(boto_asg,
            __salt__={'boto_asg.get_config': Mock(return_value=True)},
            __opts__={'test': True},
        ):
            comment = [
                'Autoscale group {0} set to be deleted.'.format(self.name),
            ]
            self.assertDictEqual(
                boto_asg.absent(self.name),
                self.base_ret_with({
                    'result': None,
                    'comment': comment,
                    'pchanges': {'asg': {'old': self.name, 'new': None}},
                }),
            )

        with patch.multiple(boto_asg,
            __salt__={
                'boto_asg.get_config': Mock(return_value=True),
                'boto_asg.delete': Mock(return_value=False),
            },
            __opts__={'test': False},
        ):
            comment = [
                'Failed to delete autoscale group {0}.'.format(self.name),
            ]
            self.assertDictEqual(
                boto_asg.absent(self.name),
                self.base_ret_with({'result': False, 'comment': comment}),
            )

        with patch.multiple(boto_asg,
            __salt__={
                'boto_asg.get_config': Mock(return_value=True),
                'boto_asg.delete': Mock(return_value=True),
            },
            __opts__={'test': False},
        ):
            comment = [
                'Deleted autoscale group {0}.'.format(self.name),
            ]
            self.assertDictEqual(
                boto_asg.absent(self.name),
                self.base_ret_with({
                    'result': True,
                    'comment': comment,
                    'changes': {'asg': {'old': self.name, 'new': None}},
                }),
            )

    def test_absent_with_subresources(self):
        '''
        Test to ensure the named autoscale group is deleted with subresources.
        '''
        mock_asg_get = Mock(return_value={'launch_config_name': 'my_lc'})
        mock_lc_absent_test = Mock(return_value={
            'name': 'my_lc',
            'result': None,
            'comment': 'Launch configuration set to be deleted.',
            'changes': {},
            'pchanges': {'old': 'my_lc', 'new': None},
        })
        with patch.multiple(boto_asg,
            __salt__={
                'boto_asg.get_config': mock_asg_get,
                'config.option': Mock(return_value={}),
            },
            __states__={'boto_lc.absent': mock_lc_absent_test},
            __opts__={'test': True},
        ):
            comment = [
                'Autoscale group {0} set to be deleted.'.format(self.name),
                'Launch configuration set to be deleted.',
            ]
            self.assertDictEqual(
                boto_asg.absent(self.name, recurse=True),
                self.base_ret_with({
                    'result': None,
                    'comment': comment,
                    'pchanges': {
                        'asg': {'old': 'my_asg', 'new': None},
                        'launch_config': {'old': 'my_lc', 'new': None},
                    },
                }),
            )

        mock_lc_absent_real = Mock(return_value={
            'name': 'my_lc',
            'result': True,
            'comment': 'Deleted launch configuration.',
            'changes': {'old': 'my_lc', 'new': None},
        })
        mock_alarms_absent_real = Mock(return_value={
            'name': '',
            'result': True,
            'comment': 'Deleted CloudWatch alarms alarm-1,alarm-2.',
            'changes': {'old': ['alarm-1', 'alarm-2'], 'new': []},
        })
        with patch.multiple(boto_asg,
            __salt__={
                'boto_asg.get_config': mock_asg_get,
                'boto_asg.delete': Mock(return_value=True),
                'config.option': Mock(return_value={}),
            },
            __states__={
                'boto_lc.absent': mock_lc_absent_real,
                'boto_cloudwatch_alarm.absent': mock_alarms_absent_real,
            },
            __opts__={'test': False},
        ):
            comment = [
                'Deleted autoscale group {0}.'.format(self.name),
                'Deleted launch configuration.',
                'Deleted CloudWatch alarms alarm-1,alarm-2.',
            ]
            self.assertDictEqual(
                boto_asg.absent(
                    self.name,
                    alarms=dict(
                        (name, {'name': name})
                        for name in ['alarm-1', 'alarm-2']
                    ),
                    recurse=True,
                ),
                self.base_ret_with({
                    'result': True,
                    'comment': comment,
                    'changes': {
                        'asg': {'old': 'my_asg', 'new': None},
                        'launch_config': {'old': 'my_lc', 'new': None},
                        'alarms': {'old': ['alarm-1', 'alarm-2'], 'new': []},
                    },
                }),
            )
