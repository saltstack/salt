# -*- coding: utf-8 -*-
'''
    :codeauthor: :email:`Jayesh Kariya <jayeshk@saltstack.com>`
'''
# Import Python libs
from __future__ import absolute_import

# Import Salt Testing Libs
from tests.support.mixins import LoaderModuleMockMixin
from tests.support.unit import skipIf, TestCase
from tests.support.mock import NO_MOCK, NO_MOCK_REASON, MagicMock, patch

# Import Salt Libs
import salt.states.boto_asg as boto_asg


@skipIf(NO_MOCK, NO_MOCK_REASON)
class BotoAsgTestCase(TestCase, LoaderModuleMockMixin):
    '''
    Test cases for salt.states.boto_asg
    '''
    # 'present' function tests: 1

    def setup_loader_modules(self):
        return {boto_asg: {}}

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

        mock = MagicMock(side_effect=[False, {'min_size': 2}, ['']])
        with patch.dict(boto_asg.__salt__, {'boto_asg.get_config': mock}):
            with patch.dict(boto_asg.__opts__, {'test': True}):
                comt = 'Autoscale group set to be created.'
                ret.update({'comment': comt})
                with patch.dict(boto_asg.__salt__,
                                {'config.option': MagicMock(return_value={})}):
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
                utils_ordered_mock = MagicMock(
                    side_effect=magic_side_effect
                )
                with patch.dict(boto_asg.__salt__,
                                {'config.option': MagicMock(return_value={})}):
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
                                {'config.option': MagicMock(return_value={})}):
                    with patch.dict(boto_asg.__utils__,
                                    {'boto3.ordered': MagicMock(return_value='')}):
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

    # 'absent' function tests: 1

    def test_absent(self):
        '''
        Test to ensure the named autoscale group is deleted.
        '''
        name = 'myasg'

        ret = {'name': name,
               'result': None,
               'changes': {},
               'comment': ''}

        mock = MagicMock(side_effect=[True, False])
        with patch.dict(boto_asg.__salt__, {'boto_asg.get_config': mock}):
            with patch.dict(boto_asg.__opts__, {'test': True}):
                comt = ('Autoscale group set to be deleted.')
                ret.update({'comment': comt})
                self.assertDictEqual(boto_asg.absent(name), ret)

                comt = ('Autoscale group does not exist.')
                ret.update({'comment': comt, 'result': True})
                self.assertDictEqual(boto_asg.absent(name), ret)
