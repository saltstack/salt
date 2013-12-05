# -*- coding: utf-8 -*-

# Import Salt Testing libs
from salttesting import skipIf, TestCase
from salttesting.helpers import ensure_in_syspath
from salttesting.mock import NO_MOCK, NO_MOCK_REASON, Mock, patch

ensure_in_syspath('../../')

# Import salt libs
from salt.modules import postgres

postgres.__grains__ = None  # in order to stub it w/patch below
postgres.__salt__ = None  # in order to stub it w/patch below

test_list_db_csv = 'Name,Owner,Encoding,Collate,Ctype,Access privileges,Tablespace\n\
template1,postgres,LATIN1,en_US,en_US,"{=c/postgres,postgres=CTc/postgres}",pg_default\n\
template0,postgres,LATIN1,en_US,en_US,"{=c/postgres,postgres=CTc/postgres}",pg_default\n\
postgres,postgres,LATIN1,en_US,en_US,,pg_default\n\
test_db,postgres,LATIN1,en_US,en_US,,pg_default'

if NO_MOCK is False:
    SALT_STUB = {
        'config.option': Mock(),
        'cmd.run_all': Mock(),
        'file.chown': Mock(),
        'file.remove': Mock(),
    }
else:
    SALT_STUB = {}


@skipIf(NO_MOCK, NO_MOCK_REASON)
@patch.multiple(postgres,
                __grains__={'os_family': 'Linux'},
                __salt__=SALT_STUB,
)
@patch('salt.utils.which', Mock(return_value='/usr/bin/pgsql'))
class PostgresTestCase(TestCase):
    def test_run_psql(self):
        postgres._run_psql('echo "hi"')
        cmd = SALT_STUB['cmd.run_all']

        self.assertEqual('postgres', cmd.call_args[1]['runas'])

    @patch('salt.modules.postgres._run_psql', Mock(return_value={'retcode': None}))
    def test_db_alter(self):
        postgres.db_alter('dbname',
                          user='testuser',
                          host='testhost',
                          port='testport',
                          maintenance_db='maint_db',
                          password='foo',
                          tablespace='testspace',
                          owner='otheruser',
                          runas='foo'
        )
        postgres._run_psql.assert_called_once_with(
            '/usr/bin/pgsql --no-align --no-readline --username testuser --host testhost --port testport --dbname maint_db -c \'ALTER DATABASE "dbname" OWNER TO "otheruser"\'',
            host='testhost', password='foo', runas='foo')

    @patch('salt.modules.postgres._run_psql', Mock(return_value={'retcode': None}))
    def test_db_create(self):
        postgres.db_create(
            'dbname',
            user='testuser',
            host='testhost',
            port='testport',
            maintenance_db='maint_db',
            password='foo',
            tablespace='testspace',
            owner='otheruser',
            runas='foo'
        )
        postgres._run_psql.assert_called_once_with(
            '/usr/bin/pgsql --no-align --no-readline --username testuser --host testhost --port testport --dbname maint_db -c \'CREATE DATABASE "dbname" WITH TABLESPACE = testspace OWNER = "otheruser"\'',
            host='testhost', password='foo', runas='foo'
        )

    @patch('salt.modules.postgres._run_psql', Mock(return_value={'retcode': None,
                                                                 'stdout': test_list_db_csv}))
    def test_db_exists(self):
        ret = postgres.db_exists(
            'test_db',
            user='testuser',
            host='testhost',
            port='testport',
            maintenance_db='maint_db',
            password='foo',
            runas='foo'
        )
        self.assertTrue(ret)

    @patch('salt.modules.postgres._run_psql', Mock(return_value={'retcode': None,
                                                                 'stdout': test_list_db_csv}))
    def test_db_list(self):
        ret = postgres.db_list(
            user='testuser',
            host='testhost',
            port='testport',
            maintenance_db='maint_db',
            password='foo',
            runas='foo'
        )
        self.assertDictEqual(ret, {
            'test_db': {'Encoding': 'LATIN1', 'Ctype': 'en_US', 'Tablespace': 'pg_default', 'Collate': 'en_US',
                        'Owner': 'postgres', 'Access privileges': ''},
            'template1': {'Encoding': 'LATIN1', 'Ctype': 'en_US', 'Tablespace': 'pg_default', 'Collate': 'en_US',
                          'Owner': 'postgres', 'Access privileges': '{=c/postgres,postgres=CTc/postgres}'},
            'template0': {'Encoding': 'LATIN1', 'Ctype': 'en_US', 'Tablespace': 'pg_default', 'Collate': 'en_US',
                          'Owner': 'postgres', 'Access privileges': '{=c/postgres,postgres=CTc/postgres}'},
            'postgres': {'Encoding': 'LATIN1', 'Ctype': 'en_US', 'Tablespace': 'pg_default', 'Collate': 'en_US',
                         'Owner': 'postgres', 'Access privileges': ''}})

    @patch('salt.modules.postgres._run_psql', Mock(return_value={'retcode': None}))
    def test_db_remove(self):
        postgres.db_remove(
            'test_db',
            user='testuser',
            host='testhost',
            port='testport',
            maintenance_db='maint_db',
            password='foo',
            runas='foo'
        )
        postgres._run_psql.assert_called_once_with(
            "/usr/bin/pgsql --no-align --no-readline --username testuser --host testhost --port testport --dbname maint_db -c 'DROP DATABASE test_db'",
            host='testhost', password='foo', runas='foo')

    @patch('salt.modules.postgres._run_psql', Mock(return_value={'retcode': None}))
    @patch('salt.modules.postgres.user_exists', Mock(return_value=False))
    def test_group_create(self):
        postgres.group_create(
            'testgroup',
            user='testuser',
            host='testhost',
            port='testport',
            maintenance_db='maint_db',
            password='foo',
            createdb=False,
            createuser=False,
            encrypted=False,
            superuser=False,
            replication=False,
            rolepassword='testrolepass',
            groups='testgroup',
            runas='foo'
        )
        postgres._run_psql.assert_called_once_with(
            '/usr/bin/pgsql --no-align --no-readline --username testuser --host testhost --port testport --dbname maint_db -c \'CREATE ROLE "testgroup" WITH PASSWORD \'"\'"\'testrolepass\'"\'"\' IN GROUP testgroup\'',
            host='testhost', password='foo', runas='foo', run_cmd='cmd.run')

    @patch('salt.modules.postgres._run_psql', Mock(return_value={'retcode': None}))
    @patch('salt.modules.postgres.user_exists', Mock(return_value=True))
    def test_group_remove(self):
        postgres.group_remove(
            'testgroup',
            user='testuser',
            host='testhost',
            port='testport',
            maintenance_db='maint_db',
            password='foo',
            runas='foo'
        )
        postgres._run_psql.assert_called_once_with(
            "/usr/bin/pgsql --no-align --no-readline --username testuser --host testhost --port testport --dbname maint_db -c 'DROP ROLE testgroup'",
            host='testhost', password='foo', runas='foo', run_cmd='cmd.run')

    @patch('salt.modules.postgres._run_psql', Mock(return_value={'retcode': None}))
    @patch('salt.modules.postgres.user_exists', Mock(return_value=True))
    def test_group_update(self):
        postgres.group_update(
            'testgroup',
            user='testuser',
            host='testhost',
            port='testport',
            maintenance_db='maint_db',
            password='foo',
            createdb=False,
            createuser=False,
            encrypted=False,
            replication=False,
            rolepassword='test_role_pass',
            groups='testgroup',
            runas='foo'
        )
        postgres._run_psql.assert_called_once_with(
            '/usr/bin/pgsql --no-align --no-readline --username testuser --host testhost --port testport --dbname maint_db -c \'ALTER ROLE testgroup WITH PASSWORD \'"\'"\'test_role_pass\'"\'"\'; GRANT testgroup TO testgroup\'',
            host='testhost', password='foo', runas='foo', run_cmd='cmd.run'
        )

    @patch('salt.modules.postgres._run_psql', Mock(return_value={'retcode': None}))
    @patch('salt.modules.postgres.user_exists', Mock(return_value=False))
    def test_user_create(self):
        postgres.user_create(
            'testuser',
            user='testuser',
            host='testhose',
            port='testport',
            maintenance_db='maint_test',
            password='test_pass',
            createdb=False,
            createuser=False,
            encrypted=False,
            superuser=False,
            replication=False,
            rolepassword='test_role_pass',
            groups='test_groups',
            runas='foo'
        )
        postgres._run_psql.assert_called_once_with(
            '/usr/bin/pgsql --no-align --no-readline --username testuser --host testhose --port testport --dbname maint_test -c \'CREATE USER "testuser" WITH PASSWORD \'"\'"\'test_role_pass\'"\'"\' IN GROUP test_groups\'',
            host='testhose', password='test_pass', runas='foo', run_cmd='cmd.run'
        )

    @patch('salt.modules.postgres._run_psql', Mock(return_value={'retcode': None}))
    @patch('salt.modules.postgres.version', Mock(return_value='9.1'))
    @patch('salt.modules.postgres.psql_query', Mock(return_value=[
        {
        'name': 'test_user',
        'superuser': 't',
        'inherits privileges': 't',
        'can create roles': 't',
        'can create databases': 't',
        'can update system catalogs': 't',
        'can login': 't',
        'replication': None,
        'connections': '-1',
        'defaults variables': None
    }]))
    def test_user_exists(self):
        ret = postgres.user_exists(
            'test_user',
            user='test_user',
            host='test_host',
            port='test_port',
            maintenance_db='maint_db',
            password='test_password',
            runas='foo'
        )
        self.assertTrue(ret)

    @patch('salt.modules.postgres._run_psql', Mock(return_value={'retcode': None}))
    @patch('salt.modules.postgres.version', Mock(return_value='9.1'))
    @patch('salt.modules.postgres.psql_query', Mock(return_value=[
        {
        'name': 'test_user',
        'superuser': 't',
        'inherits privileges': 't',
        'can create roles': 't',
        'can create databases': 't',
        'can update system catalogs': 't',
        'can login': 't',
        'replication': None,
        'connections': '-1',
        'defaults variables': None
        }]))
    def test_user_list(self):
        ret = postgres.user_list(
            'test_user',
            host='test_host',
            port='test_port',
            maintenance_db='maint_db',
            password='test_password',
            runas='foo'
        )

        self.assertDictEqual(ret, {'test_user': {'superuser': True, 'defaults variables': None, 'can create databases': True, 'can create roles': True, 'connections': None, 'replication': None, 'expiry time': None, 'can login': True, 'can update system catalogs': True, 'inherits privileges': True}})

    @patch('salt.modules.postgres._run_psql', Mock(return_value={'retcode': None}))
    @patch('salt.modules.postgres.version', Mock(return_value='9.1'))
    @patch('salt.modules.postgres.user_exists', Mock(return_value=True))
    def test_user_remove(self):
        postgres.user_remove(
            'test_user',
            user='test_user',
            host='test_host',
            port='test_port',
            maintenance_db='maint_db',
            password='test_password',
            runas='foo'
        )
        postgres._run_psql.assert_called_once_with("/usr/bin/pgsql --no-align --no-readline --username test_user --host test_host --port test_port --dbname maint_db -c 'DROP ROLE test_user'", host='test_host', password='test_password', runas='foo', run_cmd='cmd.run')

    @patch('salt.modules.postgres._run_psql', Mock(return_value={'retcode': None}))
    @patch('salt.modules.postgres.user_exists', Mock(return_value=True))
    def test_user_update(self):
        postgres.user_update(
            'test_username',
            user='test_user',
            host='test_host',
            port='test_port',
            maintenance_db='test_maint',
            password='test_pass',
            createdb=False,
            createuser=False,
            encrypted=False,
            replication=False,
            rolepassword='test_role_pass',
            groups='test_groups',
            runas='foo'
        )
        postgres._run_psql.assert_called_once_with('/usr/bin/pgsql --no-align --no-readline --username test_user --host test_host --port test_port --dbname test_maint -c \'ALTER ROLE test_username WITH PASSWORD \'"\'"\'test_role_pass\'"\'"\'; GRANT test_groups TO test_username\'', host='test_host', password='test_pass', runas='foo', run_cmd='cmd.run')

    @patch('salt.modules.postgres._run_psql', Mock(return_value={'retcode': None, 'stdout': '9.1.9'}))
    def test_version(self):
        postgres.version(
            user='test_user',
            host='test_host',
            port='test_port',
            maintenance_db='test_maint',
            password='test_pass',
            runas='foo'
        )
        postgres._run_psql.assert_called_once_with('/usr/bin/pgsql --no-align --no-readline --username test_user --host test_host --port test_port --dbname test_maint -c \'SELECT setting FROM pg_catalog.pg_settings WHERE name = \'"\'"\'server_version\'"\'"\'\' -t', host='test_host', password='test_pass', runas='foo')

if __name__ == '__main__':
    from integration import run_tests

    run_tests(PostgresTestCase, needs_daemon=False)
