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

        mock = MagicMock(side_effect=[False, True])
        with patch.dict(boto_sns.__salt__,
                        {'boto_sns.exists': mock}):
            comt = ('AWS SNS topic {0} does not exist.'.format(name))
            ret.update({'comment': comt})
            self.assertDictEqual(boto_sns.absent(name), ret)

            with patch.dict(boto_sns.__opts__, {'test': True}):
                comt = ('AWS SNS topic {0} is set to be removed.'.format(name))
                ret.update({'comment': comt, 'result': None})
                self.assertDictEqual(boto_sns.absent(name), ret)


if __name__ == '__main__':
    from integration import run_tests
    run_tests(BotoSnsTestCase, needs_daemon=False)
