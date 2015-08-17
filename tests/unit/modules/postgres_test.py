# -*- coding: utf-8 -*-

# Import python libs
from __future__ import absolute_import, print_function
from mock import call
import re

# Import Salt Testing libs
from salttesting import skipIf, TestCase
from salttesting.helpers import ensure_in_syspath
from salttesting.mock import NO_MOCK, NO_MOCK_REASON, Mock, patch
ensure_in_syspath('../../')

# Import salt libs
from salt.modules import postgres

postgres.__grains__ = None  # in order to stub it w/patch below
postgres.__salt__ = None  # in order to stub it w/patch below

test_list_db_csv = (
    'Name,Owner,Encoding,Collate,Ctype,Access privileges,Tablespace\n'
    'template1,postgres,LATIN1,en_US,en_US'
    ',"{=c/postgres,postgres=CTc/postgres}",pg_default\n'
    'template0,postgres,LATIN1,en_US,en_US'
    ',"{=c/postgres,postgres=CTc/postgres}",pg_default\n'
    'postgres,postgres,LATIN1,en_US,en_US,,pg_default\n'
    'test_db,postgres,LATIN1,en_US,en_US,,pg_default'
)

test_list_schema_csv = (
    'name,owner,acl\n'
    'public,postgres,"{postgres=UC/postgres,=UC/postgres}"\n'
    'pg_toast,postgres,""'
)


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
                __salt__=SALT_STUB)
@patch('salt.utils.which', Mock(return_value='/usr/bin/pgsql'))
class PostgresTestCase(TestCase):
    def test_run_psql(self):
        postgres._run_psql('echo "hi"')
        cmd = SALT_STUB['cmd.run_all']

        self.assertEqual('postgres', cmd.call_args[1]['runas'])

    @patch('salt.modules.postgres._run_psql',
           Mock(return_value={'retcode': 0}))
    def test_db_alter(self):
        postgres.db_alter('dbname',
                          user='testuser',
                          host='testhost',
                          port='testport',
                          maintenance_db='maint_db',
                          password='foo',
                          tablespace='testspace',
                          owner='otheruser',
                          runas='foo')
        postgres._run_psql.assert_has_calls([
            call('/usr/bin/pgsql --no-align --no-readline --no-password --username testuser '
                 '--host testhost --port testport --dbname maint_db '
                 '-c \'ALTER DATABASE "dbname" OWNER TO "otheruser"\'',
                 host='testhost', user='testuser',
                 password='foo', runas='foo', port='testport'),
            call('/usr/bin/pgsql --no-align --no-readline --no-password --username testuser '
                 '--host testhost --port testport --dbname maint_db '
                 '-c \'ALTER DATABASE "dbname" SET TABLESPACE "testspace"\'',
                 host='testhost', user='testuser',
                 password='foo', runas='foo', port='testport')
        ])

    @patch('salt.modules.postgres.owner_to',
           Mock(return_value={'retcode': None}))
    def test_db_alter_owner_recurse(self):
        postgres.db_alter('dbname',
                          user='testuser',
                          host='testhost',
                          port='testport',
                          maintenance_db='maint_db',
                          password='foo',
                          tablespace='testspace',
                          owner='otheruser',
                          owner_recurse=True,
                          runas='foo')
        postgres.owner_to.assert_called_once_with('dbname',
                                                  'otheruser',
                                                  user='testuser',
                                                  host='testhost',
                                                  port='testport',
                                                  password='foo',
                                                  runas='foo')

    @patch('salt.modules.postgres._run_psql',
           Mock(return_value={'retcode': 0}))
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

        qstr = (
            '/usr/bin/pgsql --no-align --no-readline --no-password '
            '--username testuser --host testhost --port testport --dbname maint_db '
            '-c \'CREATE DATABASE "dbname" WITH TABLESPACE = testspace OWNER = "otheruser"\'')
        postgres._run_psql.assert_called_once_with(
            qstr,
            host='testhost', user='testuser',
            password='foo', runas='foo', port='testport')

    @patch('salt.modules.postgres._run_psql',
           Mock(return_value={'retcode': 0,
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

    @patch('salt.modules.postgres._run_psql',
           Mock(return_value={'retcode': 0,
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
            'test_db': {'Encoding': 'LATIN1', 'Ctype': 'en_US',
                        'Tablespace': 'pg_default', 'Collate': 'en_US',
                        'Owner': 'postgres', 'Access privileges': ''},
            'template1': {'Encoding': 'LATIN1', 'Ctype': 'en_US',
                          'Tablespace': 'pg_default', 'Collate': 'en_US',
                          'Owner': 'postgres',
                          'Access privileges': (
                              '{=c/postgres,postgres=CTc/postgres}'
                          )},
            'template0': {'Encoding': 'LATIN1', 'Ctype': 'en_US',
                          'Tablespace': 'pg_default', 'Collate': 'en_US',
                          'Owner': 'postgres',
                          'Access privileges': (
                              '{=c/postgres,postgres=CTc/postgres}'
                          )},
            'postgres': {'Encoding': 'LATIN1', 'Ctype': 'en_US',
                         'Tablespace': 'pg_default', 'Collate': 'en_US',
                         'Owner': 'postgres', 'Access privileges': ''}})

    @patch('salt.modules.postgres._run_psql',
           Mock(return_value={'retcode': 0}))
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
            "/usr/bin/pgsql --no-align --no-readline --no-password --username testuser "
            "--host testhost --port testport --dbname maint_db "
            "-c 'DROP DATABASE test_db'",
            host='testhost', user='testuser',
            password='foo', runas='foo', port='testport')

    @patch('salt.modules.postgres._run_psql',
           Mock(return_value={'retcode': 0}))
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
        self.assertTrue(re.match(
            '/usr/bin/pgsql --no-align --no-readline --no-password --username testuser '
            '--host testhost --port testport '
            '--dbname maint_db -c (\'|\")CREATE ROLE',
            postgres._run_psql.call_args[0][0]))

    @patch('salt.modules.postgres._run_psql',
           Mock(return_value={'retcode': 0}))
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
            "/usr/bin/pgsql --no-align --no-readline --no-password --username testuser "
            "--host testhost --port testport "
            "--dbname maint_db -c 'DROP ROLE testgroup'",
            host='testhost', user='testuser',
            password='foo', runas='foo', port='testport')

    @patch('salt.modules.postgres._run_psql',
           Mock(return_value={'retcode': 0}))
    @patch('salt.modules.postgres.role_get',
           Mock(return_value={'superuser': False}))
    def test_group_update(self):
        postgres.group_update(
            'testgroup',
            user='"testuser"',
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
        self.assertTrue(re.match(
            '.*'
            '(\'|\")ALTER.* (\\\\)?"testgroup(\\\\)?" .* UNENCRYPTED PASSWORD',
            postgres._run_psql.call_args[0][0]))

    @patch('salt.modules.postgres._run_psql',
           Mock(return_value={'retcode': 0}))
    @patch('salt.modules.postgres.user_exists',
           Mock(return_value=False))
    def test_user_create(self):
        postgres.user_create(
            'testuser',
            user='testuser',
            host='testhost',
            port='testport',
            maintenance_db='maint_test',
            password='test_pass',
            login=True,
            createdb=False,
            createroles=False,
            createuser=False,
            encrypted=False,
            superuser=False,
            replication=False,
            rolepassword='test_role_pass',
            groups='test_groups',
            runas='foo'
        )
        call = postgres._run_psql.call_args[0][0]
        self.assertTrue(re.match(
            '/usr/bin/pgsql --no-align --no-readline --no-password '
            '--username testuser'
            ' --host testhost --port testport'
            ' --dbname maint_test -c (\'|\")CREATE ROLE (\\\\)?"testuser(\\\\)?"',
            call))

        for i in (
            'INHERIT NOCREATEDB NOCREATEROLE '
            'NOSUPERUSER NOREPLICATION LOGIN UNENCRYPTED PASSWORD'
        ).split():
            self.assertTrue(i in call, '{0} not in {1}'.format(i, call))

    @patch('salt.modules.postgres._run_psql',
           Mock(return_value={'retcode': 0}))
    @patch('salt.modules.postgres.version',
           Mock(return_value='9.1'))
    @patch('salt.modules.postgres.psql_query',
           Mock(return_value=[
               {
                   'name': 'test_user',
                   'superuser': 't',
                   'inherits privileges': 't',
                   'can create roles': 't',
                   'can create databases': 't',
                   'can update system catalogs': 't',
                   'can login': 't',
                   'replication': None,
                   'password': 'test_password',
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

    @patch('salt.modules.postgres._run_psql',
           Mock(return_value={'retcode': 0}))
    @patch('salt.modules.postgres.version',
           Mock(return_value='9.1'))
    @patch('salt.modules.postgres.psql_query',
           Mock(return_value=[
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

        self.assertDictEqual(ret, {
            'test_user': {'superuser': True,
                          'defaults variables': None,
                          'can create databases': True,
                          'can create roles': True,
                          'connections': None,
                          'replication': None,
                          'expiry time': None,
                          'can login': True,
                          'can update system catalogs': True,
                          'groups': [],
                          'inherits privileges': True}})

    @patch('salt.modules.postgres._run_psql',
           Mock(return_value={'retcode': 0}))
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
        postgres._run_psql.assert_called_once_with(
            "/usr/bin/pgsql --no-align --no-readline --no-password "
            "--username test_user "
            "--host test_host --port test_port "
            "--dbname maint_db -c 'DROP ROLE test_user'",
            host='test_host', port='test_port', user='test_user',
            password='test_password', runas='foo')

    @patch('salt.modules.postgres._run_psql',
           Mock(return_value={'retcode': 0}))
    @patch('salt.modules.postgres.role_get',
           Mock(return_value={'superuser': False}))
    def test_user_update(self):
        postgres.user_update(
            'test_username',
            user='test_user',
            host='test_host',
            port='test_port',
            maintenance_db='test_maint',
            password='test_pass',
            createdb=False,
            createroles=False,
            createuser=False,
            encrypted=False,
            inherit=True,
            login=True,
            replication=False,
            rolepassword='test_role_pass',
            groups='test_groups',
            runas='foo'
        )
        call_output = postgres._run_psql.call_args[0][0]
        self.assertTrue(
            re.match(
                '/usr/bin/pgsql --no-align --no-readline --no-password '
                '--username test_user '
                '--host test_host --port test_port --dbname test_maint '
                '-c [\'"]{0,1}ALTER ROLE (\\\\)?"test_username(\\\\)?" WITH  INHERIT NOCREATEDB '
                'NOCREATEROLE NOREPLICATION LOGIN '
                'UNENCRYPTED PASSWORD [\'"]{0,5}test_role_pass[\'"]{0,5};'
                ' GRANT (\\\\)?"test_groups(\\\\)?" TO (\\\\)?"test_username(\\\\)?"[\'"]{0,1}',
                call_output)
        )

    @patch('salt.modules.postgres._run_psql',
           Mock(return_value={'retcode': 0}))
    @patch('salt.modules.postgres.role_get',
           Mock(return_value={'superuser': False}))
    def test_user_update2(self):
        postgres.user_update(
            'test_username',
            user='test_user',
            host='test_host',
            port='test_port',
            maintenance_db='test_maint',
            password='test_pass',
            createdb=False,
            createroles=True,
            createuser=False,
            encrypted=False,
            inherit=True,
            login=True,
            replication=False,
            groups='test_groups',
            runas='foo'
        )
        call_output = postgres._run_psql.call_args[0][0]
        self.assertTrue(
            re.match(
                '/usr/bin/pgsql --no-align --no-readline --no-password --username test_user '
                '--host test_host --port test_port --dbname test_maint '
                '-c \'ALTER ROLE "test_username" WITH  INHERIT NOCREATEDB '
                'CREATEROLE NOREPLICATION LOGIN;'
                ' GRANT "test_groups" TO "test_username"\'',
                call_output)
        )

    @patch('salt.modules.postgres._run_psql',
           Mock(return_value={'retcode': 0}))
    @patch('salt.modules.postgres.role_get',
           Mock(return_value={'superuser': False}))
    def test_user_update3(self):
        postgres.user_update(
            'test_username',
            user='test_user',
            host='test_host',
            port='test_port',
            maintenance_db='test_maint',
            password='test_pass',
            createdb=False,
            createroles=True,
            createuser=False,
            encrypted=False,
            inherit=True,
            login=True,
            rolepassword=False,
            replication=False,
            groups='test_groups',
            runas='foo'
        )
        call_output = postgres._run_psql.call_args[0][0]
        self.assertTrue(
            re.match(
                '/usr/bin/pgsql --no-align --no-readline --no-password '
                '--username test_user '
                '--host test_host --port test_port --dbname test_maint '
                '-c \'ALTER ROLE "test_username" WITH  INHERIT NOCREATEDB '
                'CREATEROLE NOREPLICATION LOGIN NOPASSWORD;'
                ' GRANT "test_groups" TO "test_username"\'',
                call_output)
        )

    @patch('salt.modules.postgres._run_psql',
           Mock(return_value={'retcode': 0}))
    @patch('salt.modules.postgres.role_get',
           Mock(return_value={'superuser': False}))
    def test_user_update_encrypted_passwd(self):
        postgres.user_update(
            'test_username',
            user='test_user',
            host='test_host',
            port='test_port',
            maintenance_db='test_maint',
            password='test_pass',
            createdb=False,
            createroles=True,
            createuser=False,
            encrypted=True,
            inherit=True,
            login=True,
            rolepassword='foobar',
            replication=False,
            groups='test_groups',
            runas='foo'
        )
        call_output = postgres._run_psql.call_args[0][0]
        self.assertTrue(
            re.match(
                '/usr/bin/pgsql --no-align --no-readline --no-password '
                '--username test_user '
                '--host test_host --port test_port --dbname test_maint '
                '-c [\'"]{0,1}ALTER ROLE (\\\\)?"test_username(\\\\)?" WITH  INHERIT NOCREATEDB '
                'CREATEROLE NOREPLICATION LOGIN '
                'ENCRYPTED PASSWORD '
                '[\'"]{0,5}md531c27e68d3771c392b52102c01be1da1[\'"]{0,5}'
                '; GRANT (\\\\)?"test_groups(\\\\)?" TO (\\\\)?"test_username(\\\\)?"[\'"]{0,1}',
                call_output)
        )

    @patch('salt.modules.postgres._run_psql',
           Mock(return_value={'retcode': 0, 'stdout': '9.1.9'}))
    def test_version(self):
        postgres.version(
            user='test_user',
            host='test_host',
            port='test_port',
            maintenance_db='test_maint',
            password='test_pass',
            runas='foo'
        )
        call_output = postgres._run_psql.call_args[0][0]
        self.assertTrue(re.match(
            '/usr/bin/pgsql --no-align --no-readline --no-password '
            '--username test_user '
            '--host test_host --port test_port '
            '--dbname test_maint '
            '-c (\'|\")SELECT setting FROM pg_catalog.pg_settings',
            call_output))

    @patch('salt.modules.postgres.psql_query',
           Mock(return_value=[{'extname': "foo", 'extversion': "1"}]))
    def test_installed_extensions(self):
        exts = postgres.installed_extensions()
        self.assertEqual(
            exts,
            {'foo': {'extversion': '1', 'extname': 'foo'}}
        )

    @patch('salt.modules.postgres.psql_query',
           Mock(return_value=[{'name': "foo", 'default_version': "1"}]))
    def test_available_extensions(self):
        exts = postgres.available_extensions()
        self.assertEqual(
            exts,
            {'foo': {'default_version': '1', 'name': 'foo'}}
        )

    @patch('salt.modules.postgres.installed_extensions',
           Mock(side_effect=[{}, {}]))
    @patch('salt.modules.postgres._psql_prepare_and_run',
           Mock(return_value=None))
    @patch('salt.modules.postgres.available_extensions',
           Mock(return_value={'foo': {'default_version': '1', 'name': 'foo'}}))
    def test_drop_extension2(self):
        self.assertEqual(postgres.drop_extension('foo'), True)

    @patch('salt.modules.postgres.installed_extensions',
           Mock(side_effect=[{'foo': {'extversion': '1', 'extname': 'foo'}},
                             {}]))
    @patch('salt.modules.postgres._psql_prepare_and_run',
           Mock(return_value=None))
    @patch('salt.modules.postgres.available_extensions',
           Mock(return_value={'foo': {'default_version': '1', 'name': 'foo'}}))
    def test_drop_extension3(self):
        self.assertEqual(postgres.drop_extension('foo'), True)

    @patch('salt.modules.postgres.installed_extensions',
           Mock(side_effect=[{'foo': {'extversion': '1', 'extname': 'foo'}},
                             {'foo': {'extversion': '1', 'extname': 'foo'}}]))
    @patch('salt.modules.postgres._psql_prepare_and_run',
           Mock(return_value=None))
    @patch('salt.modules.postgres.available_extensions',
           Mock(return_value={'foo': {'default_version': '1', 'name': 'foo'}}))
    def test_drop_extension1(self):
        self.assertEqual(postgres.drop_extension('foo'), False)

    @patch('salt.modules.postgres.installed_extensions',
           Mock(return_value={
               'foo': {'extversion': '0.8',
                       'extrelocatable': 't',
                       'schema_name': 'foo',
                       'extname': 'foo'}},
           ))
    @patch('salt.modules.postgres.available_extensions',
           Mock(return_value={'foo': {'default_version': '1.4',
                                      'name': 'foo'}}))
    def test_create_mtdata(self):
        ret = postgres.create_metadata('foo', schema='bar', ext_version='1.4')
        self.assertTrue(postgres._EXTENSION_INSTALLED in ret)
        self.assertTrue(postgres._EXTENSION_TO_UPGRADE in ret)
        self.assertTrue(postgres._EXTENSION_TO_MOVE in ret)
        ret = postgres.create_metadata('foo', schema='foo', ext_version='0.4')
        self.assertTrue(postgres._EXTENSION_INSTALLED in ret)
        self.assertFalse(postgres._EXTENSION_TO_UPGRADE in ret)
        self.assertFalse(postgres._EXTENSION_TO_MOVE in ret)
        ret = postgres.create_metadata('foo')
        self.assertTrue(postgres._EXTENSION_INSTALLED in ret)
        self.assertFalse(postgres._EXTENSION_TO_UPGRADE in ret)
        self.assertFalse(postgres._EXTENSION_TO_MOVE in ret)
        ret = postgres.create_metadata('foobar')
        self.assertTrue(postgres._EXTENSION_NOT_INSTALLED in ret)
        self.assertFalse(postgres._EXTENSION_INSTALLED in ret)
        self.assertFalse(postgres._EXTENSION_TO_UPGRADE in ret)
        self.assertFalse(postgres._EXTENSION_TO_MOVE in ret)

    @patch('salt.modules.postgres.create_metadata',
           Mock(side_effect=[
               # create succeeded
               [postgres._EXTENSION_NOT_INSTALLED],
               [postgres._EXTENSION_INSTALLED],
               [postgres._EXTENSION_NOT_INSTALLED],
               [postgres._EXTENSION_INSTALLED],
               # create failed
               [postgres._EXTENSION_NOT_INSTALLED],
               [postgres._EXTENSION_NOT_INSTALLED],
               # move+upgrade succeeded
               [postgres._EXTENSION_TO_MOVE,
                postgres._EXTENSION_TO_UPGRADE,
                postgres._EXTENSION_INSTALLED],
               [postgres._EXTENSION_INSTALLED],
               # move succeeded
               [postgres._EXTENSION_TO_MOVE,
                postgres._EXTENSION_INSTALLED],
               [postgres._EXTENSION_INSTALLED],
               # upgrade succeeded
               [postgres._EXTENSION_TO_UPGRADE,
                postgres._EXTENSION_INSTALLED],
               [postgres._EXTENSION_INSTALLED],
               # upgrade failed
               [postgres._EXTENSION_TO_UPGRADE, postgres._EXTENSION_INSTALLED],
               [postgres._EXTENSION_TO_UPGRADE, postgres._EXTENSION_INSTALLED],
               # move failed
               [postgres._EXTENSION_TO_MOVE, postgres._EXTENSION_INSTALLED],
               [postgres._EXTENSION_TO_MOVE, postgres._EXTENSION_INSTALLED],
           ]))
    @patch('salt.modules.postgres._psql_prepare_and_run',
           Mock(return_value=None))
    @patch('salt.modules.postgres.available_extensions',
           Mock(return_value={'foo': {'default_version': '1.4',
                                      'name': 'foo'}}))
    def test_create_extension_newerthan(self):
        '''
        scenario of creating upgrading extensions with possible schema and
        version specifications
        '''
        self.assertTrue(postgres.create_extension('foo'))
        self.assertTrue(re.match(
            'CREATE EXTENSION IF NOT EXISTS "foo" ;',
            postgres._psql_prepare_and_run.call_args[0][0][1]))
        self.assertTrue(postgres.create_extension(
            'foo', schema='a', ext_version='b', from_version='c'))
        self.assertTrue(re.match(
            'CREATE EXTENSION IF NOT EXISTS "foo" '
            'WITH SCHEMA a VERSION b FROM c ;',
            postgres._psql_prepare_and_run.call_args[0][0][1]))
        self.assertFalse(postgres.create_extension('foo'))
        ret = postgres.create_extension('foo', ext_version='a', schema='b')
        self.assertTrue(ret)
        self.assertTrue(re.match(
            'ALTER EXTENSION "foo" SET SCHEMA b;'
            ' ALTER EXTENSION "foo" UPDATE TO a;',
            postgres._psql_prepare_and_run.call_args[0][0][1]))
        ret = postgres.create_extension('foo', ext_version='a', schema='b')
        self.assertTrue(ret)
        self.assertTrue(re.match(
            'ALTER EXTENSION "foo" SET SCHEMA b;',
            postgres._psql_prepare_and_run.call_args[0][0][1]))
        ret = postgres.create_extension('foo', ext_version='a', schema='b')
        self.assertTrue(ret)
        self.assertTrue(re.match(
            'ALTER EXTENSION "foo" UPDATE TO a;',
            postgres._psql_prepare_and_run.call_args[0][0][1]))
        self.assertFalse(postgres.create_extension(
            'foo', ext_version='a', schema='b'))
        self.assertFalse(postgres.create_extension(
            'foo', ext_version='a', schema='b'))

    def test_encrypt_passwords(self):
        self.assertEqual(
            postgres._maybe_encrypt_password(
                'foo', 'bar', False),
            'bar')
        self.assertEqual(
            postgres._maybe_encrypt_password(
                'foo', 'bar', True),
            'md596948aad3fcae80c08a35c9b5958cd89')

    @patch('salt.modules.postgres._run_psql',
           Mock(return_value={'retcode': 0,
                              'stdout': test_list_schema_csv}))
    def test_schema_list(self):
        ret = postgres.schema_list(
            'maint_db',
            db_user='testuser',
            db_host='testhost',
            db_port='testport',
            db_password='foo'
        )
        self.assertDictEqual(ret, {
            'public': {'acl': '{postgres=UC/postgres,=UC/postgres}',
                       'owner': 'postgres'},
            'pg_toast': {'acl': '', 'owner': 'postgres'}
            })

    @patch('salt.modules.postgres._run_psql',
           Mock(return_value={'retcode': 0}))
    @patch('salt.modules.postgres.psql_query',
           Mock(return_value=[
               {
                   'name': 'public',
                   'acl': '{postgres=UC/postgres,=UC/postgres}',
                   'owner': 'postgres'
               }]))
    def test_schema_exists(self):
        ret = postgres.schema_exists(
            'template1',
            'public'
        )
        self.assertTrue(ret)

    @patch('salt.modules.postgres._run_psql',
           Mock(return_value={'retcode': 0}))
    @patch('salt.modules.postgres.psql_query',
           Mock(return_value=[
               {
                   'name': 'public',
                   'acl': '{postgres=UC/postgres,=UC/postgres}',
                   'owner': 'postgres'
               }]))
    def test_schema_get(self):
        ret = postgres.schema_get(
            'template1',
            'public'
        )
        self.assertTrue(ret)

    @patch('salt.modules.postgres._run_psql',
           Mock(return_value={'retcode': 0}))
    @patch('salt.modules.postgres.psql_query',
           Mock(return_value=[
               {
                   'name': 'public',
                   'acl': '{postgres=UC/postgres,=UC/postgres}',
                   'owner': 'postgres'
               }]))
    def test_schema_get_again(self):
        ret = postgres.schema_get(
            'template1',
            'pg_toast'
        )
        self.assertFalse(ret)

    @patch('salt.modules.postgres._run_psql',
           Mock(return_value={'retcode': 0}))
    @patch('salt.modules.postgres.schema_exists', Mock(return_value=False))
    def test_schema_create(self):
        postgres.schema_create(
            'test_db',
            'test_schema',
            user='user',
            db_host='test_host',
            db_port='test_port',
            db_user='test_user',
            db_password='test_password'
        )
        postgres._run_psql.assert_called_once_with(
            "/usr/bin/pgsql --no-align --no-readline --no-password "
            "--username test_user "
            "--host test_host --port test_port "
            "--dbname test_db -c 'CREATE SCHEMA test_schema'",
            host='test_host', port='test_port',
            password='test_password', user='test_user', runas='user')

    @patch('salt.modules.postgres.schema_exists', Mock(return_value=True))
    def test_schema_create2(self):
        ret = postgres.schema_create('test_db',
                                     'test_schema',
                                     user='user',
                                     db_host='test_host',
                                     db_port='test_port',
                                     db_user='test_user',
                                     db_password='test_password'
                                     )
        self.assertFalse(ret)

    @patch('salt.modules.postgres._run_psql',
           Mock(return_value={'retcode': 0}))
    @patch('salt.modules.postgres.schema_exists', Mock(return_value=True))
    def test_schema_remove(self):
        postgres.schema_remove(
            'test_db',
            'test_schema',
            user='user',
            db_host='test_host',
            db_port='test_port',
            db_user='test_user',
            db_password='test_password'
        )
        postgres._run_psql.assert_called_once_with(
            "/usr/bin/pgsql --no-align --no-readline --no-password "
            "--username test_user "
            "--host test_host --port test_port "
            "--dbname test_db -c 'DROP SCHEMA test_schema'",
            host='test_host', port='test_port',
            password='test_password', user='test_user', runas='user')

    @patch('salt.modules.postgres.schema_exists', Mock(return_value=False))
    def test_schema_remove2(self):
        ret = postgres.schema_remove('test_db',
                                     'test_schema',
                                     user='user',
                                     db_host='test_host',
                                     db_port='test_port',
                                     db_user='test_user',
                                     db_password='test_password'
                                     )
        self.assertFalse(ret)

if __name__ == '__main__':
    from integration import run_tests
    run_tests(PostgresTestCase, needs_daemon=False)
