# -*- coding: utf-8 -*-
'''
    :codeauthor: :email:`Rupesh Tare <rupesht@saltstack.com>`
'''

# Import Python libs
from __future__ import absolute_import

# Import Salt Testing Libs
from salttesting import TestCase, skipIf
from salttesting.mock import (
    MagicMock,
    patch,
    NO_MOCK,
    NO_MOCK_REASON
)

# Import Salt Libs
from salt.modules import influx

DB_LIST = ['A', 'B', 'C']
USER_LIST = [{'name': 'A'}, {'name': 'B'}]


class MockInfluxDBClient(object):
    def get_list_database(self):
        return DB_LIST

    def create_database(self, name):
        return name

    def delete_database(self, name):
        return name

    def switch_database(self, name):
        return name

    def get_list_users(self):
        return USER_LIST

    def get_list_cluster_admins(self):
        return USER_LIST

    def update_cluster_admin_password(self, name, passwd):
        return name, passwd

    def update_database_user_password(self, name, passwd):
        return name, passwd

    def delete_cluster_admin(self, name):
        return name

    def delete_database_user(self, name):
        return name

    def query(self, query, time_precision, chunked):
        return query, time_precision, chunked


@skipIf(NO_MOCK, NO_MOCK_REASON)
class InfluxTestCase(TestCase):
    '''
    TestCase for the salt.modules.at module
    '''
    def test_db_list(self):
        """
        Test to list all InfluxDB databases
        """
        mock_inf_db_client = MagicMock(return_value=MockInfluxDBClient())
        with patch.object(influx, '_client', mock_inf_db_client):
            self.assertEqual(influx.db_list(user='root',
                                            password='root',
                                            host='localhost',
                                            port=8086), DB_LIST)

    def test_db_exists(self):
        '''
        Tests for checks if a database exists in InfluxDB
        '''
        with patch.object(influx, 'db_list', side_effect=[[{'name': 'A'}],
                                                          None]):
            self.assertTrue(influx.db_exists(name='A',
                                             user='root',
                                             password='root',
                                             host='localhost',
                                             port=8000))

            self.assertFalse(influx.db_exists(name='A',
                                              user='root',
                                              password='root',
                                              host='localhost',
                                              port=8000))

    def test_db_create(self):
        '''
        Test to create a database
        '''
        with patch.object(influx, 'db_exists', side_effect=[True, False]):
            self.assertFalse(influx.db_create(name='A',
                                              user='root',
                                              password='root',
                                              host='localhost',
                                              port=8000))

            mock_inf_db_client = MagicMock(return_value=MockInfluxDBClient())
            with patch.object(influx, '_client', mock_inf_db_client):
                self.assertTrue(influx.db_create(name='A',
                                                 user='root',
                                                 password='root',
                                                 host='localhost',
                                                 port=8000))

    def test_db_remove(self):
        '''
        Test to remove a database
        '''
        with patch.object(influx, 'db_exists', side_effect=[False, True]):
            self.assertFalse(influx.db_remove(name='A',
                                              user='root',
                                              password='root',
                                              host='localhost',
                                              port=8000))

            mock_inf_db_client = MagicMock(return_value=MockInfluxDBClient())
            with patch.object(influx, '_client', mock_inf_db_client):
                self.assertTrue(influx.db_remove(name='A',
                                                 user='root',
                                                 password='root',
                                                 host='localhost',
                                                 port=8000))

    def test_user_list(self):
        '''
        Tests  for list cluster admins or database users.
        '''
        mock_inf_db_client = MagicMock(return_value=MockInfluxDBClient())
        with patch.object(influx, '_client', mock_inf_db_client):
            self.assertListEqual(influx.user_list(database='A',
                                                  user='root',
                                                  password='root',
                                                  host='localhost',
                                                  port=8086), USER_LIST)

            self.assertListEqual(influx.user_list(user='root',
                                                  password='root',
                                                  host='localhost',
                                                  port=8086), USER_LIST)

    def test_user_exists(self):
        '''
        Test to checks if a cluster admin or database user exists.
        '''
        with patch.object(influx, 'user_list', side_effect=[[{'name': 'A'}],
                                                            None]):
            self.assertTrue(influx.user_exists(name='A',
                                               user='root',
                                               password='root',
                                               host='localhost',
                                               port=8000))

            self.assertFalse(influx.user_exists(name='A',
                                                user='root',
                                                password='root',
                                                host='localhost',
                                                port=8000))

    def test_user_chpass(self):
        '''
        Tests to change password for a cluster admin or a database user.
        '''
        with patch.object(influx, 'user_exists', return_value=False):
            self.assertFalse(influx.user_chpass(name='A',
                                                passwd='*',
                                                user='root',
                                                password='root',
                                                host='localhost',
                                                port=8000))

            self.assertFalse(influx.user_chpass(name='A',
                                                passwd='*',
                                                database='test',
                                                user='root',
                                                password='root',
                                                host='localhost',
                                                port=8000))

        mock_inf_db_client = MagicMock(return_value=MockInfluxDBClient())
        with patch.object(influx, '_client', mock_inf_db_client):
            with patch.object(influx, 'user_exists', return_value=True):
                self.assertTrue(influx.user_chpass(name='A',
                                                   passwd='*',
                                                   user='root',
                                                   password='root',
                                                   host='localhost',
                                                   port=8000))

                self.assertTrue(influx.user_chpass(name='A',
                                                   passwd='*',
                                                   database='test',
                                                   user='root',
                                                   password='root',
                                                   host='localhost',
                                                   port=8000))

    def test_user_remove(self):
        '''
        Tests to remove a cluster admin or a database user.
        '''
        with patch.object(influx, 'user_exists', return_value=False):
            self.assertFalse(influx.user_remove(name='A',
                                                user='root',
                                                password='root',
                                                host='localhost',
                                                port=8000))

            self.assertFalse(influx.user_remove(name='A',
                                                database='test',
                                                user='root',
                                                password='root',
                                                host='localhost',
                                                port=8000))

        mock_inf_db_client = MagicMock(return_value=MockInfluxDBClient())
        with patch.object(influx, '_client', mock_inf_db_client):
            with patch.object(influx, 'user_exists', return_value=True):
                self.assertTrue(influx.user_remove(name='A',
                                                   user='root',
                                                   password='root',
                                                   host='localhost',
                                                   port=8000))

                self.assertTrue(influx.user_remove(name='A',
                                                   database='test',
                                                   user='root',
                                                   password='root',
                                                   host='localhost',
                                                   port=8000))

    def test_query(self):
        '''
        Test for querying data
        '''
        mock_inf_db_client = MagicMock(return_value=MockInfluxDBClient())
        with patch.object(influx, '_client', mock_inf_db_client):
            self.assertTrue(influx.query(database='db',
                                         query='q',
                                         user='root',
                                         password='root',
                                         host='localhost',
                                         port=8000))

    def test_retention_policy_get(self):
        client = MockInfluxDBClient()
        policy = {'name': 'foo'}
        with patch.object(influx, '_client', MagicMock(return_value=client)):
            client.get_list_retention_policies = MagicMock(return_value=[policy])
            self.assertEqual(
                policy,
                influx.retention_policy_get(database='db', name='foo')
            )

    def test_retention_policy_add(self):
        client = MockInfluxDBClient()
        with patch.object(influx, '_client', MagicMock(return_value=client)):
            client.create_retention_policy = MagicMock()
            self.assertTrue(influx.retention_policy_add(
                database='db',
                name='name',
                duration='30d',
                replication=1,
            ))
            client.create_retention_policy.assert_called_once_with(
                'name', '30d', 1, 'db', False)

    def test_retention_policy_modify(self):
        client = MockInfluxDBClient()
        with patch.object(influx, '_client', MagicMock(return_value=client)):
            client.alter_retention_policy = MagicMock()
            self.assertTrue(influx.retention_policy_alter(
                database='db',
                name='name',
                duration='30d',
                replication=1,
            ))
            client.alter_retention_policy.assert_called_once_with(
                'name', 'db', '30d', 1, False)

if __name__ == '__main__':
    from integration import run_tests
    run_tests(InfluxTestCase, needs_daemon=False)
