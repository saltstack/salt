"""
Functional tests for ``postgres`` returner cluster_path support
(RFC item 9).

The postgres returner probes ``information_schema`` for an optional
``cluster_path`` column on ``salt_returns``.  When the column is
present AND the inbound load carries a ``cluster_path`` key, the
annotation is persisted; otherwise the pre-topology 6-column INSERT
is used verbatim.

These tests spin up a real PostgreSQL container so the probe,
schema-migration, and lookup paths run against a live backend rather
than a mock.
"""

import logging
import time

import pytest

import salt.returners.postgres as postgres

docker = pytest.importorskip("docker")
psycopg2 = pytest.importorskip("psycopg2")

log = logging.getLogger(__name__)

pytestmark = [
    pytest.mark.slow_test,
    pytest.mark.skip_if_binaries_missing("docker", "dockerd", check_all=False),
]


# Pre-topology schema — no cluster_path column.  Used by the backward-
# compatibility tests to prove the returner still writes cleanly on an
# un-migrated database.
_SCHEMA_PRE = """
CREATE TABLE IF NOT EXISTS jids (
  jid   varchar(20) PRIMARY KEY,
  load  text NOT NULL
);
CREATE TABLE IF NOT EXISTS salt_returns (
  fun       varchar(50) NOT NULL,
  jid       varchar(255) NOT NULL,
  return    text NOT NULL,
  full_ret  text,
  id        varchar(255) NOT NULL,
  success   varchar(10) NOT NULL,
  alter_time   TIMESTAMP WITH TIME ZONE DEFAULT now()
);
CREATE TABLE IF NOT EXISTS salt_events (
    id BIGINT NOT NULL UNIQUE DEFAULT nextval('seq_salt_events_id'),
    tag varchar(255) NOT NULL,
    data text NOT NULL,
    alter_time TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    master_id varchar(255) NOT NULL
);
"""

# The additive migration documented in the postgres returner's docstring.
_MIGRATION = "ALTER TABLE salt_returns ADD COLUMN IF NOT EXISTS cluster_path text NULL"


def _check_postgres_ready(timeout_at, container, db_user, db_passwd, db_name):
    sleeptime = 0.5
    while time.time() <= timeout_at:
        try:
            if not container.is_running():
                return False
            ret = container.run(
                "psql",
                f"--username={db_user}",
                f"--dbname={db_name}",
                "-c",
                "SELECT 1",
                environment={"PGPASSWORD": db_passwd},
            )
            if ret.returncode == 0:
                break
        except docker.errors.APIError:
            log.exception("psql readiness check failed")
        time.sleep(sleeptime)
        sleeptime = min(sleeptime * 2, 5)
    else:
        return False
    return True


@pytest.fixture(scope="module")
def pg_credentials():
    return {"user": "salt", "passwd": "Pa55w0rd!", "db": "salt"}


@pytest.fixture(scope="module")
def pg_container(salt_factories, pg_credentials):
    environment = {
        "POSTGRES_USER": pg_credentials["user"],
        "POSTGRES_PASSWORD": pg_credentials["passwd"],
        "POSTGRES_DB": pg_credentials["db"],
    }
    container = salt_factories.get_container(
        "postgres-cluster-path-rfc9",
        image_name="postgres:14",
        pull_before_start=True,
        skip_on_pull_failure=True,
        skip_if_docker_client_not_connectable=True,
        container_run_kwargs={
            "ports": {"5432/tcp": None},
            "environment": environment,
        },
    )
    container.container_start_check(
        _check_postgres_ready,
        container,
        pg_credentials["user"],
        pg_credentials["passwd"],
        pg_credentials["db"],
    )
    with container.started() as factory:
        yield factory


@pytest.fixture(scope="module")
def pg_port(pg_container):
    return pg_container.get_host_port_binding(5432, protocol="tcp", ipv6=False)


@pytest.fixture
def pg_opts(minion_opts, pg_credentials, pg_port):
    opts = minion_opts.copy()
    opts.update(
        {
            "returner.postgres.host": "127.0.0.1",
            "returner.postgres.port": pg_port,
            "returner.postgres.user": pg_credentials["user"],
            "returner.postgres.passwd": pg_credentials["passwd"],
            "returner.postgres.db": pg_credentials["db"],
        }
    )
    return opts


@pytest.fixture
def configure_loader_modules(pg_opts):
    return {postgres: {"__opts__": pg_opts, "__salt__": {}}}


def _connect(pg_opts):
    return psycopg2.connect(
        host=pg_opts["returner.postgres.host"],
        port=pg_opts["returner.postgres.port"],
        user=pg_opts["returner.postgres.user"],
        password=pg_opts["returner.postgres.passwd"],
        database=pg_opts["returner.postgres.db"],
    )


@pytest.fixture
def schema_pre(pg_opts):
    """Base pre-topology schema; test opts-in to the migration separately."""
    conn = _connect(pg_opts)
    try:
        with conn:
            with conn.cursor() as cur:
                # Clean slate.
                cur.execute("DROP TABLE IF EXISTS salt_returns")
                cur.execute("DROP TABLE IF EXISTS jids")
                cur.execute("DROP TABLE IF EXISTS salt_events")
                cur.execute("DROP SEQUENCE IF EXISTS seq_salt_events_id")
                cur.execute("CREATE SEQUENCE seq_salt_events_id")
                cur.execute(_SCHEMA_PRE)
        yield conn
    finally:
        conn.close()


@pytest.fixture
def schema_migrated(schema_pre):
    """Base schema + the RFC item 9 additive migration applied."""
    with schema_pre:
        with schema_pre.cursor() as cur:
            cur.execute(_MIGRATION)
    return schema_pre


def _ret(jid, mid, cluster_path=None):
    out = {
        "jid": jid,
        "id": mid,
        "fun": "test.ping",
        "return": True,
        "success": True,
        "retcode": 0,
    }
    if cluster_path is not None:
        out["cluster_path"] = cluster_path
    return out


def test_backward_compat_no_cluster_path_column(schema_pre, pg_opts):
    """
    On a pre-topology database (no ``cluster_path`` column), the
    returner must fall back to the 6-column INSERT even when the
    inbound load carries a ``cluster_path`` — operators who haven't
    run the migration shouldn't see a crash.
    """
    jid = "20260707120000000001"
    postgres.returner(_ret(jid, "m1", cluster_path=["east"]))
    got = postgres.get_jid(jid)
    assert "m1" in got
    assert "cluster_path" not in got["m1"]


def test_cluster_path_persisted_after_migration(schema_migrated, pg_opts):
    """After the additive ALTER TABLE, cluster_path is round-tripped."""
    jid = "20260707120000000002"
    postgres.returner(_ret(jid, "m1", cluster_path=["east", "central"]))
    got = postgres.get_jid(jid)
    assert got["m1"]["cluster_path"] == ["east", "central"]


def test_no_cluster_path_on_load_leaves_column_null(schema_migrated, pg_opts):
    """
    A non-topology return (no ``cluster_path`` on the load) must leave
    the column NULL — get_jid returns the record without the key, same
    as pre-topology deploys.
    """
    jid = "20260707120000000003"
    postgres.returner(_ret(jid, "m1"))
    got = postgres.get_jid(jid)
    assert "cluster_path" not in got["m1"]
    sql = "SELECT cluster_path FROM salt_returns WHERE jid = %s AND id = %s"
    with _connect(pg_opts) as conn:
        with conn.cursor() as cur:
            cur.execute(sql, (jid, "m1"))
            cp = cur.fetchone()[0]
    assert cp is None


def test_duplicate_minion_id_different_clusters(schema_migrated, pg_opts):
    """
    Two returns with the same ``(jid, id)`` but distinct
    cluster_paths are both persisted and distinguishable on lookup.
    """
    jid = "20260707120000000004"
    postgres.returner(_ret(jid, "web-01", cluster_path=["east"]))
    postgres.returner(_ret(jid, "web-01", cluster_path=["west"]))
    with _connect(pg_opts) as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT id, cluster_path FROM salt_returns "
                "WHERE jid = %s ORDER BY cluster_path",
                (jid,),
            )
            rows = cur.fetchall()
    assert len(rows) == 2
    paths = sorted(r[1] for r in rows)
    import salt.utils.json

    decoded = [salt.utils.json.loads(p) for p in paths]
    assert decoded == [["east"], ["west"]]


def test_get_jid_backward_compat_rows_without_cluster_path(schema_migrated, pg_opts):
    """
    After migration, rows that were inserted without a cluster_path
    (e.g. local returns) still read correctly — the column just
    appears absent in the record.
    """
    jid = "20260707120000000005"
    # Direct SQL insert with cluster_path NULL mimicking a pre-RFC row.
    with _connect(pg_opts) as conn:
        with conn.cursor() as cur:
            import salt.utils.json

            cur.execute(
                "INSERT INTO salt_returns "
                "(fun, jid, return, id, success, full_ret) "
                "VALUES (%s, %s, %s, %s, %s, %s)",
                (
                    "test.ping",
                    jid,
                    salt.utils.json.dumps(True),
                    "legacy-minion",
                    "True",
                    salt.utils.json.dumps({"return": True}),
                ),
            )
    got = postgres.get_jid(jid)
    assert "legacy-minion" in got
    assert "cluster_path" not in got["legacy-minion"]
