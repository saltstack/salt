import datetime
import re

import pytest
from pytestskipmarkers.utils import platform

import salt.modules.config as configmod
import salt.modules.postgres as postgres
from salt.exceptions import SaltInvocationError
from tests.support.mock import MagicMock, Mock, call, patch

pytestmark = [
    pytest.mark.skip_unless_on_linux(reason="Only supported on Linux family"),
]


# 'md5' + md5('password' + 'username')
md5_pw = "md55a231fcdb710d73268c4f44283487ba2"

scram_pw = (
    "SCRAM-SHA-256$4096:wLr5nqC+3F+r7FdQPnB+nA==$"
    "0hn08ZdX8kirGaL4TM0j13digH9Wl365OOzCtAuF2pE=:"
    "LzAh/MGUdjYkdbDzcOKpfGwa3WwPUsyGcY+TEnSpcto="
)


@pytest.fixture
def get_test_privileges_list_function_csv():
    return """name
"{baruwatest=X/baruwatest,bayestest=r/baruwatest,baruwa=X*/baruwatest}"
"""


@pytest.fixture
def get_test_list_db_csv():
    return """Name,Owner,Encoding,Collate,Ctype,Access privileges,Tablespace
template1,postgres,LATIN1,en_US,en_US,"{=c/postgres,postgres=CTc/postgres}",pg_default
template0,postgres,LATIN1,en_US,en_US,"{=c/postgres,postgres=CTc/postgres}",pg_default
postgres,postgres,LATIN1,en_US,en_US,,pg_default
test_db,postgres,LATIN1,en_US,en_US,,pg_default
"""


@pytest.fixture
def get_test_list_schema_csv():
    return """name,owner,acl
public,postgres,"{postgres=UC/postgres,=UC/postgres}"
pg_toast,postgres,""
"""


@pytest.fixture
def get_test_list_language_csv():
    return "Name\ninternal\nc\nsql\nplpgsql\n"


@pytest.fixture
def get_test_privileges_list_table_csv():
    return """name
"{baruwatest=arwdDxt/baruwatest,bayestest=arwd/baruwatest,baruwa=a*r*w*d*D*x*t*/baruwatest}"
"""


@pytest.fixture
def get_test_privileges_list_group_csv():
    return "rolname,admin_option\nbaruwa,f\nbaruwatest2,t\nbaruwatest,f\n"


@pytest.fixture
def configure_loader_modules():
    return {
        postgres: {
            "__grains__": {"os_family": "Linux"},
            "__salt__": {
                "config.option": MagicMock(),
                "cmd.run_all": MagicMock(),
                "file.chown": MagicMock(),
                "file.remove": MagicMock(),
            },
        },
        configmod: {},
    }


def idfn(val):
    if val == md5_pw:
        return "md5_pw"
    if val == scram_pw:
        return "scram_pw"


@pytest.mark.parametrize(
    "role,password,verifier,method,result",
    [
        ("username", "password", md5_pw, "md5", True),
        ("another", "password", md5_pw, "md5", False),
        ("username", "another", md5_pw, "md5", False),
        ("username", md5_pw, md5_pw, "md5", True),
        ("username", "md5another", md5_pw, "md5", False),
        ("username", "password", md5_pw, True, True),
        ("another", "password", md5_pw, True, False),
        ("username", "another", md5_pw, True, False),
        ("username", md5_pw, md5_pw, True, True),
        ("username", "md5another", md5_pw, True, False),
        (None, "password", scram_pw, "scram-sha-256", True),
        (None, "another", scram_pw, "scram-sha-256", False),
        (None, scram_pw, scram_pw, "scram-sha-256", True),
        (None, "SCRAM-SHA-256$4096:AAAA$AAAA:AAAA", scram_pw, "scram-sha-256", False),
        (None, "SCRAM-SHA-256$foo", scram_pw, "scram-sha-256", False),
        (None, "password", "password", False, True),
        (None, "another", "password", False, False),
        (None, "password", "password", "foo", False),
        ("username", "password", md5_pw, "scram-sha-256", False),
        ("username", "password", scram_pw, "md5", False),
        # Code does not currently check role of pre-hashed md5 passwords
        pytest.param("another", md5_pw, md5_pw, "md5", False, marks=pytest.mark.xfail),
    ],
    ids=idfn,
)
def test_verify_password(role, password, verifier, method, result):
    if platform.is_fips_enabled() and (method == "md5" or verifier == md5_pw):
        pytest.skip("Test cannot run on a FIPS enabled platform")
    assert postgres._verify_password(role, password, verifier, method) == result


def test_has_privileges_with_function(get_test_privileges_list_function_csv):
    with patch(
        "salt.modules.postgres._run_psql",
        MagicMock(
            return_value={"retcode": 0, "stdout": get_test_privileges_list_function_csv}
        ),
    ), patch("salt.utils.path.which", MagicMock(return_value="/usr/bin/pgsql")):
        ret = postgres.has_privileges(
            "baruwa",
            "awl",
            "function",
            "EXECUTE",
            grant_option=True,
            maintenance_db="db_name",
            runas="user",
            host="testhost",
            port="testport",
            user="testuser",
            password="testpassword",
        )

        assert ret is True

        query = (
            "COPY (SELECT rolname AS name "
            "FROM pg_catalog.pg_proc p "
            "JOIN pg_catalog.pg_namespace n "
            "ON n.oid = p.pronamespace "
            "JOIN pg_catalog.pg_roles r "
            "ON p.proowner = r.oid "
            "WHERE nspname = 'public' "
            "AND p.oid::regprocedure::text = 'awl' "
            "ORDER BY proname, proargtypes) TO STDOUT WITH CSV HEADER"
        )

        postgres._run_psql.assert_any_call(
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


def test__runpsql_with_timeout():
    cmd_run_mock = MagicMock()
    postgres_opts = {
        "config.option": configmod.option,
        "cmd.run_all": cmd_run_mock,
    }
    kwargs = {
        "reset_system_locale": False,
        "clean_env": True,
        "runas": "saltuser",
        "python_shell": False,
    }
    with patch.dict(postgres.__salt__, postgres_opts):
        with patch.dict(
            configmod.__opts__, {"postgres.timeout": 60, "postgres.pass": None}
        ):
            postgres._run_psql("fakecmd", runas="saltuser")
            cmd_run_mock.assert_called_with("fakecmd", timeout=60, **kwargs)
        with patch.dict(configmod.__opts__, {"postgres.pass": None}):
            postgres._run_psql("fakecmd", runas="saltuser")
            cmd_run_mock.assert_called_with("fakecmd", timeout=0, **kwargs)


def test__run_initdb_with_timeout():
    cmd_run_mock = MagicMock(return_value={})
    postgres_opts = {
        "config.option": configmod.option,
        "cmd.run_all": cmd_run_mock,
    }
    kwargs = {
        "clean_env": True,
        "runas": "saltuser",
        "python_shell": False,
    }
    cmd_str = "/fake/path --pgdata=fakename --username=saltuser --auth=password --encoding=UTF8"
    with patch.dict(postgres.__salt__, postgres_opts):
        with patch.object(postgres, "_find_pg_binary", return_value="/fake/path"):
            with patch.dict(
                configmod.__opts__, {"postgres.timeout": 60, "postgres.pass": None}
            ):
                postgres._run_initdb("fakename", runas="saltuser")
                cmd_run_mock.assert_called_with(cmd_str, timeout=60, **kwargs)
            with patch.dict(configmod.__opts__, {"postgres.pass": None}):
                postgres._run_initdb("fakename", runas="saltuser")
                cmd_run_mock.assert_called_with(cmd_str, timeout=0, **kwargs)


def test_run_psql():
    postgres._run_psql('echo "hi"')
    cmd = postgres.__salt__["cmd.run_all"]
    assert cmd.call_args[1]["runas"] == "postgres"


def test_db_alter():
    with patch(
        "salt.modules.postgres._run_psql", Mock(return_value={"retcode": 0})
    ), patch("salt.utils.path.which", MagicMock(return_value="/usr/bin/pgsql")):
        ret = postgres.db_alter(
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
        assert ret is True

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


def test_db_alter_owner_recurse():
    with patch(
        "salt.modules.postgres.owner_to", Mock(return_value={"retcode": None})
    ), patch("salt.utils.path.which", MagicMock(return_value="/usr/bin/pgsql")):
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


def test_db_create():
    with patch(
        "salt.modules.postgres._run_psql", Mock(return_value={"retcode": 0})
    ), patch("salt.utils.path.which", MagicMock(return_value="/usr/bin/pgsql")):
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


def test_db_create_empty_string_param():
    with patch(
        "salt.modules.postgres._run_psql", Mock(return_value={"retcode": 0})
    ), patch("salt.utils.path.which", MagicMock(return_value="/usr/bin/pgsql")):
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


def test_db_create_with_trivial_sql_injection():
    with patch(
        "salt.modules.postgres._run_psql", Mock(return_value={"retcode": 0})
    ), patch("salt.utils.path.which", MagicMock(return_value="/usr/bin/pgsql")):
        pytest.raises(
            SaltInvocationError,
            postgres.db_create,
            "dbname",
            lc_collate="foo' ENCODING='utf8",
        )


def test_db_exists(get_test_list_db_csv):
    with patch(
        "salt.modules.postgres._run_psql",
        Mock(return_value={"retcode": 0, "stdout": get_test_list_db_csv}),
    ), patch("salt.utils.path.which", MagicMock(return_value="/usr/bin/pgsql")):
        ret = postgres.db_exists(
            "test_db",
            user="testuser",
            host="testhost",
            port="testport",
            maintenance_db="maint_db",
            password="foo",
            runas="foo",
        )
        assert ret is True


def test_db_list(get_test_list_db_csv):
    with patch(
        "salt.modules.postgres._run_psql",
        Mock(return_value={"retcode": 0, "stdout": get_test_list_db_csv}),
    ), patch("salt.utils.path.which", MagicMock(return_value="/usr/bin/pgsql")):
        ret = postgres.db_list(
            user="testuser",
            host="testhost",
            port="testport",
            maintenance_db="maint_db",
            password="foo",
            runas="foo",
        )
        assert ret == {
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
        }


def test_db_remove():
    with patch(
        "salt.modules.postgres._run_psql", Mock(return_value={"retcode": 0})
    ), patch("salt.utils.path.which", MagicMock(return_value="/usr/bin/pgsql")):
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


def test_group_create():
    with patch(
        "salt.modules.postgres._run_psql", Mock(return_value={"retcode": 0})
    ), patch("salt.utils.path.which", MagicMock(return_value="/usr/bin/pgsql")), patch(
        "salt.modules.postgres.user_exists", Mock(return_value=False)
    ):
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
        assert postgres._run_psql.call_args[0][0][14].startswith("CREATE ROLE")


def test_group_remove():
    with patch(
        "salt.modules.postgres._run_psql", Mock(return_value={"retcode": 0})
    ), patch("salt.utils.path.which", MagicMock(return_value="/usr/bin/pgsql")), patch(
        "salt.modules.postgres.user_exists", Mock(return_value=True)
    ):
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


def test_group_update():
    with patch(
        "salt.modules.postgres._run_psql", Mock(return_value={"retcode": 0})
    ), patch(
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
        assert re.match(
            'ALTER.* "testgroup" .* UNENCRYPTED PASSWORD',
            postgres._run_psql.call_args[0][0][14],
        )


def test_user_create():
    with patch(
        "salt.modules.postgres._run_psql", Mock(return_value={"retcode": 0})
    ), patch("salt.modules.postgres.user_exists", Mock(return_value=False)):
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
        assert re.match('CREATE ROLE "testuser"', call)
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
            assert i in call, f"{i} not in {call}"


def test_user_exists():
    with patch(
        "salt.modules.postgres._run_psql", Mock(return_value={"retcode": 0})
    ), patch("salt.modules.postgres.version", Mock(return_value="9.1")), patch(
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
        assert ret is True


def test_user_list():
    with patch(
        "salt.modules.postgres._run_psql", Mock(return_value={"retcode": 0})
    ), patch("salt.modules.postgres.version", Mock(return_value="9.1")), patch(
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

        assert ret == {
            "test_user": {
                "superuser": True,
                "defaults variables": None,
                "can create databases": True,
                "can create roles": True,
                "connections": None,
                "replication": None,
                "expiry time": datetime.datetime(2017, 8, 16, 8, 57, 46),
                "can login": True,
                "can update system catalogs": True,
                "groups": [],
                "inherits privileges": True,
            }
        }


def test_user_remove():
    with patch(
        "salt.modules.postgres._run_psql", Mock(return_value={"retcode": 0})
    ), patch("salt.utils.path.which", MagicMock(return_value="/usr/bin/pgsql")), patch(
        "salt.modules.postgres.version", Mock(return_value="9.1")
    ), patch(
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


def test_user_update():
    with patch(
        "salt.modules.postgres._run_psql", Mock(return_value={"retcode": 0})
    ), patch(
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
        assert re.match(
            'ALTER ROLE "test_username" WITH  INHERIT NOCREATEDB '
            "NOCREATEROLE NOREPLICATION LOGIN "
            "UNENCRYPTED PASSWORD ['\"]{0,5}test_role_pass['\"]{0,5} "
            "VALID UNTIL '2017-07-01';"
            ' GRANT "test_groups" TO "test_username"',
            postgres._run_psql.call_args[0][0][14],
        )


def test_user_update2():
    with patch(
        "salt.modules.postgres._run_psql", Mock(return_value={"retcode": 0})
    ), patch(
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
        assert re.match(
            'ALTER ROLE "test_username" WITH  INHERIT NOCREATEDB '
            "CREATEROLE NOREPLICATION LOGIN;"
            ' GRANT "test_groups" TO "test_username"',
            postgres._run_psql.call_args[0][0][14],
        )


def test_user_update3():
    with patch(
        "salt.modules.postgres._run_psql", Mock(return_value={"retcode": 0})
    ), patch(
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
        assert re.match(
            'ALTER ROLE "test_username" WITH  INHERIT NOCREATEDB '
            "CREATEROLE NOREPLICATION LOGIN NOPASSWORD;"
            ' GRANT "test_groups" TO "test_username"',
            postgres._run_psql.call_args[0][0][14],
        )


@pytest.mark.skip_on_fips_enabled_platform
def test_user_update_encrypted_passwd():
    with patch(
        "salt.modules.postgres._run_psql", Mock(return_value={"retcode": 0})
    ), patch(
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
        assert re.match(
            'ALTER ROLE "test_username" WITH  INHERIT NOCREATEDB '
            "CREATEROLE NOREPLICATION LOGIN "
            "ENCRYPTED PASSWORD "
            "['\"]{0,5}md531c27e68d3771c392b52102c01be1da1['\"]{0,5}"
            '; GRANT "test_groups" TO "test_username"',
            postgres._run_psql.call_args[0][0][14],
        )


def test_version():
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
        assert re.match(
            "SELECT setting FROM pg_catalog.pg_settings",
            postgres._run_psql.call_args[0][0][14],
        )


def test_installed_extensions():
    with patch(
        "salt.modules.postgres.psql_query",
        Mock(return_value=[{"extname": "foo", "extversion": "1"}]),
    ):
        exts = postgres.installed_extensions()
        assert exts == {"foo": {"extversion": "1", "extname": "foo"}}


def test_available_extensions():
    with patch(
        "salt.modules.postgres.psql_query",
        Mock(return_value=[{"name": "foo", "default_version": "1"}]),
    ):
        exts = postgres.available_extensions()
        assert exts == {"foo": {"default_version": "1", "name": "foo"}}


def test_drop_extension2():
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
                assert postgres.drop_extension("foo")


def test_drop_extension3():
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
                assert postgres.drop_extension("foo")


def test_drop_extension1():
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
                assert not postgres.drop_extension("foo")


def test_create_mtdata():
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
            assert postgres._EXTENSION_INSTALLED in ret
            assert postgres._EXTENSION_TO_UPGRADE in ret
            assert postgres._EXTENSION_TO_MOVE in ret

            ret = postgres.create_metadata("foo", schema="foo", ext_version="0.4")
            assert postgres._EXTENSION_INSTALLED in ret
            assert postgres._EXTENSION_TO_UPGRADE not in ret
            assert postgres._EXTENSION_TO_MOVE not in ret

            ret = postgres.create_metadata("foo")
            assert postgres._EXTENSION_INSTALLED in ret
            assert postgres._EXTENSION_TO_UPGRADE not in ret
            assert postgres._EXTENSION_TO_MOVE not in ret

            ret = postgres.create_metadata("foobar")
            assert postgres._EXTENSION_NOT_INSTALLED in ret
            assert postgres._EXTENSION_INSTALLED not in ret
            assert postgres._EXTENSION_TO_UPGRADE not in ret
            assert postgres._EXTENSION_TO_MOVE not in ret


def test_create_extension_newerthan():
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
                Mock(return_value={"foo": {"default_version": "1.4", "name": "foo"}}),
            ):
                assert postgres.create_extension("foo")
                assert re.match(
                    'CREATE EXTENSION IF NOT EXISTS "foo" ;',
                    postgres._psql_prepare_and_run.call_args[0][0][1],
                )

                assert postgres.create_extension(
                    "foo", schema="a", ext_version="b", from_version="c"
                )
                assert re.match(
                    'CREATE EXTENSION IF NOT EXISTS "foo" '
                    'WITH SCHEMA "a" VERSION b FROM c ;',
                    postgres._psql_prepare_and_run.call_args[0][0][1],
                )
                assert not postgres.create_extension("foo")

                ret = postgres.create_extension("foo", ext_version="a", schema="b")
                assert ret is True
                assert re.match(
                    'ALTER EXTENSION "foo" SET SCHEMA "b";'
                    ' ALTER EXTENSION "foo" UPDATE TO a;',
                    postgres._psql_prepare_and_run.call_args[0][0][1],
                )

                ret = postgres.create_extension("foo", ext_version="a", schema="b")
                assert ret is True
                assert re.match(
                    'ALTER EXTENSION "foo" SET SCHEMA "b";',
                    postgres._psql_prepare_and_run.call_args[0][0][1],
                )

                ret = postgres.create_extension("foo", ext_version="a", schema="b")
                assert ret is True
                assert re.match(
                    'ALTER EXTENSION "foo" UPDATE TO a;',
                    postgres._psql_prepare_and_run.call_args[0][0][1],
                )
                assert not postgres.create_extension("foo", ext_version="a", schema="b")
                assert not postgres.create_extension("foo", ext_version="a", schema="b")


@pytest.mark.skip_on_fips_enabled_platform
def test_encrypt_passwords():
    assert postgres._maybe_encrypt_password("foo", "bar", False) == "bar"
    assert (
        postgres._maybe_encrypt_password("foo", "bar", True)
        == "md596948aad3fcae80c08a35c9b5958cd89"
    )


def test_schema_list(get_test_list_schema_csv):
    with patch(
        "salt.modules.postgres._run_psql",
        Mock(return_value={"retcode": 0, "stdout": get_test_list_schema_csv}),
    ):
        ret = postgres.schema_list(
            "maint_db",
            db_user="testuser",
            db_host="testhost",
            db_port="testport",
            db_password="foo",
        )
        assert ret == {
            "public": {
                "acl": "{postgres=UC/postgres,=UC/postgres}",
                "owner": "postgres",
            },
            "pg_toast": {"acl": "", "owner": "postgres"},
        }


def test_schema_exists():
    with patch("salt.modules.postgres._run_psql", Mock(return_value={"retcode": 0})):
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
            assert ret is True


def test_schema_get():
    with patch("salt.modules.postgres._run_psql", Mock(return_value={"retcode": 0})):
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
            assert ret == {
                "acl": "{postgres=UC/postgres,=UC/postgres}",
                "owner": "postgres",
            }


def test_schema_get_again():
    with patch("salt.modules.postgres._run_psql", Mock(return_value={"retcode": 0})):
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
            assert ret is None


def test_schema_create():
    with patch(
        "salt.modules.postgres._run_psql", Mock(return_value={"retcode": 0})
    ), patch("salt.utils.path.which", MagicMock(return_value="/usr/bin/pgsql")):
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


def test_schema_create2():
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
        assert ret is False


def test_schema_remove():
    with patch(
        "salt.modules.postgres._run_psql", Mock(return_value={"retcode": 0})
    ), patch("salt.utils.path.which", MagicMock(return_value="/usr/bin/pgsql")):
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


def test_schema_remove2():
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
        assert ret is False


def test_language_list(get_test_list_language_csv):
    """
    Test language listing
    """
    with patch(
        "salt.modules.postgres._run_psql",
        Mock(return_value={"retcode": 0, "stdout": get_test_list_language_csv}),
    ):
        ret = postgres.language_list(
            "testdb",
            user="testuser",
            host="testhost",
            port="testport",
            password="foo",
        )
        assert ret == {
            "c": "c",
            "internal": "internal",
            "plpgsql": "plpgsql",
            "sql": "sql",
        }


def test_language_exists():
    """
    Test language existence check
    """
    with patch(
        "salt.modules.postgres._run_psql", Mock(return_value={"retcode": 0})
    ), patch(
        "salt.modules.postgres.psql_query",
        Mock(
            return_value=[
                {"Name": "internal"},
                {"Name": "c"},
                {"Name": "sql"},
                {"Name": "plpgsql"},
            ]
        ),
    ), patch(
        "salt.modules.postgres.language_exists", Mock(return_value=True)
    ):
        ret = postgres.language_exists("sql", "testdb")
        assert ret is True


def test_language_create():
    """
    Test language creation - does not exist in db
    """
    with patch(
        "salt.modules.postgres._run_psql", Mock(return_value={"retcode": 0})
    ), patch("salt.utils.path.which", MagicMock(return_value="/usr/bin/pgsql")):
        with patch("salt.modules.postgres.language_exists", Mock(return_value=False)):
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


def test_language_create_exists():
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
        assert ret is False


def test_language_remove():
    """
    Test language removal - exists in db
    """
    with patch(
        "salt.modules.postgres._run_psql", Mock(return_value={"retcode": 0})
    ), patch("salt.utils.path.which", MagicMock(return_value="/usr/bin/pgsql")):
        with patch("salt.modules.postgres.language_exists", Mock(return_value=True)):
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


def test_language_remove_non_exist():
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
        assert ret is False


def test_privileges_list_table(get_test_privileges_list_table_csv):
    """
    Test privilege listing on a table
    """
    with patch(
        "salt.modules.postgres._run_psql",
        Mock(return_value={"retcode": 0, "stdout": get_test_privileges_list_table_csv}),
    ), patch("salt.utils.path.which", MagicMock(return_value="/usr/bin/pgsql")):
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
        assert ret == expected

        query = (
            "COPY (SELECT relacl AS name FROM pg_catalog.pg_class c "
            "JOIN pg_catalog.pg_namespace n ON n.oid = c.relnamespace "
            "WHERE nspname = 'public' AND relname = 'awl' AND relkind in ('r', 'v') "
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


def test_privileges_list_group(get_test_privileges_list_group_csv):
    """
    Test privilege listing on a group
    """
    with patch(
        "salt.modules.postgres._run_psql",
        Mock(return_value={"retcode": 0, "stdout": get_test_privileges_list_group_csv}),
    ), patch("salt.utils.path.which", MagicMock(return_value="/usr/bin/pgsql")):
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
        assert ret == expected

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


def test_has_privileges_on_table(get_test_privileges_list_table_csv):
    """
    Test privilege checks on table
    """
    with patch(
        "salt.modules.postgres._run_psql",
        Mock(return_value={"retcode": 0, "stdout": get_test_privileges_list_table_csv}),
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
        assert ret is True

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
        assert ret is True

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
        assert ret is True

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
        assert ret is False

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
        assert ret is True


def test_has_privileges_on_group(get_test_privileges_list_group_csv):
    """
    Test privilege checks on group
    """
    with patch(
        "salt.modules.postgres._run_psql",
        Mock(return_value={"retcode": 0, "stdout": get_test_privileges_list_group_csv}),
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
        assert ret is True

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
        assert ret is False

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
        assert ret is False


def test_privileges_grant_table():
    """
    Test granting privileges on table
    """
    with patch(
        "salt.modules.postgres._run_psql", Mock(return_value={"retcode": 0})
    ), patch("salt.utils.path.which", MagicMock(return_value="/usr/bin/pgsql")):
        with patch("salt.modules.postgres.has_privileges", Mock(return_value=False)):
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
    ), patch("salt.utils.path.which", MagicMock(return_value="/usr/bin/pgsql")), patch(
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
    ), patch("salt.utils.path.which", MagicMock(return_value="/usr/bin/pgsql")), patch(
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


def test_privileges_grant_group():
    """
    Test granting privileges on group
    """
    with patch(
        "salt.modules.postgres._run_psql", Mock(return_value={"retcode": 0})
    ), patch("salt.utils.path.which", MagicMock(return_value="/usr/bin/pgsql")), patch(
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
    ), patch("salt.utils.path.which", MagicMock(return_value="/usr/bin/pgsql")), patch(
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


def test_privileges_revoke_table():
    """
    Test revoking privileges on table
    """
    with patch(
        "salt.modules.postgres._run_psql", Mock(return_value={"retcode": 0})
    ), patch("salt.utils.path.which", MagicMock(return_value="/usr/bin/pgsql")), patch(
        "salt.modules.postgres.has_privileges", Mock(return_value=True)
    ):
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


def test_privileges_revoke_group():
    """
    Test revoking privileges on group
    """
    with patch(
        "salt.modules.postgres._run_psql", Mock(return_value={"retcode": 0})
    ), patch("salt.utils.path.which", MagicMock(return_value="/usr/bin/pgsql")), patch(
        "salt.modules.postgres.has_privileges", Mock(return_value=True)
    ):
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


def test_datadir_init():
    """
    Test Initializing a postgres data directory
    """
    with patch("salt.modules.postgres._run_initdb", Mock(return_value={"retcode": 0})):
        with patch("salt.modules.postgres.datadir_exists", Mock(return_value=False)):
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
            assert ret is True


def test_datadir_exists():
    """
    Test Checks if postgres data directory has been initialized
    """
    with patch("os.path.isfile", Mock(return_value=True)):
        name = "/var/lib/pgsql/data"
        ret = postgres.datadir_exists(name)
        assert ret is True


@pytest.mark.parametrize(
    "v1,v2,result",
    (
        ("8.5", "9.5", True),
        ("8.5", "8.6", True),
        ("8.5.2", "8.5.3", True),
        ("9.5", "8.5", False),
        ("9.5", "9.6", True),
        ("9.5.0", "9.5.1", True),
        ("9.5", "9.5.1", True),
        ("9.5.1", "9.5", False),
        ("9.5b", "9.5a", False),
        ("10a", "10b", True),
        ("1.2.3.4", "1.2.3.5", True),
        ("10dev", "10next", True),
        ("10next", "10dev", False),
    ),
)
def test_pg_is_older_ext_ver(v1, v2, result):
    """
    Test Checks if postgres extension version string is older
    """
    assert postgres._pg_is_older_ext_ver(v1, v2) is result


def test_tablespace_create():
    with patch(
        "salt.modules.postgres._run_psql", Mock(return_value={"retcode": 0})
    ), patch("salt.utils.path.which", MagicMock(return_value="/usr/bin/pgsql")):
        postgres.tablespace_create(
            "test_tablespace",
            "/tmp/postgres_test_tablespace",
            user="testuser",
            host="testhost",
            port="testport",
            maintenance_db="maint_db",
            password="foo",
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
                'CREATE TABLESPACE "test_tablespace" OWNER "otheruser" LOCATION \'/tmp/postgres_test_tablespace\' ',
            ],
            runas="foo",
            password="foo",
            host="testhost",
            port="testport",
            user="testuser",
        )


def test_tablespace_list():
    with patch(
        "salt.modules.postgres._run_psql", Mock(return_value={"retcode": 0})
    ), patch(
        "salt.utils.path.which", MagicMock(return_value="/usr/bin/pgsql")
    ), patch.dict(
        postgres.__salt__,
        {
            "postgres.psql_query": MagicMock(
                return_value=[
                    {
                        "Name": "pg_global",
                        "Owner": "postgres",
                        "ACL": "",
                        "Opts": "",
                        "Location": "",
                    },
                    {
                        "Name": "pg_default",
                        "Owner": "postgres",
                        "ACL": "",
                        "Opts": "",
                        "Location": "",
                    },
                    {
                        "Name": "test_tablespace",
                        "Owner": "testuser",
                        "ACL": "",
                        "Opts": "",
                        "Location": "/tmp/posgrest_test_tablespace",
                    },
                ]
            ),
        },
    ):
        ret = postgres.tablespace_list(
            user="testuser",
            host="testhost",
            port="testport",
            maintenance_db="maint_db",
            password="foo",
            runas="foo",
        )

        expected_data = {
            "pg_global": {"Owner": "postgres", "ACL": "", "Opts": "", "Location": ""},
            "pg_default": {"Owner": "postgres", "ACL": "", "Opts": "", "Location": ""},
            "test_tablespace": {
                "Owner": "testuser",
                "ACL": "",
                "Opts": "",
                "Location": "/tmp/posgrest_test_tablespace",
            },
        }
        assert ret == expected_data


def test_tablespace_exists_true():
    with patch(
        "salt.modules.postgres._run_psql", Mock(return_value={"retcode": 0})
    ), patch(
        "salt.utils.path.which", MagicMock(return_value="/usr/bin/pgsql")
    ), patch.dict(
        postgres.__salt__,
        {
            "postgres.psql_query": MagicMock(
                return_value=[
                    {
                        "Name": "pg_global",
                        "Owner": "postgres",
                        "ACL": "",
                        "Opts": "",
                        "Location": "",
                    },
                    {
                        "Name": "pg_default",
                        "Owner": "postgres",
                        "ACL": "",
                        "Opts": "",
                        "Location": "",
                    },
                    {
                        "Name": "test_tablespace",
                        "Owner": "testuser",
                        "ACL": "",
                        "Opts": "",
                        "Location": "/tmp/posgrest_test_tablespace",
                    },
                ]
            ),
        },
    ):
        ret = postgres.tablespace_exists(
            "test_tablespace",
            user="testuser",
            host="testhost",
            port="testport",
            maintenance_db="maint_db",
            password="foo",
            runas="foo",
        )
        assert ret is True


def test_tablespace_exists_false():
    with patch(
        "salt.modules.postgres._run_psql", Mock(return_value={"retcode": 0})
    ), patch(
        "salt.utils.path.which", MagicMock(return_value="/usr/bin/pgsql")
    ), patch.dict(
        postgres.__salt__,
        {
            "postgres.psql_query": MagicMock(
                return_value=[
                    {
                        "Name": "pg_global",
                        "Owner": "postgres",
                        "ACL": "",
                        "Opts": "",
                        "Location": "",
                    },
                    {
                        "Name": "pg_default",
                        "Owner": "postgres",
                        "ACL": "",
                        "Opts": "",
                        "Location": "",
                    },
                    {
                        "Name": "test_tablespace",
                        "Owner": "testuser",
                        "ACL": "",
                        "Opts": "",
                        "Location": "/tmp/posgrest_test_tablespace",
                    },
                ]
            ),
        },
    ):
        ret = postgres.tablespace_exists(
            "bad_test_tablespace",
            user="testuser",
            host="testhost",
            port="testport",
            maintenance_db="maint_db",
            password="foo",
            runas="foo",
        )
        assert ret is False


def test_tablespace_alter_new_owner():
    with patch(
        "salt.modules.postgres._run_psql", Mock(return_value={"retcode": 0})
    ), patch("salt.utils.path.which", MagicMock(return_value="/usr/bin/pgsql")):
        postgres.tablespace_alter(
            "test_tablespace",
            user="testuser",
            host="testhost",
            port="testport",
            maintenance_db="maint_db",
            password="foo",
            runas="foo",
            new_owner="testuser",
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
                'ALTER TABLESPACE "test_tablespace" OWNER TO "testuser"',
            ],
            runas="foo",
            password="foo",
            host="testhost",
            port="testport",
            user="testuser",
        )


def test_tablespace_alter_new_name():
    with patch(
        "salt.modules.postgres._run_psql", Mock(return_value={"retcode": 0})
    ), patch("salt.utils.path.which", MagicMock(return_value="/usr/bin/pgsql")):
        postgres.tablespace_alter(
            "test_tablespace",
            user="testuser",
            host="testhost",
            port="testport",
            maintenance_db="maint_db",
            password="foo",
            runas="foo",
            new_name="test_tablespace2",
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
                'ALTER TABLESPACE "test_tablespace" RENAME TO "test_tablespace2"',
            ],
            runas="foo",
            password="foo",
            host="testhost",
            port="testport",
            user="testuser",
        )


def test_tablespace_remove():
    with patch(
        "salt.modules.postgres._run_psql", Mock(return_value={"retcode": 0})
    ), patch("salt.utils.path.which", MagicMock(return_value="/usr/bin/pgsql")):
        postgres.tablespace_remove(
            "test_tablespace",
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
                'DROP TABLESPACE "test_tablespace"',
            ],
            runas="foo",
            password="foo",
            host="testhost",
            port="testport",
            user="testuser",
        )
