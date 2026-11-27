import os
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from threading import Barrier

import pytest

import salt.cache
import salt.key
import salt.sqlalchemy
from tests.pytests.functional.cache.helpers import run_common_cache_tests
from tests.support.pytest.database import available_databases

sqlalchemy = pytest.importorskip("sqlalchemy")

pytestmark = [
    pytest.mark.slow_test,
    pytest.mark.parametrize(
        "database_backend",
        available_databases(
            [
                ("mysql-server", "8.0"),
                ("mariadb", "10.4"),
                ("mariadb", "10.5"),
                ("percona", "8.0"),
                ("postgresql", "13"),
                ("postgresql", "17"),
                ("sqlite", None),
            ]
        ),
        indirect=True,
    ),
]


@pytest.fixture
def cache(master_opts, database_backend, tmp_path_factory):
    opts = master_opts.copy()
    opts["cache"] = "sqlalchemy"
    opts["sqlalchemy.echo"] = True

    if database_backend.dialect in {"mysql", "postgresql"}:
        if database_backend.dialect == "mysql":
            driver = (
                "mariadb+pymysql"
                if database_backend.name == "mariadb"
                else "mysql+pymysql"
            )
        elif database_backend.dialect == "postgresql":
            driver = "postgresql+psycopg"

        opts["sqlalchemy.drivername"] = driver
        opts["sqlalchemy.username"] = database_backend.user
        opts["sqlalchemy.password"] = database_backend.passwd
        opts["sqlalchemy.port"] = database_backend.port
        opts["sqlalchemy.database"] = database_backend.database
        opts["sqlalchemy.host"] = "0.0.0.0"
        opts["sqlalchemy.disable_connection_pool"] = True
    elif database_backend.dialect == "sqlite":
        opts["sqlalchemy.dsn"] = "sqlite:///" + os.path.join(
            tmp_path_factory.mktemp("sqlite"), "salt.db"
        )
    else:
        raise ValueError(f"Unsupported returner param: {database_backend}")

    salt.sqlalchemy.reconfigure_orm(opts)
    engine = salt.sqlalchemy.ENGINE_REGISTRY["default"]["engine"]
    if database_backend.dialect != "sqlite":

        @sqlalchemy.event.listens_for(engine, "connect")
        def set_timezone(connection, record):
            with connection.cursor() as cursor:
                cursor.execute(
                    "SET time_zone = '+05:30'"
                    if database_backend.dialect == "mysql"
                    else "SET TIME ZONE 'Asia/Kolkata'"
                )
            connection.commit()

    salt.sqlalchemy.drop_all()
    salt.sqlalchemy.create_all()

    return salt.cache.factory(opts)


@pytest.fixture(scope="module")
def master_opts(
    salt_factories,
    master_id,
    master_config_defaults,
    master_config_overrides,
):
    factory = salt_factories.salt_master_daemon(
        master_id,
        defaults=master_config_defaults or None,
        overrides=master_config_overrides,
    )
    return factory.config.copy()


def test_caching(subtests, cache):
    run_common_cache_tests(subtests, cache)


@pytest.mark.parametrize("include_data", [False, True])
def test_list_all_isolated_live_entries(cache, include_data):
    data = {"state": "accepted", "pub": "public key", "nested": b"bytes"}
    cache.store("keys", "live", data)
    cache.store("keys", "expired", data, expires=-1)
    cache.store("keys/child", "nested", data)
    other_cluster = salt.cache.Cache(cache.opts, cluster_id="other")
    other_cluster.store("keys", "other", data)
    assert cache.list_all("keys", include_data=include_data) == {"live": data}
    assert cache.list_all("missing", include_data=include_data) == {}


def test_plain_key_uses_sqlalchemy_cache(cache):
    opts = {**cache.opts, "keys.cache_driver": "sqlalchemy"}
    with salt.key.Key(opts) as key:
        key.cache.store("keys", "web1", {"state": "accepted", "pub": ""})
        key.cache.store("keys", "web2", {"state": "pending", "pub": ""})
        key.cache.store("keys", "expired", {"state": "accepted", "pub": ""}, expires=-1)
        assert key.list_keys()[key.ACC] == ["web1"]
        assert key.list_keys()[key.PEND] == ["web2"]
        assert key.glob_match("web*") == {key.ACC: ["web1"], key.PEND: ["web2"]}


def test_standalone_and_null_cluster_are_isolated(cache):
    standalone = salt.cache.Cache(cache.opts, cluster_id=None)
    named = salt.cache.Cache(cache.opts, cluster_id="null")
    standalone.store("keys", "same", "standalone")
    named.store("keys", "same", "named")
    assert standalone.fetch("keys", "same") == "standalone"
    assert named.fetch("keys", "same") == "named"


def test_expiry_and_limited_cleanup(cache):
    Cache = salt.sqlalchemy.model_for("Cache")
    for key in ("expired1", "expired2"):
        cache.store("expiry", key, key, expires=-60)
    cache.store("expiry", "live", "live", expires=3600)
    cache.store("expiry", "permanent", "permanent")
    assert cache.fetch("expiry", "expired1") == {}
    assert not cache.contains("expiry", "expired1")
    assert cache.list("expiry") == ["live", "permanent"]
    assert cache.fetch("expiry", "live") == "live"

    cache.clean_expired("expiry", limit=1)
    with salt.sqlalchemy.Session() as session:
        assert (
            session.scalar(
                sqlalchemy.select(sqlalchemy.func.count()).select_from(Cache)
            )
            == 3
        )
    cache.clean_expired("expiry")
    with salt.sqlalchemy.Session() as session:
        assert (
            session.scalar(
                sqlalchemy.select(sqlalchemy.func.count()).select_from(Cache)
            )
            == 2
        )
    assert cache.fetch("expiry", "permanent") == "permanent"


def test_overwrite_refreshes_utc_timestamp(cache):
    Cache = salt.sqlalchemy.model_for("Cache")
    before = datetime.now(timezone.utc)
    cache.store("timestamps", "key", "first")
    assert abs(cache.updated("timestamps", "key") - before.timestamp()) < 2
    with salt.sqlalchemy.Session() as session:
        session.execute(
            sqlalchemy.update(Cache).values(created_at=before - timedelta(days=1))
        )
        session.commit()
    cache.store("timestamps", "key", "second")
    assert (
        abs(cache.updated("timestamps", "key") - datetime.now(timezone.utc).timestamp())
        < 2
    )
    assert cache.fetch("timestamps", "key") == "second"


@pytest.mark.parametrize("expires", [None, 3600])
def test_overwrite_replaces_expiry(cache, expires):
    Cache = salt.sqlalchemy.model_for("Cache")
    cache.store("expiry", "key", "old", expires=-60)
    cache.store("expiry", "key", "new", expires=expires)
    assert cache.fetch("expiry", "key") == "new"
    with salt.sqlalchemy.Session() as session:
        expiry = session.scalar(sqlalchemy.select(Cache.expires_at))
    if expires is None:
        assert expiry is None
    else:
        assert abs((expiry - datetime.now(timezone.utc)).total_seconds() - expires) < 2
    cache.store("expiry", "key", "expired again", expires=-60)
    assert cache.fetch("expiry", "key") == {}


def test_overwrite_isolated_by_bank_and_cluster(cache):
    other_cluster = salt.cache.Cache(cache.opts, cluster_id="other")
    cache.store("bank", "key", "old")
    cache.store("other-bank", "key", "other bank")
    other_cluster.store("bank", "key", "other cluster")
    cache.store("bank", "key", "new")
    assert cache.fetch("bank", "key") == "new"
    assert cache.fetch("other-bank", "key") == "other bank"
    assert other_cluster.fetch("bank", "key") == "other cluster"


def test_concurrent_overwrites(cache):
    cache.store("concurrent", "key", "initial")
    start = Barrier(4)

    def overwrite(writer):
        start.wait(timeout=10)
        for iteration in range(5):
            cache.store("concurrent", "key", f"{writer}:{iteration}")

    with ThreadPoolExecutor(max_workers=4) as executor:
        list(executor.map(overwrite, range(4)))
    assert cache.fetch("concurrent", "key") in {f"{writer}:4" for writer in range(4)}


def test_bank_hierarchy(cache):
    cache.store("minions_%/web01", "grains", {"os": "Linux"})
    cache.store("minions_other/web02", "grains", {})
    cache.store("minions_%", "", "empty key")
    assert cache.list("") == ["minions_%", "minions_other"]
    assert cache.list("minions_%") == ["", "web01"]
    assert cache.contains("minions_%")
    cache.flush("minions_%", "")
    assert cache.list("minions_%") == ["web01"]
    cache.flush("minions_%")
    assert not cache.contains("minions_%")
    assert cache.contains("minions_other/web02", "grains")


def test_case_and_accent_sensitive_identifiers(cache):
    identifiers = ["Web01", "web01", "cafe", "café"]
    for name in identifiers:
        cache.store("keys", name, name)
        cache.store(name, "key", name)
    for name in identifiers:
        assert cache.fetch("keys", name) == name
        assert cache.fetch(name, "key") == name


def test_bank_hierarchy_is_case_sensitive(cache):
    cache.store("Foo/upper", "key", "upper")
    cache.store("foo/lower", "key", "lower")
    assert cache.list("Foo") == ["upper"]
    assert cache.list("foo") == ["lower"]
    assert cache.list("FOO") == []
    assert not cache.contains("FOO")
    cache.flush("Foo")
    assert not cache.contains("Foo")
    assert cache.fetch("foo/lower", "key") == "lower"
