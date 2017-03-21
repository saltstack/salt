# -*- coding: utf-8 -*-
'''
    :codeauthor: :email:`Logilab <contact@logilab.fr>`
'''
# Import Python libs
from __future__ import absolute_import

# Import Salt Testing Libs
from tests.support.unit import skipIf, TestCase
from tests.support.mock import (
    NO_MOCK,
    NO_MOCK_REASON,
    MagicMock,
    patch
)

# Import Salt Libs
import salt.states.postgres_cluster as postgres_cluster

postgres_cluster.__opts__ = {}
postgres_cluster.__salt__ = {}


@skipIf(NO_MOCK, NO_MOCK_REASON)
class PostgresClusterTestCase(TestCase):
    '''
    Test cases for salt.states.postgres_cluster
    '''
    # 'present' function tests: 1

    def test_present(self):
        '''
        Test to ensure that the named database is present
        with the specified properties.
        '''
        name = 'main'
        version = '9.4'

        ret = {'name': name,
               'changes': {},
               'result': False,
               'comment': ''}

        mock_t = MagicMock(return_value=True)
        mock_f = MagicMock(return_value=False)
        infos = {'{0}/{1}'.format(version, name): {}}
        mock = MagicMock(return_value=infos)
        with patch.dict(postgres_cluster.__salt__,
                        {'postgres.cluster_list': mock,
                         'postgres.cluster_exists': mock_t,
                         'postgres.cluster_create': mock_t,
                        }):
            comt = ('Cluster {0}/{1} is already present'.format(version, name))
            ret.update({'comment': comt, 'result': True})
            self.assertDictEqual(postgres_cluster.present(version, name), ret)
            infos['{0}/{1}'.format(version, name)]['port'] = 5433
            comt = ('Cluster {0}/{1} has wrong parameters '
                    'which couldn\'t be changed on fly.'.format(version, name))
            ret.update({'comment': comt, 'result': False})
            self.assertDictEqual(postgres_cluster.present(version, name, port=5434), ret)
            infos['{0}/{1}'.format(version, name)]['datadir'] = '/tmp/'
            comt = ('Cluster {0}/{1} has wrong parameters '
                    'which couldn\'t be changed on fly.'.format(version, name))
            ret.update({'comment': comt, 'result': False})
            self.assertDictEqual(postgres_cluster.present(version, name, port=5434), ret)

        with patch.dict(postgres_cluster.__salt__,
                        {'postgres.cluster_list': mock,
                         'postgres.cluster_exists': mock_f,
                         'postgres.cluster_create': mock_t,
                        }):
            comt = 'The cluster {0}/{1} has been created'.format(version, name)
            ret.update({'comment': comt, 'result': True,
                        'changes': {'{0}/{1}'.format(version, name): 'Present'}
                        })
            self.assertDictEqual(postgres_cluster.present(version, name),
                                 ret)
            with patch.dict(postgres_cluster.__opts__, {'test': True}):
                comt = 'Cluster {0}/{1} is set to be created'.format(version, name)
                ret.update({'comment': comt, 'result': None, 'changes': {}})
                self.assertDictEqual(postgres_cluster.present(version, name),
                                     ret)

        with patch.dict(postgres_cluster.__salt__,
                        {'postgres.cluster_list': mock,
                         'postgres.cluster_exists': mock_f,
                         'postgres.cluster_create': mock_f,
                        }):
            comt = 'Failed to create cluster {0}/{1}'.format(version, name)
            ret.update({'comment': comt, 'result': False})
            self.assertDictEqual(postgres_cluster.present(version, name),
                                 ret)

    # 'absent' function tests: 1

    def test_absent(self):
        '''
        Test to ensure that the named database is absent.
        '''
        name = 'main'
        version = '9.4'

        ret = {'name': name,
               'changes': {},
               'result': False,
               'comment': ''}

        mock_t = MagicMock(return_value=True)
        mock = MagicMock(side_effect=[True, True, False])
        with patch.dict(postgres_cluster.__salt__,
                        {'postgres.cluster_exists': mock,
                         'postgres.cluster_remove': mock_t}):
            with patch.dict(postgres_cluster.__opts__, {'test': True}):
                comt = ('Cluster {0}/{1} is set to be removed'.format(version, name))
                ret.update({'comment': comt, 'result': None})
                self.assertDictEqual(postgres_cluster.absent(version, name), ret)

            with patch.dict(postgres_cluster.__opts__, {'test': False}):
                comt = ('Cluster {0}/{1} has been removed'.format(version, name))
                ret.update({'comment': comt, 'result': True,
                            'changes': {name: 'Absent'}})
                self.assertDictEqual(postgres_cluster.absent(version, name), ret)

                comt = ('Cluster {0}/{1} is not present, so it cannot be removed'
                        .format(version, name))
                ret.update({'comment': comt, 'result': True, 'changes': {}})
                self.assertDictEqual(postgres_cluster.absent(version, name), ret)
