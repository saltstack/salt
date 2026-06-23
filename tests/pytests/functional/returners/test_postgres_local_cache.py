"""
Functional tests for the ``postgres_local_cache`` returner.

These spin up a real PostgreSQL server in a container so the
``ON CONFLICT (jid) DO NOTHING`` and ``psycopg2.errors.UniqueViolation``
code paths added for #69214 are exercised against a live database
rather than a mock.
"""

import logging
import time

import pytest

import salt.returners.postgres_local_cache as postgres_local_cache

docker = pytest.importorskip("docker")
psycopg2 = pytest.importorskip("psycopg2")
import psycopg2.errors  # isort:skip  pylint: disable=3rd-party-module-not-gated

log = logging.getLogger(__name__)

pytestmark = [
    pytest.mark.slow_test,
    pytest.mark.skip_if_binaries_missing("docker", "dockerd", check_all=False),
]


# The schema is documented in ``salt.returners.postgres_local_cache``'s
# module docstring; keep this aligned with that block.
_SCHEMA = """
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


def _check_postgres_ready(timeout_at, container, db_user, db_passwd, db_name):
    sleeptime = 0.5
    while time.time() <= timeout_at:
        try:
            if not container.is_running():
                log.warning("%s is no longer running", container)
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
def postgres_credentials():
    return {
        "user": "salt",
        "passwd": "Pa55w0rd!",
        "db": "salt",
    }


@pytest.fixture(scope="module")
def postgres_container(salt_factories, postgres_credentials):
    environment = {
        "POSTGRES_USER": postgres_credentials["user"],
        "POSTGRES_PASSWORD": postgres_credentials["passwd"],
        "POSTGRES_DB": postgres_credentials["db"],
    }
    container = salt_factories.get_container(
        "postgres-local-cache-69214",
        # Pin to a release that supports ON CONFLICT (>= 9.5) so the
        # primary new code path is exercised. 14 is current LTS at the
        # time of writing.
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
        postgres_credentials["user"],
        postgres_credentials["passwd"],
        postgres_credentials["db"],
    )
    with container.started() as factory:
        yield factory


@pytest.fixture(scope="module")
def postgres_port(postgres_container):
    return postgres_container.get_host_port_binding(5432, protocol="tcp", ipv6=False)


@pytest.fixture
def postgres_opts(minion_opts, postgres_credentials, postgres_port):
    opts = minion_opts.copy()
    opts.update(
        {
            "master_job_cache.postgres.host": "127.0.0.1",
            "master_job_cache.postgres.port": postgres_port,
            "master_job_cache.postgres.user": postgres_credentials["user"],
            "master_job_cache.postgres.passwd": postgres_credentials["passwd"],
            "master_job_cache.postgres.db": postgres_credentials["db"],
        }
    )
    return opts


@pytest.fixture
def configure_loader_modules(postgres_opts):
    return {
        postgres_local_cache: {
            "__opts__": postgres_opts,
        },
    }


@pytest.fixture
def schema(postgres_opts):
    """Create the schema and truncate between tests for isolation."""
    conn = psycopg2.connect(
        host=postgres_opts["master_job_cache.postgres.host"],
        port=postgres_opts["master_job_cache.postgres.port"],
        user=postgres_opts["master_job_cache.postgres.user"],
        password=postgres_opts["master_job_cache.postgres.passwd"],
        database=postgres_opts["master_job_cache.postgres.db"],
    )
    try:
        with conn:
            with conn.cursor() as cur:
                cur.execute(_SCHEMA)
                cur.execute("TRUNCATE jids, salt_returns, salt_events")
        yield conn
    finally:
        conn.close()


def _load(fun="test.ping"):
    return {
        "tgt_type": "glob",
        "cmd": "publish",
        "tgt": "*",
        "kwargs": {},
        "ret": "",
        "user": "root",
        "arg": [],
        "fun": fun,
    }


def test_save_load_persists_row(schema, postgres_opts):
    """A single save_load writes the row and returns the same load via
    get_load."""
    jid = "20260606120000000001"
    postgres_local_cache.save_load(jid, _load("test.ping"))

    loaded = postgres_local_cache.get_load(jid)
    assert loaded["jid"] == jid
    assert loaded["fun"] == "test.ping"


def test_save_load_duplicate_jid_is_idempotent(schema, postgres_opts):
    """
    Regression test for #69214.

    In an active-active multi-master cluster both masters race to
    persist the same JID. The second save_load must not raise; the row
    written by the first master must remain intact. This exercises
    ``ON CONFLICT (jid) DO NOTHING`` on PostgreSQL >= 9.5 against a
    real server.
    """
    jid = "20260606120000000002"
    postgres_local_cache.save_load(jid, _load("test.ping"))

    # Second master writes the same jid with a different fun -- must
    # not raise and must not overwrite the first row (DO NOTHING).
    postgres_local_cache.save_load(jid, _load("state.apply"))

    with schema.cursor() as cur:
        cur.execute("SELECT count(*), max(fun) FROM jids WHERE jid = %s", (jid,))
        count, fun = cur.fetchone()
    assert count == 1
    assert fun == "test.ping"


def test_save_load_uses_on_conflict_on_pg_95_or_newer(schema, postgres_opts):
    """
    Sanity check that the running container is on a PostgreSQL version
    that exercises the ON CONFLICT path (the whole point of this
    functional test). If this fails the test image needs to be bumped.
    """
    with schema.cursor() as cur:
        cur.execute("SHOW server_version_num")
        server_version = int(cur.fetchone()[0])
    assert server_version >= 90500, (
        f"functional test image must be PG >= 9.5 to exercise the ON "
        f"CONFLICT path; got {server_version}"
    )
