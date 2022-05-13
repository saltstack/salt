import datetime
import logging
import re

import salt.modules.postgres as postgres
from salt.exceptions import SaltInvocationError
from tests.support.mixins import LoaderModuleMockMixin
from tests.support.mock import Mock, call, patch
from tests.support.unit import TestCase

test_list_db_csv = (
    "Name,Owner,Encoding,Collate,Ctype,Access privileges,Tablespace\n"
    "template1,postgres,LATIN1,en_US,en_US"
    ',"{=c/postgres,postgres=CTc/postgres}",pg_default\n'
    "template0,postgres,LATIN1,en_US,en_US"
    ',"{=c/postgres,postgres=CTc/postgres}",pg_default\n'
    "postgres,postgres,LATIN1,en_US,en_US,,pg_default\n"
    "test_db,postgres,LATIN1,en_US,en_US,,pg_default"
)

test_list_schema_csv = (
    "name,owner,acl\n"
    'public,postgres,"{postgres=UC/postgres,=UC/postgres}"\n'
    'pg_toast,postgres,""'
)

test_list_language_csv = "Name\ninternal\nc\nsql\nplpgsql\n"

test_privileges_list_table_csv = (
    "name\n"
    '"{baruwatest=arwdDxt/baruwatest,bayestest=arwd/baruwatest,baruwa=a*r*w*d*D*x*t*/baruwatest}"\n'
)

test_privileges_list_group_csv = (
    "rolname,admin_option\nbaruwa,f\nbaruwatest2,t\nbaruwatest,f\n"
)

log = logging.getLogger(__name__)


class PostgresTestCase(TestCase, LoaderModuleMockMixin):
    def setup_loader_modules(self):
        patcher = patch("salt.utils.path.which", Mock(return_value="/usr/bin/pgsql"))
        patcher.start()
        self.addCleanup(patcher.stop)
        return {
            postgres: {
                "__grains__": {"os_family": "Linux"},
                "__salt__": {
                    "config.option": Mock(),
                    "cmd.run_all": Mock(),
                    "file.chown": Mock(),
                    "file.remove": Mock(),
                },
            }
        }

    def test_run_psql(self):
        postgres._run_psql('echo "hi"')
        cmd = postgres.__salt__["cmd.run_all"]

        self.assertEqual("postgres", cmd.call_args[1]["runas"])

    def test_db_alter(self):
        with patch(
            "salt.modules.postgres._run_psql", Mock(return_value={"retcode": 0})
        ):
            postgres.db_alter(
                "dbname",
                user="testuser",
                host="testhost",
                port="testport",
                maintenance_db="maint_db",
                password="foo",
                tablespace="testspace",
                owner="otheruser",
                runas="foo",
            )
            postgres._run_psql.assert_has_calls(
                [
                    call(
                        [
                            "/usr/bin/pgsql",
                            "--no-align",
                            "--no-readline",
                            "--no-psqlrc",
                            "--no-password",
                            "--username",
                            "testuser",
                            "--host",
                            "testhost",
                            "--port",
                            "testport",
                            "--dbname",
                            "maint_db",
                            "-c",
                            'ALTER DATABASE "dbname" OWNER TO "otheruser"',
                        ],
                        host="testhost",
                        user="testuser",
                        password="foo",
                        runas="foo",
                        port="testport",
                    ),
                    call(
                        [
                            "/usr/bin/pgsql",
                            "--no-align",
                            "--no-readline",
                            "--no-psqlrc",
                            "--no-password",
                            "--username",
                            "testuser",
                            "--host",
                            "testhost",
                            "--port",
                            "testport",
                            "--dbname",
                            "maint_db",
                            "-c",
                            'ALTER DATABASE "dbname" SET TABLESPACE "testspace"',
                        ],
                        host="testhost",
                        user="testuser",
                        password="foo",
                        runas="foo",
                        port="testport",
                    ),
                ]
            )

    def test_db_alter_owner_recurse(self):
        with patch(
            "salt.modules.postgres.owner_to", Mock(return_value={"retcode": None})
        ):
            postgres.db_alter(
                "dbname",
                user="testuser",
                host="testhost",
                port="testport",
                maintenance_db="maint_db",
                password="foo",
                tablespace="testspace",
                owner="otheruser",
                owner_recurse=True,
                runas="foo",
            )
            postgres.owner_to.assert_called_once_with(
                "dbname",
                "otheruser",
                user="testuser",
                host="testhost",
                port="testport",
                password="foo",
                runas="foo",
            )

    def test_db_create(self):
        with patch(
            "salt.modules.postgres._run_psql", Mock(return_value={"retcode": 0})
        ):
            postgres.db_create(
                "dbname",
                user="testuser",
                host="testhost",
                port="testport",
                maintenance_db="maint_db",
                password="foo",
                tablespace="testspace",
                owner="otheruser",
                runas="foo",
            )

            postgres._run_psql.assert_called_once_with(
                [
                    "/usr/bin/pgsql",
                    "--no-align",
                    "--no-readline",
                    "--no-psqlrc",
                    "--no-password",
                    "--username",
                    "testuser",
                    "--host",
                    "testhost",
                    "--port",
                    "testport",
                    "--dbname",
                    "maint_db",
                    "-c",
                    'CREATE DATABASE "dbname" WITH TABLESPACE = "testspace" '
                    'OWNER = "otheruser"',
                ],
                host="testhost",
                user="testuser",
                password="foo",
                runas="foo",
                port="testport",
            )

    def test_db_create_empty_string_param(self):
        with patch(
            "salt.modules.postgres._run_psql", Mock(return_value={"retcode": 0})
        ):
            postgres.db_create(
                "dbname",
                lc_collate="",
                encoding="utf8",
                user="testuser",
                host="testhost",
                port=1234,
                maintenance_db="maint_db",
                password="foo",
            )

            postgres._run_psql.assert_called_once_with(
                [
                    "/usr/bin/pgsql",
                    "--no-align",
                    "--no-readline",
                    "--no-psqlrc",
                    "--no-password",
                    "--username",
                    "testuser",
                    "--host",
                    "testhost",
                    "--port",
                    "1234",
                    "--dbname",
                    "maint_db",
                    "-c",
                    "CREATE DATABASE \"dbname\" WITH ENCODING = 'utf8' LC_COLLATE = ''",
                ],
                host="testhost",
                password="foo",
                port=1234,
                runas=None,
                user="testuser",
            )

    def test_db_create_with_trivial_sql_injection(self):
        with patch(
            "salt.modules.postgres._run_psql", Mock(return_value={"retcode": 0})
        ):
            self.assertRaises(
                SaltInvocationError,
                postgres.db_create,
                "dbname",
                lc_collate="foo' ENCODING='utf8",
            )

    def test_db_exists(self):
        with patch(
            "salt.modules.postgres._run_psql",
            Mock(return_value={"retcode": 0, "stdout": test_list_db_csv}),
        ):
            ret = postgres.db_exists(
                "test_db",
                user="testuser",
                host="testhost",
                port="testport",
                maintenance_db="maint_db",
                password="foo",
                runas="foo",
            )
            self.assertTrue(ret)

    def test_db_list(self):
        with patch(
            "salt.modules.postgres._run_psql",
            Mock(return_value={"retcode": 0, "stdout": test_list_db_csv}),
        ):
            ret = postgres.db_list(
                user="testuser",
                host="testhost",
                port="testport",
                maintenance_db="maint_db",
                password="foo",
                runas="foo",
            )
            self.assertDictEqual(
                ret,
                {
                    "test_db": {
                        "Encoding": "LATIN1",
                        "Ctype": "en_US",
                        "Tablespace": "pg_default",
                        "Collate": "en_US",
                        "Owner": "postgres",
                        "Access privileges": "",
                    },
                    "template1": {
                        "Encoding": "LATIN1",
                        "Ctype": "en_US",
                        "Tablespace": "pg_default",
                        "Collate": "en_US",
                        "Owner": "postgres",
                        "Access privileges": "{=c/postgres,postgres=CTc/postgres}",
                    },
                    "template0": {
                        "Encoding": "LATIN1",
                        "Ctype": "en_US",
                        "Tablespace": "pg_default",
                        "Collate": "en_US",
                        "Owner": "postgres",
                        "Access privileges": "{=c/postgres,postgres=CTc/postgres}",
                    },
                    "postgres": {
                        "Encoding": "LATIN1",
                        "Ctype": "en_US",
                        "Tablespace": "pg_default",
                        "Collate": "en_US",
                        "Owner": "postgres",
                        "Access privileges": "",
                    },
                },
            )

    def test_db_remove(self):
        with patch(
            "salt.modules.postgres._run_psql", Mock(return_value={"retcode": 0})
        ):
            postgres.db_remove(
                "test_db",
                user="testuser",
                host="testhost",
                port="testport",
                maintenance_db="maint_db",
                password="foo",
                runas="foo",
            )

            calls = (
                call(
                    [
                        "/usr/bin/pgsql",
                        "--no-align",
                        "--no-readline",
                        "--no-psqlrc",
                        "--no-password",
                        "--username",
                        "testuser",
                        "--host",
                        "testhost",
                        "--port",
                        "testport",
                        "--dbname",
                        "maint_db",
                        "-c",
                        'REVOKE CONNECT ON DATABASE "test_db" FROM public;',
                    ],
                    host="testhost",
                    password="foo",
                    port="testport",
                    runas="foo",
                    user="testuser",
                ),
                call(
                    [
                        "/usr/bin/pgsql",
                        "--no-align",
                        "--no-readline",
                        "--no-psqlrc",
                        "--no-password",
                        "--username",
                        "testuser",
                        "--host",
                        "testhost",
                        "--port",
                        "testport",
                        "--dbname",
                        "maint_db",
                        "-c",
                        "SELECT pid, pg_terminate_backend(pid) FROM pg_stat_activity"
                        " WHERE datname = 'test_db' AND pid <> pg_backend_pid();",
                    ],
                    host="testhost",
                    password="foo",
                    port="testport",
                    runas="foo",
                    user="testuser",
                ),
                call(
                    [
                        "/usr/bin/pgsql",
                        "--no-align",
                        "--no-readline",
                        "--no-psqlrc",
                        "--no-password",
                        "--username",
                        "testuser",
                        "--host",
                        "testhost",
                        "--port",
                        "testport",
                        "--dbname",
                        "maint_db",
                        "-c",
                        'DROP DATABASE "test_db";',
                    ],
                    host="testhost",
                    password="foo",
                    port="testport",
                    runas="foo",
                    user="testuser",
                ),
            )

            postgres._run_psql.assert_has_calls(calls, any_order=True)

    def test_group_create(self):
        with patch(
            "salt.modules.postgres._run_psql", Mock(return_value={"retcode": 0})
        ):
            with patch("salt.modules.postgres.user_exists", Mock(return_value=False)):
                postgres.group_create(
                    "testgroup",
                    user="testuser",
                    host="testhost",
                    port="testport",
                    maintenance_db="maint_db",
                    password="foo",
                    createdb=False,
                    encrypted=False,
                    superuser=False,
                    replication=False,
                    rolepassword="testrolepass",
                    groups="testgroup",
                    runas="foo",
                )
                # postgres._run_psql.call_args[0][0] will contain the list of CLI args.
                # The first 14 elements of this list are initial args used in all (or
                # virtually all) commands run through _run_psql(), so the actual SQL
                # query will be in the 15th argument.
                self.assertTrue(
                    postgres._run_psql.call_args[0][0][14].startswith("CREATE ROLE")
                )

    def test_group_remove(self):
        with patch(
            "salt.modules.postgres._run_psql", Mock(return_value={"retcode": 0})
        ):
            with patch("salt.modules.postgres.user_exists", Mock(return_value=True)):
                postgres.group_remove(
                    "testgroup",
                    user="testuser",
                    host="testhost",
                    port="testport",
                    maintenance_db="maint_db",
                    password="foo",
                    runas="foo",
                )
                postgres._run_psql.assert_called_once_with(
                    [
                        "/usr/bin/pgsql",
                        "--no-align",
                        "--no-readline",
                        "--no-psqlrc",
                        "--no-password",
                        "--username",
                        "testuser",
                        "--host",
                        "testhost",
                        "--port",
                        "testport",
                        "--dbname",
                        "maint_db",
                        "-c",
                        'DROP ROLE "testgroup"',
                    ],
                    host="testhost",
                    user="testuser",
                    password="foo",
                    runas="foo",
                    port="testport",
                )

    def test_group_update(self):
        with patch(
            "salt.modules.postgres._run_psql", Mock(return_value={"retcode": 0})
        ):
            with patch(
                "salt.modules.postgres.role_get",
                Mock(return_value={"superuser": False}),
            ):
                postgres.group_update(
                    "testgroup",
                    user='"testuser"',
                    host="testhost",
                    port="testport",
                    maintenance_db="maint_db",
                    password="foo",
                    createdb=False,
                    encrypted=False,
                    replication=False,
                    rolepassword="test_role_pass",
                    groups="testgroup",
                    runas="foo",
                )
                # postgres._run_psql.call_args[0][0] will contain the list of CLI args.
                # The first 14 elements of this list are initial args used in all (or
                # virtually all) commands run through _run_psql(), so the actual SQL
                # query will be in the 15th argument.
                self.assertTrue(
                    re.match(
                        'ALTER.* "testgroup" .* UNENCRYPTED PASSWORD',
                        postgres._run_psql.call_args[0][0][14],
                    )
                )

    def test_user_create(self):
        with patch(
            "salt.modules.postgres._run_psql", Mock(return_value={"retcode": 0})
        ):
            with patch("salt.modules.postgres.user_exists", Mock(return_value=False)):
                postgres.user_create(
                    "testuser",
                    user="testuser",
                    host="testhost",
                    port="testport",
                    maintenance_db="maint_test",
                    password="test_pass",
                    login=True,
                    createdb=False,
                    createroles=False,
                    encrypted=False,
                    superuser=False,
                    replication=False,
                    rolepassword="test_role_pass",
                    valid_until="2042-07-01",
                    groups="test_groups",
                    runas="foo",
                )
                # postgres._run_psql.call_args[0][0] will contain the list of CLI args.
                # The first 14 elements of this list are initial args used in all (or
                # virtually all) commands run through _run_psql(), so the actual SQL
                # query will be in the 15th argument.
                call = postgres._run_psql.call_args[0][0][14]
                self.assertTrue(re.match('CREATE ROLE "testuser"', call))
                for i in (
                    "INHERIT",
                    "NOCREATEDB",
                    "NOCREATEROLE",
                    "NOSUPERUSER",
                    "NOREPLICATION",
                    "LOGIN",
                    "UNENCRYPTED",
                    "PASSWORD",
                    "VALID UNTIL",
                ):
                    self.assertTrue(i in call, "{} not in {}".format(i, call))

    def test_user_exists(self):
        with patch(
            "salt.modules.postgres._run_psql", Mock(return_value={"retcode": 0})
        ):
            with patch("salt.modules.postgres.version", Mock(return_value="9.1")):
                with patch(
                    "salt.modules.postgres.psql_query",
                    Mock(
                        return_value=[
                            {
                                "name": "test_user",
                                "superuser": "t",
                                "inherits privileges": "t",
                                "can create roles": "t",
                                "can create databases": "t",
                                "can update system catalogs": "t",
                                "can login": "t",
                                "replication": None,
                                "password": "test_password",
                                "connections": "-1",
                                "groups": "",
                                "expiry time": "",
                                "defaults variables": None,
                            }
                        ]
                    ),
                ):
                    ret = postgres.user_exists(
                        "test_user",
                        user="test_user",
                        host="test_host",
                        port="test_port",
                        maintenance_db="maint_db",
                        password="test_password",
                        runas="foo",
                    )
                    self.assertTrue(ret)

    def test_user_list(self):
        with patch(
            "salt.modules.postgres._run_psql", Mock(return_value={"retcode": 0})
        ):
            with patch("salt.modules.postgres.version", Mock(return_value="9.1")):
                with patch(
                    "salt.modules.postgres.psql_query",
                    Mock(
                        return_value=[
                            {
                                "name": "test_user",
                                "superuser": "t",
                                "inherits privileges": "t",
                                "can create roles": "t",
                                "can create databases": "t",
                                "can update system catalogs": "t",
                                "can login": "t",
                                "replication": None,
                                "connections": "-1",
                                "groups": "",
                                "expiry time": "2017-08-16 08:57:46",
                                "defaults variables": None,
                            }
                        ]
                    ),
                ):
                    ret = postgres.user_list(
                        "test_user",
                        host="test_host",
                        port="test_port",
                        maintenance_db="maint_db",
                        password="test_password",
                        runas="foo",
                    )

                    self.assertDictEqual(
                        ret,
                        {
                            "test_user": {
                                "superuser": True,
                                "defaults variables": None,
                                "can create databases": True,
                                "can create roles": True,
                                "connections": None,
                                "replication": None,
                                "expiry time": datetime.datetime(
                                    2017, 8, 16, 8, 57, 46
                                ),
                                "can login": True,
                                "can update system catalogs": True,
                                "groups": [],
                                "inherits privileges": True,
                            }
                        },
                    )

    def test_user_remove(self):
        with patch(
            "salt.modules.postgres._run_psql", Mock(return_value={"retcode": 0})
        ):
            with patch("salt.modules.postgres.version", Mock(return_value="9.1")):
                with patch(
                    "salt.modules.postgres.user_exists", Mock(return_value=True)
                ):
                    postgres.user_remove(
                        "testuser",
                        user="testuser",
                        host="testhost",
                        port="testport",
                        maintenance_db="maint_db",
                        password="testpassword",
                        runas="foo",
                    )
                    postgres._run_psql.assert_called_once_with(
                        [
                            "/usr/bin/pgsql",
                            "--no-align",
                            "--no-readline",
                            "--no-psqlrc",
                            "--no-password",
                            "--username",
                            "testuser",
                            "--host",
                            "testhost",
                            "--port",
                            "testport",
                            "--dbname",
                            "maint_db",
                            "-c",
                            'DROP ROLE "testuser"',
                        ],
                        host="testhost",
                        port="testport",
                        user="testuser",
                        password="testpassword",
                        runas="foo",
                    )

    def test_user_update(self):
        with patch(
            "salt.modules.postgres._run_psql", Mock(return_value={"retcode": 0})
        ):
            with patch(
                "salt.modules.postgres.role_get",
                Mock(return_value={"superuser": False}),
            ):
                postgres.user_update(
                    "test_username",
                    user="test_user",
                    host="test_host",
                    port="test_port",
                    maintenance_db="test_maint",
                    password="test_pass",
                    createdb=False,
                    createroles=False,
                    encrypted=False,
                    inherit=True,
                    login=True,
                    replication=False,
                    rolepassword="test_role_pass",
                    valid_until="2017-07-01",
                    groups="test_groups",
                    runas="foo",
                )
                # postgres._run_psql.call_args[0][0] will contain the list of CLI args.
                # The first 14 elements of this list are initial args used in all (or
                # virtually all) commands run through _run_psql(), so the actual SQL
                # query will be in the 15th argument.
                self.assertTrue(
                    re.match(
                        'ALTER ROLE "test_username" WITH  INHERIT NOCREATEDB '
                        "NOCREATEROLE NOREPLICATION LOGIN "
                        "UNENCRYPTED PASSWORD ['\"]{0,5}test_role_pass['\"]{0,5} "
                        "VALID UNTIL '2017-07-01';"
                        ' GRANT "test_groups" TO "test_username"',
                        postgres._run_psql.call_args[0][0][14],
                    )
                )

    def test_user_update2(self):
        with patch(
            "salt.modules.postgres._run_psql", Mock(return_value={"retcode": 0})
        ):
            with patch(
                "salt.modules.postgres.role_get",
                Mock(return_value={"superuser": False}),
            ):
                postgres.user_update(
                    "test_username",
                    user="test_user",
                    host="test_host",
                    port="test_port",
                    maintenance_db="test_maint",
                    password="test_pass",
                    createdb=False,
                    createroles=True,
                    encrypted=False,
                    inherit=True,
                    login=True,
                    replication=False,
                    groups="test_groups",
                    runas="foo",
                )
                # postgres._run_psql.call_args[0][0] will contain the list of CLI args.
                # The first 14 elements of this list are initial args used in all (or
                # virtually all) commands run through _run_psql(), so the actual SQL
                # query will be in the 15th argument.
                self.assertTrue(
                    re.match(
                        'ALTER ROLE "test_username" WITH  INHERIT NOCREATEDB '
                        "CREATEROLE NOREPLICATION LOGIN;"
                        ' GRANT "test_groups" TO "test_username"',
                        postgres._run_psql.call_args[0][0][14],
                    )
                )

    def test_user_update3(self):
        with patch(
            "salt.modules.postgres._run_psql", Mock(return_value={"retcode": 0})
        ):
            with patch(
                "salt.modules.postgres.role_get",
                Mock(return_value={"superuser": False}),
            ):
                postgres.user_update(
                    "test_username",
                    user="test_user",
                    host="test_host",
                    port="test_port",
                    maintenance_db="test_maint",
                    password="test_pass",
                    createdb=False,
                    createroles=True,
                    encrypted=False,
                    inherit=True,
                    login=True,
                    rolepassword=False,
                    replication=False,
                    groups="test_groups",
                    runas="foo",
                )
                # postgres._run_psql.call_args[0][0] will contain the list of CLI args.
                # The first 14 elements of this list are initial args used in all (or
                # virtually all) commands run through _run_psql(), so the actual SQL
                # query will be in the 15th argument.
                self.assertTrue(
                    re.match(
                        'ALTER ROLE "test_username" WITH  INHERIT NOCREATEDB '
                        "CREATEROLE NOREPLICATION LOGIN NOPASSWORD;"
                        ' GRANT "test_groups" TO "test_username"',
                        postgres._run_psql.call_args[0][0][14],
                    )
                )

    def test_user_update_encrypted_passwd(self):
        with patch(
            "salt.modules.postgres._run_psql", Mock(return_value={"retcode": 0})
        ):
            with patch(
                "salt.modules.postgres.role_get",
                Mock(return_value={"superuser": False}),
            ):
                postgres.user_update(
                    "test_username",
                    user="test_user",
                    host="test_host",
                    port="test_port",
                    maintenance_db="test_maint",
                    password="test_pass",
                    createdb=False,
                    createroles=True,
                    encrypted=True,
                    inherit=True,
                    login=True,
                    rolepassword="foobar",
                    replication=False,
                    groups="test_groups",
                    runas="foo",
                )
                # postgres._run_psql.call_args[0][0] will contain the list of CLI args.
                # The first 14 elements of this list are initial args used in all (or
                # virtually all) commands run through _run_psql(), so the actual SQL
                # query will be in the 15th argument.
                self.assertTrue(
                    re.match(
                        'ALTER ROLE "test_username" WITH  INHERIT NOCREATEDB '
                        "CREATEROLE NOREPLICATION LOGIN "
                        "ENCRYPTED PASSWORD "
                        "['\"]{0,5}md531c27e68d3771c392b52102c01be1da1['\"]{0,5}"
                        '; GRANT "test_groups" TO "test_username"',
                        postgres._run_psql.call_args[0][0][14],
                    )
                )

    def test_version(self):
        with patch(
            "salt.modules.postgres._run_psql",
            Mock(return_value={"retcode": 0, "stdout": "9.1.9"}),
        ):
            postgres.version(
                user="test_user",
                host="test_host",
                port="test_port",
                maintenance_db="test_maint",
                password="test_pass",
                runas="foo",
            )
            # postgres._run_psql.call_args[0][0] will contain the list of CLI args.
            # The first 14 elements of this list are initial args used in all (or
            # virtually all) commands run through _run_psql(), so the actual SQL
            # query will be in the 15th argument.
            self.assertTrue(
                re.match(
                    "SELECT setting FROM pg_catalog.pg_settings",
                    postgres._run_psql.call_args[0][0][14],
                )
            )

    def test_installed_extensions(self):
        with patch(
            "salt.modules.postgres.psql_query",
            Mock(return_value=[{"extname": "foo", "extversion": "1"}]),
        ):
            exts = postgres.installed_extensions()
            self.assertEqual(exts, {"foo": {"extversion": "1", "extname": "foo"}})

    def test_available_extensions(self):
        with patch(
            "salt.modules.postgres.psql_query",
            Mock(return_value=[{"name": "foo", "default_version": "1"}]),
        ):
            exts = postgres.available_extensions()
            self.assertEqual(exts, {"foo": {"default_version": "1", "name": "foo"}})

    def test_drop_extension2(self):
        with patch(
            "salt.modules.postgres.installed_extensions", Mock(side_effect=[{}, {}])
        ):
            with patch(
                "salt.modules.postgres._psql_prepare_and_run", Mock(return_value=None)
            ):
                with patch(
                    "salt.modules.postgres.available_extensions",
                    Mock(return_value={"foo": {"default_version": "1", "name": "foo"}}),
                ):
                    self.assertEqual(postgres.drop_extension("foo"), True)

    def test_drop_extension3(self):
        with patch(
            "salt.modules.postgres.installed_extensions",
            Mock(side_effect=[{"foo": {"extversion": "1", "extname": "foo"}}, {}]),
        ):
            with patch(
                "salt.modules.postgres._psql_prepare_and_run", Mock(return_value=None)
            ):
                with patch(
                    "salt.modules.postgres.available_extensions",
                    Mock(return_value={"foo": {"default_version": "1", "name": "foo"}}),
                ):
                    self.assertEqual(postgres.drop_extension("foo"), True)

    def test_drop_extension1(self):
        with patch(
            "salt.modules.postgres.installed_extensions",
            Mock(
                side_effect=[
                    {"foo": {"extversion": "1", "extname": "foo"}},
                    {"foo": {"extversion": "1", "extname": "foo"}},
                ]
            ),
        ):
            with patch(
                "salt.modules.postgres._psql_prepare_and_run", Mock(return_value=None)
            ):
                with patch(
                    "salt.modules.postgres.available_extensions",
                    Mock(return_value={"foo": {"default_version": "1", "name": "foo"}}),
                ):
                    self.assertEqual(postgres.drop_extension("foo"), False)

    def test_create_mtdata(self):
        with patch(
            "salt.modules.postgres.installed_extensions",
            Mock(
                return_value={
                    "foo": {
                        "extversion": "0.8",
                        "extrelocatable": "t",
                        "schema_name": "foo",
                        "extname": "foo",
                    }
                },
            ),
        ):
            with patch(
                "salt.modules.postgres.available_extensions",
                Mock(return_value={"foo": {"default_version": "1.4", "name": "foo"}}),
            ):
                ret = postgres.create_metadata("foo", schema="bar", ext_version="1.4")
                self.assertTrue(postgres._EXTENSION_INSTALLED in ret)
                self.assertTrue(postgres._EXTENSION_TO_UPGRADE in ret)
                self.assertTrue(postgres._EXTENSION_TO_MOVE in ret)
                ret = postgres.create_metadata("foo", schema="foo", ext_version="0.4")
                self.assertTrue(postgres._EXTENSION_INSTALLED in ret)
                self.assertFalse(postgres._EXTENSION_TO_UPGRADE in ret)
                self.assertFalse(postgres._EXTENSION_TO_MOVE in ret)
                ret = postgres.create_metadata("foo")
                self.assertTrue(postgres._EXTENSION_INSTALLED in ret)
                self.assertFalse(postgres._EXTENSION_TO_UPGRADE in ret)
                self.assertFalse(postgres._EXTENSION_TO_MOVE in ret)
                ret = postgres.create_metadata("foobar")
                self.assertTrue(postgres._EXTENSION_NOT_INSTALLED in ret)
                self.assertFalse(postgres._EXTENSION_INSTALLED in ret)
                self.assertFalse(postgres._EXTENSION_TO_UPGRADE in ret)
                self.assertFalse(postgres._EXTENSION_TO_MOVE in ret)

    def test_create_extension_newerthan(self):
        """
        scenario of creating upgrading extensions with possible schema and
        version specifications
        """
        with patch(
            "salt.modules.postgres.create_metadata",
            Mock(
                side_effect=[
                    # create succeeded
                    [postgres._EXTENSION_NOT_INSTALLED],
                    [postgres._EXTENSION_INSTALLED],
                    [postgres._EXTENSION_NOT_INSTALLED],
                    [postgres._EXTENSION_INSTALLED],
                    # create failed
                    [postgres._EXTENSION_NOT_INSTALLED],
                    [postgres._EXTENSION_NOT_INSTALLED],
                    # move+upgrade succeeded
                    [
                        postgres._EXTENSION_TO_MOVE,
                        postgres._EXTENSION_TO_UPGRADE,
                        postgres._EXTENSION_INSTALLED,
                    ],
                    [postgres._EXTENSION_INSTALLED],
                    # move succeeded
                    [postgres._EXTENSION_TO_MOVE, postgres._EXTENSION_INSTALLED],
                    [postgres._EXTENSION_INSTALLED],
                    # upgrade succeeded
                    [postgres._EXTENSION_TO_UPGRADE, postgres._EXTENSION_INSTALLED],
                    [postgres._EXTENSION_INSTALLED],
                    # upgrade failed
                    [postgres._EXTENSION_TO_UPGRADE, postgres._EXTENSION_INSTALLED],
                    [postgres._EXTENSION_TO_UPGRADE, postgres._EXTENSION_INSTALLED],
                    # move failed
                    [postgres._EXTENSION_TO_MOVE, postgres._EXTENSION_INSTALLED],
                    [postgres._EXTENSION_TO_MOVE, postgres._EXTENSION_INSTALLED],
                ]
            ),
        ):
            with patch(
                "salt.modules.postgres._psql_prepare_and_run", Mock(return_value=None)
            ):
                with patch(
                    "salt.modules.postgres.available_extensions",
                    Mock(
                        return_value={"foo": {"default_version": "1.4", "name": "foo"}}
                    ),
                ):
                    self.assertTrue(postgres.create_extension("foo"))
                    self.assertTrue(
                        re.match(
                            'CREATE EXTENSION IF NOT EXISTS "foo" ;',
                            postgres._psql_prepare_and_run.call_args[0][0][1],
                        )
                    )
                    self.assertTrue(
                        postgres.create_extension(
                            "foo", schema="a", ext_version="b", from_version="c"
                        )
                    )
                    self.assertTrue(
                        re.match(
                            'CREATE EXTENSION IF NOT EXISTS "foo" '
                            'WITH SCHEMA "a" VERSION b FROM c ;',
                            postgres._psql_prepare_and_run.call_args[0][0][1],
                        )
                    )
                    self.assertFalse(postgres.create_extension("foo"))
                    ret = postgres.create_extension("foo", ext_version="a", schema="b")
                    self.assertTrue(ret)
                    self.assertTrue(
                        re.match(
                            'ALTER EXTENSION "foo" SET SCHEMA "b";'
                            ' ALTER EXTENSION "foo" UPDATE TO a;',
                            postgres._psql_prepare_and_run.call_args[0][0][1],
                        )
                    )
                    ret = postgres.create_extension("foo", ext_version="a", schema="b")
                    self.assertTrue(ret)
                    self.assertTrue(
                        re.match(
                            'ALTER EXTENSION "foo" SET SCHEMA "b";',
                            postgres._psql_prepare_and_run.call_args[0][0][1],
                        )
                    )
                    ret = postgres.create_extension("foo", ext_version="a", schema="b")
                    self.assertTrue(ret)
                    self.assertTrue(
                        re.match(
                            'ALTER EXTENSION "foo" UPDATE TO a;',
                            postgres._psql_prepare_and_run.call_args[0][0][1],
                        )
                    )
                    self.assertFalse(
                        postgres.create_extension("foo", ext_version="a", schema="b")
                    )
                    self.assertFalse(
                        postgres.create_extension("foo", ext_version="a", schema="b")
                    )

    def test_encrypt_passwords(self):
        self.assertEqual(postgres._maybe_encrypt_password("foo", "bar", False), "bar")
        self.assertEqual(
            postgres._maybe_encrypt_password("foo", "bar", True),
            "md596948aad3fcae80c08a35c9b5958cd89",
        )

    def test_schema_list(self):
        with patch(
            "salt.modules.postgres._run_psql",
            Mock(return_value={"retcode": 0, "stdout": test_list_schema_csv}),
        ):
            ret = postgres.schema_list(
                "maint_db",
                db_user="testuser",
                db_host="testhost",
                db_port="testport",
                db_password="foo",
            )
            self.assertDictEqual(
                ret,
                {
                    "public": {
                        "acl": "{postgres=UC/postgres,=UC/postgres}",
                        "owner": "postgres",
                    },
                    "pg_toast": {"acl": "", "owner": "postgres"},
                },
            )

    def test_schema_exists(self):
        with patch(
            "salt.modules.postgres._run_psql", Mock(return_value={"retcode": 0})
        ):
            with patch(
                "salt.modules.postgres.psql_query",
                Mock(
                    return_value=[
                        {
                            "name": "public",
                            "acl": "{postgres=UC/postgres,=UC/postgres}",
                            "owner": "postgres",
                        }
                    ]
                ),
            ):
                ret = postgres.schema_exists("template1", "public")
                self.assertTrue(ret)

    def test_schema_get(self):
        with patch(
            "salt.modules.postgres._run_psql", Mock(return_value={"retcode": 0})
        ):
            with patch(
                "salt.modules.postgres.psql_query",
                Mock(
                    return_value=[
                        {
                            "name": "public",
                            "acl": "{postgres=UC/postgres,=UC/postgres}",
                            "owner": "postgres",
                        }
                    ]
                ),
            ):
                ret = postgres.schema_get("template1", "public")
                self.assertTrue(ret)

    def test_schema_get_again(self):
        with patch(
            "salt.modules.postgres._run_psql", Mock(return_value={"retcode": 0})
        ):
            with patch(
                "salt.modules.postgres.psql_query",
                Mock(
                    return_value=[
                        {
                            "name": "public",
                            "acl": "{postgres=UC/postgres,=UC/postgres}",
                            "owner": "postgres",
                        }
                    ]
                ),
            ):
                ret = postgres.schema_get("template1", "pg_toast")
                self.assertFalse(ret)

    def test_schema_create(self):
        with patch(
            "salt.modules.postgres._run_psql", Mock(return_value={"retcode": 0})
        ):
            with patch("salt.modules.postgres.schema_exists", Mock(return_value=False)):
                postgres.schema_create(
                    "maint_db",
                    "testschema",
                    user="user",
                    db_host="testhost",
                    db_port="testport",
                    db_user="testuser",
                    db_password="testpassword",
                )
                postgres._run_psql.assert_called_once_with(
                    [
                        "/usr/bin/pgsql",
                        "--no-align",
                        "--no-readline",
                        "--no-psqlrc",
                        "--no-password",
                        "--username",
                        "testuser",
                        "--host",
                        "testhost",
                        "--port",
                        "testport",
                        "--dbname",
                        "maint_db",
                        "-c",
                        'CREATE SCHEMA "testschema"',
                    ],
                    host="testhost",
                    port="testport",
                    password="testpassword",
                    user="testuser",
                    runas="user",
                )

    def test_schema_create2(self):
        with patch("salt.modules.postgres.schema_exists", Mock(return_value=True)):
            ret = postgres.schema_create(
                "test_db",
                "test_schema",
                user="user",
                db_host="test_host",
                db_port="test_port",
                db_user="test_user",
                db_password="test_password",
            )
            self.assertFalse(ret)

    def test_schema_remove(self):
        with patch(
            "salt.modules.postgres._run_psql", Mock(return_value={"retcode": 0})
        ):
            with patch("salt.modules.postgres.schema_exists", Mock(return_value=True)):
                postgres.schema_remove(
                    "maint_db",
                    "testschema",
                    user="user",
                    db_host="testhost",
                    db_port="testport",
                    db_user="testuser",
                    db_password="testpassword",
                )
                postgres._run_psql.assert_called_once_with(
                    [
                        "/usr/bin/pgsql",
                        "--no-align",
                        "--no-readline",
                        "--no-psqlrc",
                        "--no-password",
                        "--username",
                        "testuser",
                        "--host",
                        "testhost",
                        "--port",
                        "testport",
                        "--dbname",
                        "maint_db",
                        "-c",
                        'DROP SCHEMA "testschema"',
                    ],
                    host="testhost",
                    port="testport",
                    password="testpassword",
                    user="testuser",
                    runas="user",
                )

    def test_schema_remove2(self):
        with patch("salt.modules.postgres.schema_exists", Mock(return_value=False)):
            ret = postgres.schema_remove(
                "test_db",
                "test_schema",
                user="user",
                db_host="test_host",
                db_port="test_port",
                db_user="test_user",
                db_password="test_password",
            )
            self.assertFalse(ret)

    def test_language_list(self):
        """
        Test language listing
        """
        with patch(
            "salt.modules.postgres._run_psql",
            Mock(return_value={"retcode": 0, "stdout": test_list_language_csv}),
        ):
            ret = postgres.language_list(
                "testdb",
                user="testuser",
                host="testhost",
                port="testport",
                password="foo",
            )
            self.assertDictEqual(
                ret,
                {"c": "c", "internal": "internal", "plpgsql": "plpgsql", "sql": "sql"},
            )

    def test_language_exists(self):
        """
        Test language existence check
        """
        with patch(
            "salt.modules.postgres._run_psql", Mock(return_value={"retcode": 0})
        ):
            with patch(
                "salt.modules.postgres.psql_query",
                Mock(
                    return_value=[
                        {"Name": "internal"},
                        {"Name": "c"},
                        {"Name": "sql"},
                        {"Name": "plpgsql"},
                    ]
                ),
            ):
                with patch(
                    "salt.modules.postgres.language_exists", Mock(return_value=True)
                ):
                    ret = postgres.language_exists("sql", "testdb")
                    self.assertTrue(ret)

    def test_language_create(self):
        """
        Test language creation - does not exist in db
        """
        with patch(
            "salt.modules.postgres._run_psql", Mock(return_value={"retcode": 0})
        ):
            with patch(
                "salt.modules.postgres.language_exists", Mock(return_value=False)
            ):
                postgres.language_create(
                    "plpythonu",
                    "testdb",
                    runas="user",
                    host="testhost",
                    port="testport",
                    user="testuser",
                    password="testpassword",
                )
                postgres._run_psql.assert_called_once_with(
                    [
                        "/usr/bin/pgsql",
                        "--no-align",
                        "--no-readline",
                        "--no-psqlrc",
                        "--no-password",
                        "--username",
                        "testuser",
                        "--host",
                        "testhost",
                        "--port",
                        "testport",
                        "--dbname",
                        "testdb",
                        "-c",
                        "CREATE LANGUAGE plpythonu",
                    ],
                    host="testhost",
                    port="testport",
                    password="testpassword",
                    user="testuser",
                    runas="user",
                )

    def test_language_create_exists(self):
        """
        Test language creation - already exists in db
        """
        with patch("salt.modules.postgres.language_exists", Mock(return_value=True)):
            ret = postgres.language_create(
                "plpythonu",
                "testdb",
                runas="user",
                host="testhost",
                port="testport",
                user="testuser",
                password="testpassword",
            )
            self.assertFalse(ret)

    def test_language_remove(self):
        """
        Test language removal - exists in db
        """
        with patch(
            "salt.modules.postgres._run_psql", Mock(return_value={"retcode": 0})
        ):
            with patch(
                "salt.modules.postgres.language_exists", Mock(return_value=True)
            ):
                postgres.language_remove(
                    "plpgsql",
                    "testdb",
                    runas="user",
                    host="testhost",
                    port="testport",
                    user="testuser",
                    password="testpassword",
                )
                postgres._run_psql.assert_called_once_with(
                    [
                        "/usr/bin/pgsql",
                        "--no-align",
                        "--no-readline",
                        "--no-psqlrc",
                        "--no-password",
                        "--username",
                        "testuser",
                        "--host",
                        "testhost",
                        "--port",
                        "testport",
                        "--dbname",
                        "testdb",
                        "-c",
                        "DROP LANGUAGE plpgsql",
                    ],
                    host="testhost",
                    port="testport",
                    password="testpassword",
                    user="testuser",
                    runas="user",
                )

    def test_language_remove_non_exist(self):
        """
        Test language removal - does not exist in db
        """
        with patch("salt.modules.postgres.language_exists", Mock(return_value=False)):
            ret = postgres.language_remove(
                "plpgsql",
                "testdb",
                runas="user",
                host="testhost",
                port="testport",
                user="testuser",
                password="testpassword",
            )
            self.assertFalse(ret)

    def test_privileges_list_table(self):
        """
        Test privilege listing on a table
        """
        with patch(
            "salt.modules.postgres._run_psql",
            Mock(return_value={"retcode": 0, "stdout": test_privileges_list_table_csv}),
        ):
            ret = postgres.privileges_list(
                "awl",
                "table",
                maintenance_db="db_name",
                runas="user",
                host="testhost",
                port="testport",
                user="testuser",
                password="testpassword",
            )
            expected = {
                "bayestest": {
                    "INSERT": False,
                    "UPDATE": False,
                    "SELECT": False,
                    "DELETE": False,
                },
                "baruwa": {
                    "INSERT": True,
                    "TRUNCATE": True,
                    "UPDATE": True,
                    "TRIGGER": True,
                    "REFERENCES": True,
                    "SELECT": True,
                    "DELETE": True,
                },
                "baruwatest": {
                    "INSERT": False,
                    "TRUNCATE": False,
                    "UPDATE": False,
                    "TRIGGER": False,
                    "REFERENCES": False,
                    "SELECT": False,
                    "DELETE": False,
                },
            }

            self.assertDictEqual(ret, expected)

            query = (
                "COPY (SELECT relacl AS name FROM pg_catalog.pg_class c "
                "JOIN pg_catalog.pg_namespace n ON n.oid = c.relnamespace "
                "WHERE nspname = 'public' AND relname = 'awl' AND relkind = 'r' "
                "ORDER BY relname) TO STDOUT WITH CSV HEADER"
            )

            postgres._run_psql.assert_called_once_with(
                [
                    "/usr/bin/pgsql",
                    "--no-align",
                    "--no-readline",
                    "--no-psqlrc",
                    "--no-password",
                    "--username",
                    "testuser",
                    "--host",
                    "testhost",
                    "--port",
                    "testport",
                    "--dbname",
                    "db_name",
                    "-v",
                    "datestyle=ISO,MDY",
                    "-c",
                    query,
                ],
                host="testhost",
                port="testport",
                password="testpassword",
                user="testuser",
                runas="user",
            )

    def test_privileges_list_group(self):
        """
        Test privilege listing on a group
        """
        with patch(
            "salt.modules.postgres._run_psql",
            Mock(return_value={"retcode": 0, "stdout": test_privileges_list_group_csv}),
        ):
            ret = postgres.privileges_list(
                "admin",
                "group",
                maintenance_db="db_name",
                runas="user",
                host="testhost",
                port="testport",
                user="testuser",
                password="testpassword",
            )
            expected = {
                "baruwa": False,
                "baruwatest": False,
                "baruwatest2": True,
            }

            self.assertDictEqual(ret, expected)

            query = (
                "COPY (SELECT rolname, admin_option "
                "FROM pg_catalog.pg_auth_members m JOIN pg_catalog.pg_roles r "
                "ON m.member=r.oid WHERE m.roleid IN (SELECT oid FROM "
                "pg_catalog.pg_roles WHERE rolname='admin') ORDER BY rolname) "
                "TO STDOUT WITH CSV HEADER"
            )

            postgres._run_psql.assert_called_once_with(
                [
                    "/usr/bin/pgsql",
                    "--no-align",
                    "--no-readline",
                    "--no-psqlrc",
                    "--no-password",
                    "--username",
                    "testuser",
                    "--host",
                    "testhost",
                    "--port",
                    "testport",
                    "--dbname",
                    "db_name",
                    "-v",
                    "datestyle=ISO,MDY",
                    "-c",
                    query,
                ],
                host="testhost",
                port="testport",
                password="testpassword",
                user="testuser",
                runas="user",
            )

    def test_has_privileges_on_table(self):
        """
        Test privilege checks on table
        """
        with patch(
            "salt.modules.postgres._run_psql",
            Mock(return_value={"retcode": 0, "stdout": test_privileges_list_table_csv}),
        ):
            ret = postgres.has_privileges(
                "baruwa",
                "awl",
                "table",
                "SELECT,INSERT",
                grant_option=True,
                maintenance_db="db_name",
                runas="user",
                host="testhost",
                port="testport",
                user="testuser",
                password="testpassword",
            )

            self.assertTrue(ret)

            ret = postgres.has_privileges(
                "baruwa",
                "awl",
                "table",
                "ALL",
                grant_option=True,
                maintenance_db="db_name",
                runas="user",
                host="testhost",
                port="testport",
                user="testuser",
                password="testpassword",
            )

            self.assertTrue(ret)

            ret = postgres.has_privileges(
                "baruwa",
                "awl",
                "table",
                "ALL",
                grant_option=False,
                maintenance_db="db_name",
                runas="user",
                host="testhost",
                port="testport",
                user="testuser",
                password="testpassword",
            )

            self.assertTrue(ret)

            ret = postgres.has_privileges(
                "bayestest",
                "awl",
                "table",
                "SELECT,INSERT,TRUNCATE",
                maintenance_db="db_name",
                runas="user",
                host="testhost",
                port="testport",
                user="testuser",
                password="testpassword",
            )

            self.assertFalse(ret)

            ret = postgres.has_privileges(
                "bayestest",
                "awl",
                "table",
                "SELECT,INSERT",
                maintenance_db="db_name",
                runas="user",
                host="testhost",
                port="testport",
                user="testuser",
                password="testpassword",
            )

            self.assertTrue(ret)

    def test_has_privileges_on_group(self):
        """
        Test privilege checks on group
        """
        with patch(
            "salt.modules.postgres._run_psql",
            Mock(return_value={"retcode": 0, "stdout": test_privileges_list_group_csv}),
        ):
            ret = postgres.has_privileges(
                "baruwa",
                "admin",
                "group",
                maintenance_db="db_name",
                runas="user",
                host="testhost",
                port="testport",
                user="testuser",
                password="testpassword",
            )

            self.assertTrue(ret)

            ret = postgres.has_privileges(
                "baruwa",
                "admin",
                "group",
                grant_option=True,
                maintenance_db="db_name",
                runas="user",
                host="testhost",
                port="testport",
                user="testuser",
                password="testpassword",
            )

            self.assertFalse(ret)

            ret = postgres.has_privileges(
                "tony",
                "admin",
                "group",
                maintenance_db="db_name",
                runas="user",
                host="testhost",
                port="testport",
                user="testuser",
                password="testpassword",
            )

            self.assertFalse(ret)

    def test_privileges_grant_table(self):
        """
        Test granting privileges on table
        """
        with patch(
            "salt.modules.postgres._run_psql", Mock(return_value={"retcode": 0})
        ):
            with patch(
                "salt.modules.postgres.has_privileges", Mock(return_value=False)
            ):
                ret = postgres.privileges_grant(
                    "baruwa",
                    "awl",
                    "table",
                    "ALL",
                    grant_option=True,
                    maintenance_db="db_name",
                    runas="user",
                    host="testhost",
                    port="testport",
                    user="testuser",
                    password="testpassword",
                )

                query = 'GRANT ALL ON TABLE public."awl" TO "baruwa" WITH GRANT OPTION'

                postgres._run_psql.assert_called_once_with(
                    [
                        "/usr/bin/pgsql",
                        "--no-align",
                        "--no-readline",
                        "--no-psqlrc",
                        "--no-password",
                        "--username",
                        "testuser",
                        "--host",
                        "testhost",
                        "--port",
                        "testport",
                        "--dbname",
                        "db_name",
                        "-c",
                        query,
                    ],
                    host="testhost",
                    port="testport",
                    password="testpassword",
                    user="testuser",
                    runas="user",
                )

        with patch(
            "salt.modules.postgres._run_psql", Mock(return_value={"retcode": 0})
        ):
            with patch(
                "salt.modules.postgres.has_privileges", Mock(return_value=False)
            ):
                ret = postgres.privileges_grant(
                    "baruwa",
                    "awl",
                    "table",
                    "ALL",
                    maintenance_db="db_name",
                    runas="user",
                    host="testhost",
                    port="testport",
                    user="testuser",
                    password="testpassword",
                )

                query = 'GRANT ALL ON TABLE public."awl" TO "baruwa"'

                postgres._run_psql.assert_called_once_with(
                    [
                        "/usr/bin/pgsql",
                        "--no-align",
                        "--no-readline",
                        "--no-psqlrc",
                        "--no-password",
                        "--username",
                        "testuser",
                        "--host",
                        "testhost",
                        "--port",
                        "testport",
                        "--dbname",
                        "db_name",
                        "-c",
                        query,
                    ],
                    host="testhost",
                    port="testport",
                    password="testpassword",
                    user="testuser",
                    runas="user",
                )

        # Test grant on all tables
        with patch(
            "salt.modules.postgres._run_psql", Mock(return_value={"retcode": 0})
        ):
            with patch(
                "salt.modules.postgres.has_privileges", Mock(return_value=False)
            ):
                ret = postgres.privileges_grant(
                    "baruwa",
                    "ALL",
                    "table",
                    "SELECT",
                    maintenance_db="db_name",
                    runas="user",
                    host="testhost",
                    port="testport",
                    user="testuser",
                    password="testpassword",
                )

                query = 'GRANT SELECT ON ALL TABLES IN SCHEMA public TO "baruwa"'

                postgres._run_psql.assert_called_once_with(
                    [
                        "/usr/bin/pgsql",
                        "--no-align",
                        "--no-readline",
                        "--no-psqlrc",
                        "--no-password",
                        "--username",
                        "testuser",
                        "--host",
                        "testhost",
                        "--port",
                        "testport",
                        "--dbname",
                        "db_name",
                        "-c",
                        query,
                    ],
                    host="testhost",
                    port="testport",
                    password="testpassword",
                    user="testuser",
                    runas="user",
                )

    def test_privileges_grant_group(self):
        """
        Test granting privileges on group
        """
        with patch(
            "salt.modules.postgres._run_psql", Mock(return_value={"retcode": 0})
        ):
            with patch(
                "salt.modules.postgres.has_privileges", Mock(return_value=False)
            ):
                ret = postgres.privileges_grant(
                    "baruwa",
                    "admins",
                    "group",
                    grant_option=True,
                    maintenance_db="db_name",
                    runas="user",
                    host="testhost",
                    port="testport",
                    user="testuser",
                    password="testpassword",
                )

                query = 'GRANT admins TO "baruwa" WITH ADMIN OPTION'

                postgres._run_psql.assert_called_once_with(
                    [
                        "/usr/bin/pgsql",
                        "--no-align",
                        "--no-readline",
                        "--no-psqlrc",
                        "--no-password",
                        "--username",
                        "testuser",
                        "--host",
                        "testhost",
                        "--port",
                        "testport",
                        "--dbname",
                        "db_name",
                        "-c",
                        query,
                    ],
                    host="testhost",
                    port="testport",
                    password="testpassword",
                    user="testuser",
                    runas="user",
                )

        with patch(
            "salt.modules.postgres._run_psql", Mock(return_value={"retcode": 0})
        ):
            with patch(
                "salt.modules.postgres.has_privileges", Mock(return_value=False)
            ):
                ret = postgres.privileges_grant(
                    "baruwa",
                    "admins",
                    "group",
                    maintenance_db="db_name",
                    runas="user",
                    host="testhost",
                    port="testport",
                    user="testuser",
                    password="testpassword",
                )

                query = 'GRANT admins TO "baruwa"'

                postgres._run_psql.assert_called_once_with(
                    [
                        "/usr/bin/pgsql",
                        "--no-align",
                        "--no-readline",
                        "--no-psqlrc",
                        "--no-password",
                        "--username",
                        "testuser",
                        "--host",
                        "testhost",
                        "--port",
                        "testport",
                        "--dbname",
                        "db_name",
                        "-c",
                        query,
                    ],
                    host="testhost",
                    port="testport",
                    password="testpassword",
                    user="testuser",
                    runas="user",
                )

    def test_privileges_revoke_table(self):
        """
        Test revoking privileges on table
        """
        with patch(
            "salt.modules.postgres._run_psql", Mock(return_value={"retcode": 0})
        ):
            with patch("salt.modules.postgres.has_privileges", Mock(return_value=True)):
                ret = postgres.privileges_revoke(
                    "baruwa",
                    "awl",
                    "table",
                    "ALL",
                    maintenance_db="db_name",
                    runas="user",
                    host="testhost",
                    port="testport",
                    user="testuser",
                    password="testpassword",
                )

                query = "REVOKE ALL ON TABLE public.awl FROM baruwa"

                postgres._run_psql.assert_called_once_with(
                    [
                        "/usr/bin/pgsql",
                        "--no-align",
                        "--no-readline",
                        "--no-psqlrc",
                        "--no-password",
                        "--username",
                        "testuser",
                        "--host",
                        "testhost",
                        "--port",
                        "testport",
                        "--dbname",
                        "db_name",
                        "-c",
                        query,
                    ],
                    host="testhost",
                    port="testport",
                    password="testpassword",
                    user="testuser",
                    runas="user",
                )

    def test_privileges_revoke_group(self):
        """
        Test revoking privileges on group
        """
        with patch(
            "salt.modules.postgres._run_psql", Mock(return_value={"retcode": 0})
        ):
            with patch("salt.modules.postgres.has_privileges", Mock(return_value=True)):
                ret = postgres.privileges_revoke(
                    "baruwa",
                    "admins",
                    "group",
                    maintenance_db="db_name",
                    runas="user",
                    host="testhost",
                    port="testport",
                    user="testuser",
                    password="testpassword",
                )

                query = "REVOKE admins FROM baruwa"

                postgres._run_psql.assert_called_once_with(
                    [
                        "/usr/bin/pgsql",
                        "--no-align",
                        "--no-readline",
                        "--no-psqlrc",
                        "--no-password",
                        "--username",
                        "testuser",
                        "--host",
                        "testhost",
                        "--port",
                        "testport",
                        "--dbname",
                        "db_name",
                        "-c",
                        query,
                    ],
                    host="testhost",
                    port="testport",
                    password="testpassword",
                    user="testuser",
                    runas="user",
                )

    def test_datadir_init(self):
        """
        Test Initializing a postgres data directory
        """
        with patch(
            "salt.modules.postgres._run_initdb", Mock(return_value={"retcode": 0})
        ):
            with patch(
                "salt.modules.postgres.datadir_exists", Mock(return_value=False)
            ):
                name = "/var/lib/pgsql/data"
                ret = postgres.datadir_init(
                    name, user="postgres", password="test", runas="postgres"
                )
                postgres._run_initdb.assert_called_once_with(
                    name,
                    auth="password",
                    encoding="UTF8",
                    locale=None,
                    password="test",
                    runas="postgres",
                    checksums=False,
                    waldir=None,
                    user="postgres",
                )
                self.assertTrue(ret)

    def test_datadir_exists(self):
        """
        Test Checks if postgres data directory has been initialized
        """
        with patch("os.path.isfile", Mock(return_value=True)):
            name = "/var/lib/pgsql/data"
            ret = postgres.datadir_exists(name)
            self.assertTrue(ret)

    def test_pg_is_older_ext_ver(self):
        """
        Test Checks if postgres extension version string is older
        """
        self.assertTrue(postgres._pg_is_older_ext_ver("8.5", "9.5"))
        self.assertTrue(postgres._pg_is_older_ext_ver("8.5", "8.6"))
        self.assertTrue(postgres._pg_is_older_ext_ver("8.5.2", "8.5.3"))
        self.assertFalse(postgres._pg_is_older_ext_ver("9.5", "8.5"))
        self.assertTrue(postgres._pg_is_older_ext_ver("9.5", "9.6"))
        self.assertTrue(postgres._pg_is_older_ext_ver("9.5.0", "9.5.1"))
        self.assertTrue(postgres._pg_is_older_ext_ver("9.5", "9.5.1"))
        self.assertFalse(postgres._pg_is_older_ext_ver("9.5.1", "9.5"))
        self.assertFalse(postgres._pg_is_older_ext_ver("9.5b", "9.5a"))
        self.assertTrue(postgres._pg_is_older_ext_ver("10a", "10b"))
        self.assertTrue(postgres._pg_is_older_ext_ver("1.2.3.4", "1.2.3.5"))
        self.assertTrue(postgres._pg_is_older_ext_ver("10dev", "10next"))
        self.assertFalse(postgres._pg_is_older_ext_ver("10next", "10dev"))
