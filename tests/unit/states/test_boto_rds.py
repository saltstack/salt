# -*- coding: utf-8 -*-
'''
Unit tests for the boto_rds state module.
'''
# Import Python libs
from __future__ import absolute_import, print_function, unicode_literals

# Import Salt Testing Libs
from tests.support.mixins import LoaderModuleMockMixin
from tests.support.unit import TestCase, skipIf
from tests.support.mock import (
    patch,
    MagicMock,
    NO_MOCK,
    NO_MOCK_REASON
)

# pylint: disable=import-error,no-name-in-module
import salt.states.boto_rds as boto_rds


@skipIf(NO_MOCK, NO_MOCK_REASON)
class BotoRdsTestCase(TestCase, LoaderModuleMockMixin):
    '''
    Test cases for salt.states.boto_ec2
    '''
    @classmethod
    def setUpClass(cls):
        cls.name = 'my-db-cluster'
        cls.engine = 'MySQL'
        cls.master_username = 'sqlusr'
        cls.master_user_password = 'sqlpassw'

    @classmethod
    def tearDownClass(cls):
        del cls.name
        del cls.engine
        del cls.master_username
        del cls.master_user_password

    def setup_loader_modules(self):
        return {boto_rds: {}}

    def test_db_cluster_present_when_db_cluster_exists_returns_error(self):
        '''
        Tests the return of db_cluster_present when boto_rds.db_cluster_exists
        returns an error
        '''
        mock_exists = MagicMock(return_value={
            'error': 'db_cluster_exists_error',
        })
        with patch.dict(boto_rds.__salt__, {
            'boto_rds.db_cluster_exists': mock_exists,
        }):
            comment = 'Error when attempting to find db cluster: ' \
                      'db_cluster_exists_error.'
            self.assertDictEqual(
                boto_rds.db_cluster_present(
                    self.name,
                    self.engine,
                    self.master_username,
                    self.master_user_password,
                ),
                {
                    'name': self.name,
                    'result': False,
                    'comment': comment,
                    'changes': {},
                },
            )

    def test_db_cluster_present_when_cluster_already_present(self):
        '''
        Tests the return of db_cluster_present when boto_rds.db_cluster_exists
        indicates that the cluster is present
        '''
        mock_exists = MagicMock(return_value={'exists': True})
        with patch.dict(boto_rds.__salt__, {
            'boto_rds.db_cluster_exists': mock_exists,
        }):
            comment = 'DB cluster {0} present.'.format(self.name)
            self.assertDictEqual(
                boto_rds.db_cluster_present(
                    self.name,
                    self.engine,
                    self.master_username,
                    self.master_user_password,
                ),
                {
                    'name': self.name,
                    'result': True,
                    'comment': comment,
                    'changes': {},
                },
            )

    def test_db_cluster_present_in_test_mode(self):
        '''
        Tests the return of db_cluster_present in test mode
        '''
        mock_exists = MagicMock(return_value={'exists': False})
        with patch.multiple(boto_rds,
            __salt__={'boto_rds.db_cluster_exists': mock_exists},
            __opts__={'test': True},
        ):
            comment = 'DB cluster {0} is set to be created.'.format(self.name)
            self.assertDictEqual(
                boto_rds.db_cluster_present(
                    self.name,
                    self.engine,
                    self.master_username,
                    self.master_user_password,
                ),
                {
                    'name': self.name,
                    'result': None,
                    'comment': comment,
                    'changes': {},
                },
            )

    def test_db_cluster_present_when_db_cluster_is_not_created(self):
        '''
        Tests the return of db_cluster_present when create_db_cluster fails
        '''
        mock_exists = MagicMock(return_value={'exists': False})
        mock_create = MagicMock(return_value={'created': False})
        with patch.multiple(boto_rds, __salt__={
                'boto_rds.db_cluster_exists': mock_exists,
                'boto_rds.create_db_cluster': mock_create,
            },
            __opts__={'test': False},
        ):
            comment = 'Failed to create {0} db cluster.'.format(self.name)
            self.assertDictEqual(
                boto_rds.db_cluster_present(
                    self.name,
                    self.engine,
                    self.master_username,
                    self.master_user_password,
                ),
                {
                    'name': self.name,
                    'result': False,
                    'comment': comment,
                    'changes': {},
                },
            )

    def test_db_cluster_present_when_db_cluster_is_created(self):
        '''
        Tests the return of db_cluster_present when create_db_cluster
        creates the cluster successfully
        '''
        mock_exists = MagicMock(return_value={'exists': False})
        mock_create = MagicMock(return_value={'created': True})
        with patch.multiple(boto_rds, __salt__={
                'boto_rds.db_cluster_exists': mock_exists,
                'boto_rds.create_db_cluster': mock_create,
            },
            __opts__={'test': False},
        ):
            comment = 'DB cluster {0} created.'.format(self.name)
            self.assertDictEqual(
                boto_rds.db_cluster_present(
                    self.name,
                    self.engine,
                    self.master_username,
                    self.master_user_password,
                ),
                {
                    'name': self.name,
                    'result': True,
                    'comment': comment,
                    'changes': {'New DB Cluster': self.name},
                },
            )
