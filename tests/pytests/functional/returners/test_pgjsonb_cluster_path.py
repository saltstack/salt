"""
Functional tests for ``pgjsonb`` returner cluster_path support
(RFC item 9).

Spin up a real PostgreSQL container, exercise the probe/INSERT/SELECT
paths both before and after applying the additive migration, and
confirm the pre-topology schema still roundtrips cleanly.
"""

import logging
import time

import pytest

import salt.returners.pgjsonb as pgjsonb

docker = pytest.importorskip("docker")
psycopg2 = pytest.importorskip("psycopg2")
import psycopg2.extras  # isort:skip  pylint: disable=3rd-party-module-not-gated

log = logging.getLogger(__name__)

pytestmark = [
    pytest.mark.slow_test,
    pytest.mark.skip_if_binaries_missing("docker", "dockerd", check_all=False),
]


# Pre-topology schema (no cluster_path).
_SCHEMA_PRE = """
CREATE TABLE IF NOT EXISTS jids (
   jid varchar(255) NOT NULL primary key,
   load jsonb NOT NULL
);
CREATE TABLE IF NOT EXISTS salt_returns (
  fun varchar(50) NOT NULL,
  jid varchar(255) NOT NULL,
  return jsonb NOT NULL,
  id varchar(255) NOT NULL,
  success varchar(10) NOT NULL,
  full_ret jsonb NOT NULL,
  alter_time TIMESTAMP WITH TIME ZONE DEFAULT NOW());
CREATE TABLE IF NOT EXISTS salt_events (
    id BIGINT NOT NULL UNIQUE DEFAULT nextval('seq_salt_events_id'),
    tag varchar(255) NOT NULL,
    data jsonb NOT NULL,
    alter_time TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    master_id varchar(255) NOT NULL);
"""

_MIGRATION = "ALTER TABLE salt_returns ADD COLUMN IF NOT EXISTS cluster_path jsonb NULL"


def _check_pg_ready(timeout_at, container, db_user, db_passwd, db_name):
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
        "pgjsonb-cluster-path-rfc9",
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
        _check_pg_ready,
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
            "returner.pgjsonb.host": "127.0.0.1",
            "returner.pgjsonb.port": pg_port,
            "returner.pgjsonb.user": pg_credentials["user"],
            "returner.pgjsonb.pass": pg_credentials["passwd"],
            "returner.pgjsonb.db": pg_credentials["db"],
        }
    )
    return opts


@pytest.fixture
def configure_loader_modules(pg_opts):
    return {pgjsonb: {"__opts__": pg_opts, "__salt__": {}}}


def _connect(pg_opts):
    return psycopg2.connect(
        host=pg_opts["returner.pgjsonb.host"],
        port=pg_opts["returner.pgjsonb.port"],
        user=pg_opts["returner.pgjsonb.user"],
        password=pg_opts["returner.pgjsonb.pass"],
        database=pg_opts["returner.pgjsonb.db"],
    )


@pytest.fixture
def schema_pre(pg_opts):
    conn = _connect(pg_opts)
    try:
        with conn:
            with conn.cursor() as cur:
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
    """Pre-migration DB: inbound load with cluster_path still inserts cleanly."""
    jid = "20260707130000000001"
    pgjsonb.returner(_ret(jid, "m1", cluster_path=["east"]))
    got = pgjsonb.get_jid(jid)
    assert "m1" in got
    # Without the column, cluster_path is not surfaced.
    full = got["m1"]
    if isinstance(full, dict):
        assert "cluster_path" not in full


def test_cluster_path_persisted_after_migration(schema_migrated, pg_opts):
    jid = "20260707130000000002"
    pgjsonb.returner(_ret(jid, "m1", cluster_path=["east", "central"]))
    got = pgjsonb.get_jid(jid)
    assert got["m1"]["cluster_path"] == ["east", "central"]


def test_no_cluster_path_leaves_column_null(schema_migrated, pg_opts):
    jid = "20260707130000000003"
    pgjsonb.returner(_ret(jid, "m1"))
    with _connect(pg_opts) as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT cluster_path FROM salt_returns WHERE jid = %s",
                (jid,),
            )
            cp = cur.fetchone()[0]
    assert cp is None


def test_get_jid_backward_compat_rows_without_cluster_path(schema_migrated, pg_opts):
    """Rows inserted directly without cluster_path still read cleanly."""
    jid = "20260707130000000004"
    with _connect(pg_opts) as conn:
        with conn.cursor() as cur:
            cur.execute(
                "INSERT INTO salt_returns "
                "(fun, jid, return, id, success, full_ret) "
                "VALUES (%s, %s, %s, %s, %s, %s)",
                (
                    "test.ping",
                    jid,
                    psycopg2.extras.Json(True),
                    "legacy-m",
                    "True",
                    psycopg2.extras.Json({"return": True}),
                ),
            )
    got = pgjsonb.get_jid(jid)
    assert "legacy-m" in got
    full = got["legacy-m"]
    if isinstance(full, dict):
        assert "cluster_path" not in full
