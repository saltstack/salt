from contextlib import contextmanager
from types import SimpleNamespace

import pytest

import salt.cache.sqlalchemy as cache
import salt.sqlalchemy
from salt.exceptions import SaltCacheError
from tests.support.mock import MagicMock, patch

sqlalchemy = pytest.importorskip("sqlalchemy")


@pytest.fixture
def database(tmp_path):
    from salt.sqlalchemy import models

    with patch.dict(salt.sqlalchemy.ENGINE_REGISTRY, {}, clear=True), patch.dict(
        models.REGISTRY, {}, clear=True
    ):
        salt.sqlalchemy.configure_orm(
            {"sqlalchemy.dsn": f"sqlite:///{tmp_path / 'cache.db'}"}
        )
        salt.sqlalchemy.create_all()
        try:
            yield salt.sqlalchemy.ENGINE_REGISTRY["default"]["engine"]
        finally:
            salt.sqlalchemy.dispose_orm()


def test_native_overwrite_does_not_raise_integrity_errors(database):
    errors = []
    sqlalchemy.event.listen(database, "handle_error", errors.append)
    cache.store("bank", "key", "old", cluster_id="cluster")
    cache.store("bank", "key", "new", cluster_id="cluster")
    assert cache.fetch("bank", "key", cluster_id="cluster") == "new"
    assert errors == []


@pytest.fixture
def generic_session(database):
    make_session = salt.sqlalchemy.Session

    @contextmanager
    def session_factory(engine_name=None):
        with make_session(engine_name) as session:
            yield SimpleNamespace(
                bind=SimpleNamespace(dialect=SimpleNamespace(name="generic")),
                execute=session.execute,
                scalar=session.scalar,
                rollback=session.rollback,
                commit=session.commit,
            )

    return session_factory


def test_fallback_does_not_lose_write_when_cleanup_removes_row(
    database, generic_session
):
    Cache = salt.sqlalchemy.model_for("Cache")
    cache.store("bank", "key", "old", cluster_id="cluster")
    removed = []

    @contextmanager
    def cleanup_before_update(engine_name=None):
        with generic_session(engine_name) as session:
            execute = session.execute

            def execute_after_cleanup(statement):
                if isinstance(statement, sqlalchemy.sql.dml.Update) and not removed:
                    execute(sqlalchemy.delete(Cache))
                    session.commit()
                    removed.append(True)
                return execute(statement)

            session.execute = execute_after_cleanup
            yield session

    with patch("salt.sqlalchemy.Session", cleanup_before_update):
        cache.store("bank", "key", "new", cluster_id="cluster")
    assert removed
    assert cache.fetch("bank", "key", cluster_id="cluster") == "new"


def test_fallback_preserves_unrelated_integrity_error(database, generic_session):
    with patch("salt.sqlalchemy.Session", generic_session), pytest.raises(
        sqlalchemy.exc.IntegrityError
    ):
        cache.store("bank", "key", "invalid null cluster", cluster_id=None)


@pytest.mark.parametrize("succeeds", [False, True])
def test_fallback_bounds_retries_for_concurrent_creation(database, succeeds):
    session = MagicMock()
    session.bind.dialect.name = "generic"
    error = sqlalchemy.exc.IntegrityError("INSERT", {}, RuntimeError("duplicate"))
    session.scalar.return_value = "key"
    session.execute.side_effect = (
        [SimpleNamespace(rowcount=0), error, SimpleNamespace(rowcount=1)]
        if succeeds
        else [SimpleNamespace(rowcount=0), error] * 3
    )
    with patch("salt.sqlalchemy.Session") as factory:
        factory.return_value.__enter__.return_value = session
        if succeeds:
            cache.store("bank", "key", "new", cluster_id="cluster")
            session.commit.assert_called_once_with()
            assert session.rollback.call_count == 1
        else:
            with pytest.raises(sqlalchemy.exc.IntegrityError) as raised:
                cache.store("bank", "key", "new", cluster_id="cluster")
            assert raised.value is error
            session.commit.assert_not_called()
            assert session.rollback.call_count == 3


def test_fallback_rejects_unknown_affected_row_count(database):
    session = MagicMock()
    session.bind.dialect.name = "generic"
    session.execute.return_value.rowcount = -1
    with patch("salt.sqlalchemy.Session") as factory:
        factory.return_value.__enter__.return_value = session
        with pytest.raises(SaltCacheError, match="row count"):
            cache.store("bank", "key", "new", cluster_id="cluster")
    session.commit.assert_not_called()
