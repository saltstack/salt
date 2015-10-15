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
from salt.states import boto_dynamodb

boto_dynamodb.__salt__ = {}
boto_dynamodb.__opts__ = {}


@skipIf(NO_MOCK, NO_MOCK_REASON)
class BotoDynamodbTestCase(TestCase):
    '''
    Test cases for salt.states.boto_dynamodb
    '''
    # 'present' function tests: 1

    def test_present(self):
        '''
        Test to ensure the DynamoDB table exists.
        '''
        name = 'new_table'

        ret = {'name': name,
               'result': True,
               'changes': {},
               'comment': ''}

        mock = MagicMock(side_effect=[True, False, False])
        mock_bool = MagicMock(return_value=True)
        with patch.dict(boto_dynamodb.__salt__,
                        {'boto_dynamodb.exists': mock,
                         'boto_dynamodb.create_table': mock_bool}):
            comt = ('DynamoDB table {0} already exists. \
                         Nothing to change.'.format(name))
            ret.update({'comment': comt})
            self.assertDictEqual(boto_dynamodb.present(name), ret)

            with patch.dict(boto_dynamodb.__opts__, {'test': True}):
                comt = ('DynamoDB table {0} is set to be created \
                        '.format(name))
                ret.update({'comment': comt, 'result': None})
                self.assertDictEqual(boto_dynamodb.present(name), ret)

            changes = {'new': {'global_indexes': None,
                               'hash_key': (None,),
                               'hash_key_data_type': None,
                               'local_indexes': (None,),
                               'range_key': (None,),
                               'range_key_data_type': (None,),
                               'read_capacity_units': (None,),
                               'table': 'new_table',
                               'write_capacity_units': (None,)},
                       'old': None}

            with patch.dict(boto_dynamodb.__opts__, {'test': False}):
                comt = ('DynamoDB table {0} created successfully \
                             '.format(name))
                ret.update({'comment': comt, 'result': True,
                            'changes': changes})
                self.assertDictEqual(boto_dynamodb.present(name), ret)

    # 'absent' function tests: 1

    def test_absent(self):
        '''
        Test to ensure the DynamoDB table does not exist.
        '''
        name = 'new_table'

        ret = {'name': name,
               'result': True,
               'changes': {},
               'comment': ''}

        mock = MagicMock(side_effect=[False, True, True])
        mock_bool = MagicMock(return_value=True)
        with patch.dict(boto_dynamodb.__salt__,
                        {'boto_dynamodb.exists': mock,
                         'boto_dynamodb.delete': mock_bool}):
            comt = ('DynamoDB table {0} does not exist'.format(name))
            ret.update({'comment': comt})
            self.assertDictEqual(boto_dynamodb.absent(name), ret)

            with patch.dict(boto_dynamodb.__opts__, {'test': True}):
                comt = ('DynamoDB table {0} is set to be deleted \
                         '.format(name))
                ret.update({'comment': comt, 'result': None})
                self.assertDictEqual(boto_dynamodb.absent(name), ret)

            changes = {'new': 'Table new_table deleted',
                       'old': 'Table new_table exists'}

            with patch.dict(boto_dynamodb.__opts__, {'test': False}):
                comt = ('Deleted DynamoDB table {0}'.format(name))
                ret.update({'comment': comt, 'result': True,
                            'changes': changes})
                self.assertDictEqual(boto_dynamodb.absent(name), ret)


if __name__ == '__main__':
    from integration import run_tests
    run_tests(BotoDynamodbTestCase, needs_daemon=False)
