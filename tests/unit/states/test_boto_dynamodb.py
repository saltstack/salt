# -*- coding: utf-8 -*-
'''
    :codeauthor: :email:`Jayesh Kariya <jayeshk@saltstack.com>`
'''
# Import Python libs
from __future__ import absolute_import, print_function, unicode_literals

# Import Salt Testing Libs
from tests.support.mixins import LoaderModuleMockMixin
from tests.support.unit import skipIf, TestCase
from tests.support.mock import (
    NO_MOCK,
    NO_MOCK_REASON,
    MagicMock,
    patch)

# Import Salt Libs
import salt.states.boto_dynamodb as boto_dynamodb


@skipIf(NO_MOCK, NO_MOCK_REASON)
class BotoDynamodbTestCase(TestCase, LoaderModuleMockMixin):
    '''
    Test cases for salt.states.boto_dynamodb
    '''
    def setup_loader_modules(self):
        return {boto_dynamodb: {}}

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

        exists_mock = MagicMock(side_effect=[True, False, False])
        dict_mock = MagicMock(return_value={})
        mock_bool = MagicMock(return_value=True)
        pillar_mock = MagicMock(return_value=[])
        with patch.dict(boto_dynamodb.__salt__,
                        {'boto_dynamodb.exists': exists_mock,
                         'boto_dynamodb.describe': dict_mock,
                         'config.option': dict_mock,
                         'pillar.get': pillar_mock,
                         'boto_dynamodb.create_table': mock_bool}):
            comt = ('DynamoDB table {0} exists,\n'
                    'DynamoDB table {0} throughput matches,\n'
                    'All global secondary indexes match,\n'.format(name))
            ret.update({'comment': comt})
            self.assertDictEqual(boto_dynamodb.present(name), ret)

            with patch.dict(boto_dynamodb.__opts__, {'test': True}):
                comt = ('DynamoDB table {0} would be created.'.format(name))
                ret.update({'comment': comt, 'result': None})
                self.assertDictEqual(boto_dynamodb.present(name), ret)

            changes = {'new': {'global_indexes': None,
                               'hash_key': None,
                               'hash_key_data_type': None,
                               'local_indexes': None,
                               'range_key': None,
                               'range_key_data_type': None,
                               'read_capacity_units': None,
                               'table': 'new_table',
                               'write_capacity_units': None}}

            with patch.dict(boto_dynamodb.__opts__, {'test': False}):
                comt = ('DynamoDB table {0} was successfully created,\n'
                        'DynamoDB table new_table throughput matches,\n'
                        .format(name))
                ret.update({'comment': comt, 'result': True,
                            'changes': changes})
                self.assertDictEqual(ret, boto_dynamodb.present(name))

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
                comt = 'DynamoDB table {0} is set to be deleted'.format(name)
                ret.update({'comment': comt, 'result': None})
                self.assertDictEqual(boto_dynamodb.absent(name), ret)

            changes = {'new': 'Table new_table deleted',
                       'old': 'Table new_table exists'}

            with patch.dict(boto_dynamodb.__opts__, {'test': False}):
                comt = ('Deleted DynamoDB table {0}'.format(name))
                ret.update({'comment': comt, 'result': True,
                            'changes': changes})
                self.assertDictEqual(boto_dynamodb.absent(name), ret)
