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
from salt.states import boto_iam_role

boto_iam_role.__salt__ = {}
boto_iam_role.__opts__ = {}


@skipIf(NO_MOCK, NO_MOCK_REASON)
class BotoIAMRoleTestCase(TestCase):
    '''
    Test cases for salt.states.boto_iam_role
    '''
    # 'present' function tests: 1

    def test_present(self):
        '''
        Test to ensure the IAM role exists.
        '''
        name = 'myrole'

        ret = {'name': name,
               'result': False,
               'changes': {},
               'comment': ''}

        _desc_role = {
            'create_date': '2015-02-11T19:47:14Z',
            'role_id': 'HIUHBIUBIBNKJNBKJ',
            'assume_role_policy_document': {
                'Version': '2008-10-17',
                'Statement': [{
                    'Action': 'sts:AssumeRole',
                    'Principal': {'Service': 'ec2.amazonaws.com'},
                    'Effect': 'Allow'
                }]},
            'role_name': 'myfakerole',
            'path': '/',
            'arn': 'arn:aws:iam::12345:role/myfakerole'
        }
        _desc_role2 = {
            'create_date': '2015-02-11T19:47:14Z',
            'role_id': 'HIUHBIUBIBNKJNBKJ',
            'assume_role_policy_document': {
                'Version': '2008-10-17',
                'Statement': [{
                    'Action': 'sts:AssumeRole',
                    'Principal': {
                        'Service': [
                            'ec2.amazonaws.com',
                            'datapipeline.amazonaws.com'
                        ]
                    },
                    'Effect': 'Allow'
                }]},
            'role_name': 'myfakerole',
            'path': '/',
            'arn': 'arn:aws:iam::12345:role/myfakerole'
        }
        mock_desc = MagicMock(side_effect=[
            False, _desc_role, _desc_role, _desc_role2, _desc_role
        ])
        _build_policy = {
            'Version': '2008-10-17',
            'Statement': [{
                'Action': 'sts:AssumeRole',
                'Effect': 'Allow',
                'Principal': {'Service': 'ec2.amazonaws.com'}
            }]
        }
        mock_policy = MagicMock(return_value=_build_policy)
        mock_ipe = MagicMock(side_effect=[False, True, True, True])
        mock_pa = MagicMock(side_effect=[False, True, True, True])
        mock_bool = MagicMock(return_value=False)
        mock_lst = MagicMock(return_value=[])
        with patch.dict(boto_iam_role.__salt__,
                        {'boto_iam.describe_role': mock_desc,
                         'boto_iam.create_role': mock_bool,
                         'boto_iam.build_policy': mock_policy,
                         'boto_iam.update_assume_role_policy': mock_bool,
                         'boto_iam.instance_profile_exists': mock_ipe,
                         'boto_iam.create_instance_profile': mock_bool,
                         'boto_iam.profile_associated': mock_pa,
                         'boto_iam.associate_profile_to_role': mock_bool,
                         'boto_iam.list_role_policies': mock_lst}):
            with patch.dict(boto_iam_role.__opts__, {'test': False}):
                comt = (' Failed to create {0} IAM role.'.format(name))
                ret.update({'comment': comt})
                self.assertDictEqual(boto_iam_role.present(name), ret)

                comt = (' myrole role present. '
                        'Failed to create myrole instance profile.')
                ret.update({'comment': comt})
                self.assertDictEqual(boto_iam_role.present(name), ret)

                comt = (' myrole role present.  Failed to associate myrole'
                        ' instance profile with myrole role.')
                ret.update({'comment': comt})
                self.assertDictEqual(boto_iam_role.present(name), ret)

                comt = (' myrole role present. Failed to update assume role'
                        ' policy.')
                ret.update({'comment': comt})

                self.assertDictEqual(boto_iam_role.present(name), ret)
                comt = (' myrole role present.   ')
                ret.update({'comment': comt, 'result': True})
                self.assertDictEqual(boto_iam_role.present(name), ret)

    # 'absent' function tests: 1

    def test_absent(self):
        '''
        Test to ensure the IAM role is deleted.
        '''
        name = 'myrole'

        ret = {'name': name,
               'result': False,
               'changes': {},
               'comment': ''}

        mock = MagicMock(side_effect=[['mypolicy'], ['mypolicy'], False, True,
                                      False, False, True, False, False, False,
                                      True])
        mock_bool = MagicMock(return_value=False)
        with patch.dict(boto_iam_role.__salt__,
                        {'boto_iam.list_role_policies': mock,
                         'boto_iam.delete_role_policy': mock_bool,
                         'boto_iam.profile_associated': mock,
                         'boto_iam.disassociate_profile_from_role': mock_bool,
                         'boto_iam.instance_profile_exists': mock,
                         'boto_iam.delete_instance_profile': mock_bool,
                         'boto_iam.role_exists': mock,
                         'boto_iam.delete_role': mock_bool}):
            with patch.dict(boto_iam_role.__opts__, {'test': False}):
                comt = (' Failed to add policy mypolicy to role myrole')
                ret.update({'comment': comt,
                            'changes': {'new': {'policies': ['mypolicy']},
                                        'old': {'policies': ['mypolicy']}}})
                self.assertDictEqual(boto_iam_role.absent(name), ret)

                comt = (' No policies in role myrole. Failed to disassociate '
                        'myrole instance profile from myrole role.')
                ret.update({'comment': comt, 'changes': {}})
                self.assertDictEqual(boto_iam_role.absent(name), ret)

                comt = (' No policies in role myrole.  '
                        'Failed to delete myrole instance profile.')
                ret.update({'comment': comt, 'changes': {}})
                self.assertDictEqual(boto_iam_role.absent(name), ret)

                comt = (' No policies in role myrole.  myrole instance profile '
                        'does not exist. Failed to delete myrole iam role.')
                ret.update({'comment': comt, 'changes': {}})
                self.assertDictEqual(boto_iam_role.absent(name), ret)


if __name__ == '__main__':
    from integration import run_tests
    run_tests(BotoIAMRoleTestCase, needs_daemon=False)
