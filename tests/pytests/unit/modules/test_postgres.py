import pytest

import salt.modules.config as configmod
import salt.modules.postgres as postgres
from tests.support.mock import MagicMock, patch

# 'md5' + md5('password' + 'username')
md5_pw = "md55a231fcdb710d73268c4f44283487ba2"

scram_pw = (
    "SCRAM-SHA-256$4096:wLr5nqC+3F+r7FdQPnB+nA==$"
    "0hn08ZdX8kirGaL4TM0j13digH9Wl365OOzCtAuF2pE=:"
    "LzAh/MGUdjYkdbDzcOKpfGwa3WwPUsyGcY+TEnSpcto="
)

test_privileges_list_function_csv = (
    'name\n"{baruwatest=X/baruwatest,bayestest=r/baruwatest,baruwa=X*/baruwatest}"\n'
)


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
    assert postgres._verify_password(role, password, verifier, method) == result


def test_has_privileges_with_function():
    with patch(
        "salt.modules.postgres._run_psql",
        MagicMock(
            return_value={"retcode": 0, "stdout": test_privileges_list_function_csv}
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
