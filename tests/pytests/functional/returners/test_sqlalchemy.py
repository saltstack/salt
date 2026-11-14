import logging
import os
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone

import pytest

import salt.exceptions
import salt.loader
import salt.sqlalchemy
from salt.sqlalchemy import Session
from salt.sqlalchemy.models import model_for
from salt.utils.jid import gen_jid
from tests.support.mock import patch
from tests.support.pytest.database import available_databases

sqlalchemy = pytest.importorskip("sqlalchemy")

delete = sqlalchemy.delete
func = sqlalchemy.func
select = sqlalchemy.select

log = logging.getLogger(__name__)

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


@pytest.fixture(scope="module")
def returner(master_opts, database_backend, tmp_path_factory):
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

    functions = salt.loader.minion_mods(opts)
    return salt.loader.returners(opts, functions)


def test_returner_inserts(returner):
    Returns = model_for("Returns")
    ret = {"fun": "test.ping", "jid": gen_jid({}), "id": "minion", "success": True}
    returner["sqlalchemy.returner"](ret)

    with Session() as session:
        stmt = select(func.count()).where(  # pylint: disable=not-callable
            Returns.jid == ret["jid"]
        )
        inserted = session.execute(stmt).scalar()
        assert inserted == 1


def test_returner_with_minion_defaults(returner):
    opts = returner["sqlalchemy.returner"].__globals__["__opts__"]
    ret = {
        "fun": "test.ping",
        "jid": gen_jid({}),
        "id": "minion-defaults",
        "success": True,
    }
    with patch.dict(opts, {"id": "minion-defaults"}, clear=True):
        returner["sqlalchemy.returner"](ret)
        assert returner["sqlalchemy.get_jid"](ret["jid"]) == {"minion-defaults": ret}


def test_event_return_inserts(returner):
    Events = model_for("Events")
    evts = [{"tag": "test", "data": {"_stamp": str(datetime.now(timezone.utc))}}]
    returner["sqlalchemy.event_return"](evts)
    with Session() as session:
        stmt = select(func.count()).where(  # pylint: disable=not-callable
            Events.tag == "test"
        )
        inserted = session.execute(stmt).scalar()
        assert inserted == 1


def test_save_load_inserts(returner):
    Jids = model_for("Jids")
    jid = gen_jid({})
    load = {"foo": "bar"}
    minions = ["minion1", "minion2"]
    returner["sqlalchemy.save_load"](jid, load, minions)
    with Session() as session:
        stmt = select(func.count()).where(  # pylint: disable=not-callable
            Jids.jid == jid
        )
        inserted = session.execute(stmt).scalar()
        assert inserted == 1


def test_repeated_save_preserves_publish_load(returner):
    Jids = model_for("Jids")
    jid = gen_jid({}) + "_123"
    load = {"fun": "test.ping", "arg": []}
    minions = ["minion1", "minion2"]
    returner["sqlalchemy.save_load"](jid, load, minions)
    for minion in minions:
        returner["sqlalchemy.save_load"](jid, {"id": minion, "return": True})
    assert returner["sqlalchemy.get_load"](jid) == {**load, "Minions": minions}
    with Session() as session:
        assert (
            session.scalar(
                select(func.count()).select_from(Jids).where(Jids.jid == jid)
            )
            == 1
        )


@pytest.mark.parametrize("model_name", ["Jids", "JidMinions"])
def test_jid_timestamp_constraint(returner, model_name):
    Model = model_for(model_name)
    now = datetime.now(timezone.utc)
    values = (
        {"load": {}, "minions": []} if model_name == "Jids" else {"minion_id": "minion"}
    )
    with Session() as session, pytest.raises(sqlalchemy.exc.DBAPIError):
        session.execute(
            sqlalchemy.insert(Model).values(
                jid=now.strftime("%Y%m%d%H%M%S%f"),
                cluster="constraint-test",
                created_at=now + timedelta(seconds=1),
                **values,
            )
        )
        session.commit()


def test_cluster_isolation(returner):
    opts = returner["sqlalchemy.save_load"].__globals__["__opts__"]
    jid = gen_jid({})
    for cluster in (None, "null", "cluster-a", "cluster-b"):
        minion = cluster or "standalone"
        with patch.dict(opts, {"cluster_id": cluster}):
            returner["sqlalchemy.save_load"](jid, {"cluster": cluster}, [minion])
            returner["sqlalchemy.save_minions"](jid, [f"{minion}-forwarded"])
            returner["sqlalchemy.returner"](
                {"jid": jid, "id": minion, "fun": "test.ping", "success": True}
            )
    for cluster in (None, "null", "cluster-a", "cluster-b"):
        minion = cluster or "standalone"
        with patch.dict(opts, {"cluster_id": cluster}):
            assert returner["sqlalchemy.get_load"](jid) == {
                "cluster": cluster,
                "Minions": [minion, f"{minion}-forwarded"],
            }
            assert set(returner["sqlalchemy.get_jid"](jid)) == {minion}


@pytest.mark.parametrize("extra_functions", [0, 40])
def test_multifunction_return(returner, extra_functions):
    Returns = model_for("Returns")
    functions = ["test.ping", "test.echo"] + [
        f"test.function_{number}" for number in range(extra_functions)
    ]
    ret = {
        "fun": functions,
        "jid": gen_jid({}),
        "id": "multi",
        "success": {fun: fun != "test.echo" for fun in functions},
        "return": {fun: b"echo" if fun == "test.echo" else True for fun in functions},
    }
    returner["sqlalchemy.returner"](ret)
    assert returner["sqlalchemy.get_jid"](ret["jid"]) == {"multi": ret}
    with Session() as session:
        fun, success = session.execute(
            select(Returns.fun, Returns.success).where(Returns.jid == ret["jid"])
        ).one()
        assert fun == ",".join(functions)
        assert success is False


def test_expired_jid_is_not_recreated(returner):
    opts = returner["sqlalchemy.save_load"].__globals__["__opts__"]
    jid = (datetime.now(timezone.utc) - timedelta(days=1)).strftime("%Y%m%d%H%M%S%f")
    with patch.dict(opts, {"keep_jobs_seconds": 3600}):
        returner["sqlalchemy.save_load"](jid, {"expired": True})
        returner["sqlalchemy.save_minions"](jid, ["expired"])
        assert returner["sqlalchemy.get_load"](jid) == {}
        JidMinions = model_for("JidMinions")
        with Session() as session:
            assert (
                session.scalar(select(JidMinions.jid).where(JidMinions.jid == jid))
                is None
            )
    with patch.dict(opts, {"keep_jobs_seconds": 0}):
        returner["sqlalchemy.save_load"](jid, {"expired": True})
        returner["sqlalchemy.save_minions"](jid, ["retained"])
        assert returner["sqlalchemy.get_load"](jid) == {
            "expired": True,
            "Minions": ["retained"],
        }


def test_get_load_returns(returner):
    jid = gen_jid({})
    load = {"foo": "bar"}
    minions = ["minion1", "minion2"]
    returner["sqlalchemy.save_load"](jid, load, minions)
    result = returner["sqlalchemy.get_load"](jid)
    assert isinstance(result, dict)
    assert "foo" in result


def test_get_jid_returns(returner):
    jid = gen_jid({})
    ret = {"fun": "test.ping", "jid": jid, "id": "minion", "success": True}
    returner["sqlalchemy.returner"](ret)
    result = returner["sqlalchemy.get_jid"](jid)
    assert isinstance(result, dict)
    assert "minion" in result


def test_prep_jid_returns_unique(returner):
    jid1 = returner["sqlalchemy.prep_jid"]()
    jid2 = returner["sqlalchemy.prep_jid"]()
    assert jid1 != jid2


@pytest.mark.parametrize("before_load", [False, True])
def test_save_minions_preserves_load_and_merges_ids(returner, before_load):
    jid = gen_jid({})
    load = {"fun": "test.ping", "arg": []}
    if not before_load:
        returner["sqlalchemy.save_load"](jid, load, ["local", "overlap"])
    returner["sqlalchemy.save_minions"](jid, ["forwarded", "overlap", "forwarded"])
    returner["sqlalchemy.save_minions"](jid, ["other", "forwarded"], syndic_id="syndic")
    if before_load:
        assert returner["sqlalchemy.get_load"](jid) == {}
        returner["sqlalchemy.save_load"](jid, load, ["local", "overlap"])
    assert returner["sqlalchemy.get_load"](jid) == {
        **load,
        "Minions": ["local", "overlap", "forwarded", "other"],
    }
    JidMinions = model_for("JidMinions")
    with Session() as session:
        assert (
            session.scalar(
                select(func.count())
                .select_from(JidMinions)
                .where(JidMinions.jid == jid)
            )
            == 3
        )


def test_concurrent_save_minions(returner):
    jid = gen_jid({})
    returner["sqlalchemy.save_load"](jid, {"fun": "test.ping"}, ["local"])
    save = returner["sqlalchemy.save_minions"]

    def discovered(index):
        save(jid, ["shared", f"forwarded-{index}"])

    with ThreadPoolExecutor(max_workers=4) as executor:
        list(executor.map(discovered, range(4)))
    assert set(returner["sqlalchemy.get_load"](jid)["Minions"]) == {
        "local",
        "shared",
        *(f"forwarded-{index}" for index in range(4)),
    }


def test_job_reads_do_not_use_replica(returner):
    jid = gen_jid({})
    load = {"fun": "test.ping"}
    ret = {"fun": "test.ping", "jid": jid, "id": "minion", "success": True}
    returner["sqlalchemy.save_load"](jid, load, ["minion"])
    returner["sqlalchemy.returner"](ret)
    with patch("salt.sqlalchemy.ROSession", side_effect=AssertionError("Replica read")):
        assert returner["sqlalchemy.get_load"](jid) == {**load, "Minions": ["minion"]}
        assert returner["sqlalchemy.get_jid"](jid) == {"minion": ret}


def test_get_fun_raises(returner):
    with pytest.raises(Exception):
        returner["sqlalchemy.get_fun"]("test.ping")


def test_get_jids_raises(returner):
    with pytest.raises(Exception):
        returner["sqlalchemy.get_jids"]()


def test_get_minions_raises(returner):
    with pytest.raises(Exception):
        returner["sqlalchemy.get_minions"]()


def test_clean_old_jobs(master_opts, returner):
    # there might be a better way to do this
    opts = returner["sqlalchemy.clean_old_jobs"].__globals__["__opts__"]

    with patch.dict(opts, {"keep_jobs_seconds": 3600, "archive_jobs": True}):
        with pytest.raises(salt.exceptions.SaltException):
            returner["sqlalchemy.clean_old_jobs"]()

    with patch.dict(
        opts,
        {"keep_jobs_seconds": 3600, "cluster_id": "testcluster", "id": "testmaster"},
    ):
        # Insert fake data into Jids, Returns, Events
        Jids = model_for("Jids")
        JidMinions = model_for("JidMinions")
        Returns = model_for("Returns")
        Events = model_for("Events")
        #
        # delete all state so counts are correct
        with Session() as session:
            session.execute(delete(Jids))
            session.execute(delete(JidMinions))
            session.execute(delete(Returns))
            session.execute(delete(Events))
            session.commit()

        now = datetime.now(timezone.utc)
        old_time = now - timedelta(days=365)
        jid = old_time.strftime("%Y%m%d%H%M%S%f")

        with Session() as session:
            session.add(
                Jids(
                    jid=jid,
                    load={"foo": "bar"},
                    minions=["minion1"],
                    cluster="testcluster",
                    created_at=old_time,
                )
            )
            session.add(
                JidMinions(
                    jid=jid,
                    cluster="testcluster",
                    created_at=old_time,
                    minion_id="forwarded",
                )
            )
            session.add(
                Returns(
                    fun="test.ping",
                    jid=jid,
                    id="minion1",
                    success=True,
                    ret={"foo": "bar"},
                    cluster="testcluster",
                    created_at=old_time,
                )
            )
            session.add(
                Events(
                    tag="test",
                    data={"_stamp": str(old_time)},
                    master_id="testmaster",
                    cluster="testcluster",
                    created_at=old_time,
                )
            )
            session.commit()

        # Run clean_old_jobs
        returner["sqlalchemy.clean_old_jobs"]()

        # Assert all old data is deleted
        with Session() as session:
            assert session.query(Jids).count() == 0
            assert session.query(JidMinions).count() == 0
            assert session.query(Returns).count() == 0
            assert session.query(Events).count() == 0
