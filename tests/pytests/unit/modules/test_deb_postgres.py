import logging

import pytest

import salt.modules.deb_postgres as deb_postgres
from tests.support.mock import Mock, patch

log = logging.getLogger(__name__)

pytestmark = [
    pytest.mark.skip_unless_on_linux(reason="Only supported on Linux family"),
]


@pytest.fixture
def get_lscuster():
    return """\
8.4 main 5432 online postgres /srv/8.4/main \
        /var/log/postgresql/postgresql-8.4-main.log
9.1 main 5433 online postgres /srv/9.1/main \
        /var/log/postgresql/postgresql-9.1-main.log
"""


@pytest.fixture
def configure_loader_modules(get_lscuster):
    return {
        deb_postgres: {
            "__salt__": {
                "config.option": Mock(),
                "cmd.run_all": Mock(return_value={"stdout": get_lscuster}),
                "file.chown": Mock(),
                "file.remove": Mock(),
            }
        }
    }


def test_cluster_create():
    with patch("salt.utils.path.which", Mock(return_value="/usr/bin/pg_createcluster")):
        expected_cmdstr = (
            "/usr/bin/pg_createcluster "
            "--port 5432 --locale fr_FR --encoding UTF-8 "
            "--datadir /opt/postgresql "
            "9.3 main"
        )

        deb_postgres.cluster_create(
            "9.3",
            "main",
            port="5432",
            locale="fr_FR",
            encoding="UTF-8",
            datadir="/opt/postgresql",
        )
        assert deb_postgres.__salt__["cmd.run_all"].call_args[0][0] == expected_cmdstr


def test_cluster_create_with_initdb_options():
    with patch("salt.utils.path.which", Mock(return_value="/usr/bin/pg_createcluster")):
        expected_cmdstr = (
            "/usr/bin/pg_createcluster "
            "--port 5432 --locale fr_FR --encoding UTF-8 "
            "--datadir /opt/postgresql "
            "11 main "
            "-- "
            "--allow-group-access "
            "--data-checksums "
            "--wal-segsize 32"
        )

        deb_postgres.cluster_create(
            "11",
            "main",
            port="5432",
            locale="fr_FR",
            encoding="UTF-8",
            datadir="/opt/postgresql",
            allow_group_access=True,
            data_checksums=True,
            wal_segsize="32",
        )
        assert deb_postgres.__salt__["cmd.run_all"].call_args[0][0] == expected_cmdstr


def test_cluster_create_with_float():
    with patch("salt.utils.path.which", Mock(return_value="/usr/bin/pg_createcluster")):
        expected_cmdstr = (
            "/usr/bin/pg_createcluster "
            "--port 5432 --locale fr_FR --encoding UTF-8 "
            "--datadir /opt/postgresql "
            "9.3 main"
        )

        deb_postgres.cluster_create(
            9.3,
            "main",
            port="5432",
            locale="fr_FR",
            encoding="UTF-8",
            datadir="/opt/postgresql",
        )
        assert deb_postgres.__salt__["cmd.run_all"].call_args[0][0] == expected_cmdstr


def test_parse_pg_lsclusters(get_lscuster):
    with patch("salt.utils.path.which", Mock(return_value="/usr/bin/pg_lsclusters")):
        stdout = get_lscuster
        maxDiff = None
        expected = {
            "8.4/main": {
                "port": 5432,
                "status": "online",
                "user": "postgres",
                "datadir": "/srv/8.4/main",
                "log": "/var/log/postgresql/postgresql-8.4-main.log",
            },
            "9.1/main": {
                "port": 5433,
                "status": "online",
                "user": "postgres",
                "datadir": "/srv/9.1/main",
                "log": "/var/log/postgresql/postgresql-9.1-main.log",
            },
        }
        assert deb_postgres._parse_pg_lscluster(stdout) == expected


def test_cluster_list():
    with patch("salt.utils.path.which", Mock(return_value="/usr/bin/pg_lsclusters")):
        return_list = deb_postgres.cluster_list()
        assert (
            deb_postgres.__salt__["cmd.run_all"].call_args[0][0]
            == "/usr/bin/pg_lsclusters --no-header"
        )

        return_dict = deb_postgres.cluster_list(verbose=True)
        assert isinstance(return_dict, dict)


def test_cluster_exists():
    assert deb_postgres.cluster_exists("8.4")
    assert deb_postgres.cluster_exists("8.4", "main")
    assert not deb_postgres.cluster_exists("3.4", "main")


def test_cluster_delete():
    with patch("salt.utils.path.which", Mock(return_value="/usr/bin/pg_dropcluster")):
        deb_postgres.cluster_remove("9.3", "main")
        assert (
            deb_postgres.__salt__["cmd.run_all"].call_args[0][0]
            == "/usr/bin/pg_dropcluster 9.3 main"
        )

        deb_postgres.cluster_remove("9.3", "main", stop=True)
        assert (
            deb_postgres.__salt__["cmd.run_all"].call_args[0][0]
            == "/usr/bin/pg_dropcluster --stop 9.3 main"
        )

        deb_postgres.cluster_remove(9.3, "main", stop=True)
        assert (
            deb_postgres.__salt__["cmd.run_all"].call_args[0][0]
            == "/usr/bin/pg_dropcluster --stop 9.3 main"
        )
