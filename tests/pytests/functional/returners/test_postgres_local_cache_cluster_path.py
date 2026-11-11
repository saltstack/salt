"""
Functional tests for ``postgres_local_cache`` cluster_path support
(RFC item 9).
"""

import logging
import time

import pytest

import salt.returners.postgres_local_cache as postgres_local_cache

docker = pytest.importorskip("docker")
psycopg2 = pytest.importorskip("psycopg2")

log = logging.getLogger(__name__)

pytestmark = [
    pytest.mark.slow_test,
    pytest.mark.skip_if_binaries_missing("docker", "dockerd", check_all=False),
]


_SCHEMA_PRE = """
CREATE TABLE IF NOT EXISTS jids (
  jid     varchar(20) PRIMARY KEY,
  started TIMESTAMP WITH TIME ZONE DEFAULT now(),
  tgt_type text NOT NULL,
  cmd text NOT NULL,
  tgt text NOT NULL,
  kwargs text NOT NULL,
  ret text NOT NULL,
  username text NOT NULL,
  arg text NOT NULL,
  fun text NOT NULL
);
CREATE TABLE IF NOT EXISTS salt_returns (
  added     TIMESTAMP WITH TIME ZONE DEFAULT now(),
  fun       text NOT NULL,
  jid       varchar(20) NOT NULL,
  return    text NOT NULL,
  id        text NOT NULL,
  success   boolean
);
CREATE TABLE IF NOT EXISTS salt_events (
  id SERIAL,
  tag text NOT NULL,
  data text NOT NULL,
  alter_time TIMESTAMP WITH TIME ZONE DEFAULT now(),
  master_id text NOT NULL
);
"""

_MIGRATION = "ALTER TABLE salt_returns ADD COLUMN IF NOT EXISTS cluster_path text NULL"


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
        "pglc-cluster-path-rfc9",
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
            "master_job_cache.postgres.host": "127.0.0.1",
            "master_job_cache.postgres.port": pg_port,
            "master_job_cache.postgres.user": pg_credentials["user"],
            "master_job_cache.postgres.passwd": pg_credentials["passwd"],
            "master_job_cache.postgres.db": pg_credentials["db"],
        }
    )
    return opts


@pytest.fixture
def configure_loader_modules(pg_opts):
    return {postgres_local_cache: {"__opts__": pg_opts}}


def _connect(pg_opts):
    return psycopg2.connect(
        host=pg_opts["master_job_cache.postgres.host"],
        port=pg_opts["master_job_cache.postgres.port"],
        user=pg_opts["master_job_cache.postgres.user"],
        password=pg_opts["master_job_cache.postgres.passwd"],
        database=pg_opts["master_job_cache.postgres.db"],
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


def _load(jid, mid, cluster_path=None):
    out = {
        "jid": jid,
        "id": mid,
        "fun": "test.ping",
        "return": "pong",
        "success": True,
        "retcode": 0,
    }
    if cluster_path is not None:
        out["cluster_path"] = cluster_path
    return out


def test_backward_compat_no_cluster_path_column(schema_pre, pg_opts):
    """
    On a pre-topology database, inbound loads carrying ``cluster_path``
    still persist via the 5-column INSERT without raising.
    """
    jid = "20260707140000000001"
    postgres_local_cache.returner(_load(jid, "m1", cluster_path=["east"]))
    got = postgres_local_cache.get_jid(jid)
    assert "m1" in got
    assert "cluster_path" not in got["m1"]


def test_cluster_path_persisted_after_migration(schema_migrated, pg_opts):
    jid = "20260707140000000002"
    postgres_local_cache.returner(_load(jid, "m1", cluster_path=["east", "central"]))
    got = postgres_local_cache.get_jid(jid)
    assert got["m1"]["cluster_path"] == ["east", "central"]


def test_no_cluster_path_leaves_column_null(schema_migrated, pg_opts):
    jid = "20260707140000000003"
    postgres_local_cache.returner(_load(jid, "m1"))
    with _connect(pg_opts) as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT cluster_path FROM salt_returns WHERE jid = %s",
                (jid,),
            )
            cp = cur.fetchone()[0]
    assert cp is None
    got = postgres_local_cache.get_jid(jid)
    assert "cluster_path" not in got["m1"]


def test_duplicate_minion_id_different_clusters(schema_migrated, pg_opts):
    """
    Two returns with the same ``(jid, id)`` but different
    cluster_paths are both persisted (postgres_local_cache does not
    deduplicate on insert) and distinguishable via the column.
    """
    jid = "20260707140000000004"
    postgres_local_cache.returner(_load(jid, "web-01", cluster_path=["east"]))
    postgres_local_cache.returner(_load(jid, "web-01", cluster_path=["west"]))
    with _connect(pg_opts) as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT cluster_path FROM salt_returns WHERE jid = %s "
                "ORDER BY cluster_path",
                (jid,),
            )
            rows = [r[0] for r in cur.fetchall()]
    import salt.utils.json

    decoded = [salt.utils.json.loads(p) for p in rows]
    assert decoded == [["east"], ["west"]]
