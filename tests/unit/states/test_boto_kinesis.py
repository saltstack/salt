# -*- coding: utf-8 -*-
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
import salt.states.boto_kinesis as boto_kinesis


@skipIf(NO_MOCK, NO_MOCK_REASON)
class BotoKinesisTestCase(TestCase, LoaderModuleMockMixin):
    '''
    Test cases for salt.states.boto_kinesis
    '''
    # 'present' function tests: 1

    maxDiff = None

    def setup_loader_modules(self):
        return {boto_kinesis: {}}

    def test_stream_present(self):
        '''
        Test to ensure the kinesis stream exists.
        '''
        name = 'new_stream'
        retention_hours = 24
        enhanced_monitoring = ['IteratorAgeMilliseconds']
        different_enhanced_monitoring = ['IncomingBytes']
        num_shards = 1

        ret = {'name': name,
               'result': True,
               'changes': {},
               'comment': ''}

        shards = [{'ShardId': 'shardId-000000000000',
                   'HashKeyRange': {'EndingHashKey': 'big number', 'StartingHashKey': '0'},
                   'SequenceNumberRange': {'StartingSequenceNumber': 'bigger number'}}]
        stream_description = {'HasMoreShards': False,
                              'RetentionPeriodHours': retention_hours,
                              'StreamName': name,
                              'Shards': shards,
                              'StreamARN': "",
                              'EnhancedMonitoring': [{'ShardLevelMetrics': enhanced_monitoring}],
                              'StreamStatus': 'ACTIVE'}

        exists_mock = MagicMock(side_effect=[{'result': True}, {'result': False}, {'result': True}, {'result': False}])
        get_stream_mock = MagicMock(return_value={'result': {'StreamDescription': stream_description}})
        shard_mock = MagicMock(return_value=[0, 0, {'OpenShards': shards}])
        dict_mock = MagicMock(return_value={'result': True})
        mock_bool = MagicMock(return_value=True)
        with patch.dict(boto_kinesis.__salt__,
                        {'boto_kinesis.exists': exists_mock,
                         'boto_kinesis.create_stream': dict_mock,
                         'boto_kinesis.get_stream_when_active': get_stream_mock,
                         'boto_kinesis.get_info_for_reshard': shard_mock,
                         'boto_kinesis.num_shards_matches': mock_bool}):
            # already present, no change required
            comt = ('Kinesis stream {0} already exists,\n'
                    'Kinesis stream {0}: retention hours did not require change, already set at {1},\n'
                    'Kinesis stream {0}: enhanced monitoring did not require change, already set at {2},\n'
                    'Kinesis stream {0}: did not require resharding, remains at {3} shards'
                    .format(name, retention_hours, enhanced_monitoring, num_shards))
            ret.update({'comment': comt})
            self.assertDictEqual(boto_kinesis.present(name, retention_hours, enhanced_monitoring, num_shards), ret)

            with patch.dict(boto_kinesis.__opts__, {'test': True}):
                # not present, test environment (dry run)
                comt = ('Kinesis stream {0} would be created'
                        .format(name))
                ret.update({'comment': comt, 'result': None})
                self.assertDictEqual(boto_kinesis.present(name, retention_hours, enhanced_monitoring, num_shards), ret)

                # already present, changes required, test environment (dry run)
                comt = ('Kinesis stream {0} already exists,\n'
                        'Kinesis stream {0}: retention hours would be updated to {1},\n'
                        'Kinesis stream {0}: would enable enhanced monitoring for {2},\n'
                        'Kinesis stream {0}: would disable enhanced monitoring for {3},\n'
                        'Kinesis stream {0}: would be resharded from {4} to {5} shards'
                        .format(name, retention_hours+1, different_enhanced_monitoring,
                                enhanced_monitoring, num_shards, num_shards+1))
                ret.update({'comment': comt, 'result': None})
                self.assertDictEqual(boto_kinesis.present(name, retention_hours+1, different_enhanced_monitoring,
                                                          num_shards+1), ret)

            # not present, create and configure
            changes = {'new': {'name': name,
                               'num_shards': num_shards}}

            with patch.dict(boto_kinesis.__opts__, {'test': False}):
                comt = ('Kinesis stream {0} successfully created,\n'
                        'Kinesis stream {0}: retention hours did not require change, already set at {1},\n'
                        'Kinesis stream {0}: enhanced monitoring did not require change, already set at {2},\n'
                        'Kinesis stream {0}: did not require resharding, remains at {3} shards'
                        .format(name, retention_hours, enhanced_monitoring, num_shards))
                ret.update({'comment': comt, 'result': True,
                            'changes': changes})
                self.assertDictEqual(ret, boto_kinesis.present(name, retention_hours, enhanced_monitoring, num_shards))

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
