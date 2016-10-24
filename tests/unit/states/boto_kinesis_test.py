# -*- coding: utf-8 -*-
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
from salt.states import boto_kinesis

boto_kinesis.__salt__ = {}
boto_kinesis.__opts__ = {}


@skipIf(NO_MOCK, NO_MOCK_REASON)
class BotoKinesisTestCase(TestCase):
    '''
    Test cases for salt.states.boto_kinesis
    '''
    # # 'present' function tests: 1
    #
    # def test_stream_present(self):
    #     '''
    #     Test to ensure the kinesis stream exists.
    #     '''
    #     name = 'new_stream'
    #
    #     ret = {'name': name,
    #            'result': True,
    #            'changes': {},
    #            'comment': ''}
    #
    #     exists_mock = MagicMock(side_effect=[True, False, False])
    #     dict_mock = MagicMock(return_value={})
    #     mock_bool = MagicMock(return_value=True)
    #     pillar_mock = MagicMock(return_value=[])
    #     with patch.dict(boto_kinesis.__salt__,
    #                     {'boto_kinesis.exists': exists_mock,
    #                      'boto_kinesis.get_stream_when_active': dict_mock,
    #                      'config.option': dict_mock,
    #                      'pillar.get': pillar_mock,
    #                      'boto_kinesis.create_stream': mock_bool}):
    #         comt = ('Kinesis stream {0} already exists\n'
    #                 'Kinesis stream {0}: retention hours did not require change, already set at {1}\n'
    #                 'Kinesis stream {0}: enhanced monitoring did not require change, already set at {2}\n'
    #                 'Kinesis stream {0}: did not reshard, remains at {3} shards\n'
    #                 .format(name))
    #         ret.update({'comment': comt})
    #         self.assertDictEqual(boto_kinesis.present(name), ret)
    #
    #         with patch.dict(boto_kinesis.__opts__, {'test': True}):
    #             comt = ('Kinesis stream {0} would be be created\n'
    #                     'Kinesis stream {0}: retention hours did not require change, already set at {1}\n'
    #                     'Kinesis stream {0}: enhanced monitoring did not require change, already set at {2}\n'
    #                     'Kinesis stream {0}: did not reshard, remains at {3} shards\n'
    #                     .format(name))
    #             ret.update({'comment': comt, 'result': None})
    #             self.assertDictEqual(boto_kinesis.present(name), ret)
    #
    #         changes = {'new': {'global_indexes': None,
    #                            'hash_key': None,
    #                            'hash_key_data_type': None,
    #                            'local_indexes': None,
    #                            'range_key': None,
    #                            'range_key_data_type': None,
    #                            'read_capacity_units': None,
    #                            'table': 'new_table',
    #                            'write_capacity_units': None}}
    #
    #         with patch.dict(boto_kinesis.__opts__, {'test': False}):
    #             comt = ('DynamoDB table {0} was successfully created,\n'
    #                     'DynamoDB table new_table throughput matches,\n'
    #                     .format(name))
    #             ret.update({'comment': comt, 'result': True,
    #                         'changes': changes})
    #             self.assertDictEqual(ret, boto_kinesis.present(name))

    # 'absent' function tests: 1

    def test_absent(self):
        '''
        Test to ensure the Kinesis stream does not exist.
        '''
        name = 'new_stream'

        ret = {'name': name,
               'result': True,
               'changes': {},
               'comment': ''}

        mock = MagicMock(side_effect=[{'result': False}, {'result': True}, {'result': True}])
        mock_bool = MagicMock(return_value={'result': True})
        with patch.dict(boto_kinesis.__salt__,
                        {'boto_kinesis.exists': mock,
                         'boto_kinesis.delete_stream': mock_bool}):
            comt = ('Kinesis stream {0} does not exist'.format(name))
            ret.update({'comment': comt})
            self.assertDictEqual(boto_kinesis.absent(name), ret)

            with patch.dict(boto_kinesis.__opts__, {'test': True}):
                comt = ('Kinesis stream {0} would be deleted'.format(name))
                ret.update({'comment': comt, 'result': None})
                self.assertDictEqual(boto_kinesis.absent(name), ret)

            changes = {'new': 'Stream {0} deleted'.format(name),
                       'old': 'Stream {0} exists'.format(name)}

            with patch.dict(boto_kinesis.__opts__, {'test': False}):
                comt = ('Deleted stream {0}'.format(name))
                ret.update({'comment': comt, 'result': True,
                            'changes': changes})
                self.assertDictEqual(boto_kinesis.absent(name), ret)


if __name__ == '__main__':
    from integration import run_tests
    run_tests(BotoKinesisTestCase, needs_daemon=False)
