"""
    Test cases for salt.sqlalchemy
"""

import json

import pytest

import salt.exceptions
import salt.sqlalchemy
from tests.support.mock import ANY, MagicMock, call, patch


@pytest.fixture
def mock_engine():
    """Mock SQLAlchemy engine object"""
    mock_engine = MagicMock()
    mock_engine.dialect.name = "postgresql"

    # Mock connection and cursor for event listeners
    mock_connection = MagicMock()
    mock_cursor = MagicMock()
    mock_connection.cursor.return_value = mock_cursor
    mock_engine.connect.return_value.__enter__.return_value = mock_connection

    return mock_engine


@pytest.fixture
def dsn_opts():
    """Return opts dict with DSN configuration"""
    return {
        "sqlalchemy.dsn": "postgresql://user:pass@localhost:5432/test",
        "sqlalchemy.slow_query_threshold": 0.5,
        "sqlalchemy.slow_connect_threshold": 0.5,
    }


@pytest.fixture
def connection_opts():
    """Return opts dict with connection parameters"""
    return {
        "sqlalchemy.drivername": "postgresql",
        "sqlalchemy.host": "localhost",
        "sqlalchemy.username": "salt",
        "sqlalchemy.password": "salt",
        "sqlalchemy.database": "salt",
        "sqlalchemy.port": 5432,
        "sqlalchemy.slow_query_threshold": 0.5,
        "sqlalchemy.slow_connect_threshold": 0.5,
        "sqlalchemy.disable_connection_pool": True,
    }


@pytest.fixture
def ro_connection_opts():
    """Return opts dict with connection parameters including read-only configuration"""
    return {
        "sqlalchemy.drivername": "postgresql",
        "sqlalchemy.host": "localhost",
        "sqlalchemy.username": "salt",
        "sqlalchemy.password": "salt",
        "sqlalchemy.database": "salt",
        "sqlalchemy.port": 5432,
        "sqlalchemy.slow_query_threshold": 0.5,
        "sqlalchemy.slow_connect_threshold": 0.5,
        "sqlalchemy.ro_host": "readonly.localhost",
        "sqlalchemy.ro_username": "salt_ro",
        "sqlalchemy.ro_password": "salt_ro",
        "sqlalchemy.ro_database": "salt",
        "sqlalchemy.ro_port": 5432,
    }


@pytest.fixture
def ro_dsn_opts():
    """Return opts dict with DSN configuration including read-only DSN"""
    return {
        "sqlalchemy.dsn": "postgresql://user:pass@localhost:5432/test",
        "sqlalchemy.ro_dsn": "postgresql://reader:pass@readonly.localhost:5432/test",
        "sqlalchemy.slow_query_threshold": 0.5,
        "sqlalchemy.slow_connect_threshold": 0.5,
    }


def strip_prefix(opts):
    """
    direct calls to _make_engine do not expect prefixed opts
    """
    return {k.replace("sqlalchemy.", ""): v for k, v in opts.items()}


def test_orm_configured():
    """
    Test the orm_configured function
    """
    salt.sqlalchemy.ENGINE_REGISTRY = {}
    assert salt.sqlalchemy.orm_configured() is False
    salt.sqlalchemy.ENGINE_REGISTRY = {"default": {}}
    assert salt.sqlalchemy.orm_configured() is True


def test_make_engine_with_dsn(dsn_opts):
    """
    Test _make_engine function with DSN configuration
    """
    stripped_dsn_opts = strip_prefix(dsn_opts)
    with patch("sqlalchemy.create_engine") as mock_create_engine, patch(
        "sqlalchemy.event.listens_for"
    ):
        mock_create_engine.return_value = MagicMock()
        engine = salt.sqlalchemy._make_engine(stripped_dsn_opts)
        assert engine is mock_create_engine.return_value
        mock_create_engine.assert_called_once_with(
            stripped_dsn_opts["dsn"],
            json_serializer=ANY,
            json_deserializer=ANY,
        )


def test_make_engine_with_connection_params(connection_opts):
    """
    Test _make_engine function with connection parameters
    """
    with patch("sqlalchemy.create_engine") as mock_create_engine, patch(
        "sqlalchemy.engine.url.URL"
    ) as mock_url, patch("sqlalchemy.event.listens_for"):
        mock_url.return_value = "postgresql://salt:salt@localhost:5432/salt"
        mock_engine = MagicMock()
        mock_create_engine.return_value = mock_engine
        engine = salt.sqlalchemy._make_engine(strip_prefix(connection_opts))
        assert engine is mock_engine
        mock_url.assert_called_once()
        mock_create_engine.assert_called_once()


def test_make_engine_with_both_configurations(dsn_opts, connection_opts):
    """
    Test _make_engine with both DSN and connection parameters should raise an exception
    """
    invalid_opts = {**dsn_opts}
    invalid_opts.update(
        {
            k: v
            for k, v in connection_opts.items()
            if k != "sqlalchemy.slow_query_threshold"
        }
    )

    with pytest.raises(salt.exceptions.SaltConfigurationError):
        salt.sqlalchemy._make_engine(strip_prefix(invalid_opts))


def test_make_engine_with_missing_config():
    """
    Test _make_engine with missing required configuration should raise an exception
    """
    opts = {"host": "localhost"}  # Missing other required params
    with pytest.raises(salt.exceptions.SaltConfigurationError):
        salt.sqlalchemy._make_engine(opts)


def test_make_engine_with_schema(dsn_opts):
    """
    Test _make_engine with schema translation
    """
    with patch("sqlalchemy.create_engine") as mock_create_engine, patch(
        "sqlalchemy.event.listens_for"
    ):
        mock_engine = MagicMock()
        mock_create_engine.return_value = mock_engine
        salt.sqlalchemy._make_engine(strip_prefix(dsn_opts))

        # Verify schema translation was not set
        mock_engine.execution_options.assert_not_called()


def test_configure_orm(dsn_opts, mock_engine):
    """
    Test configure_orm function
    """
    with patch("salt.sqlalchemy._make_engine", return_value=mock_engine), patch(
        "sqlalchemy.orm.sessionmaker"
    ), patch("sqlalchemy.orm.scoped_session"), patch(
        "salt.sqlalchemy.models.populate_model_registry"
    ) as mock_populate:

        # Clear any existing registry
        salt.sqlalchemy.ENGINE_REGISTRY = {}

        salt.sqlalchemy.configure_orm(dsn_opts)

        # Check that the engine was registered
        assert "default" in salt.sqlalchemy.ENGINE_REGISTRY
        assert "engine" in salt.sqlalchemy.ENGINE_REGISTRY["default"]
        assert "session" in salt.sqlalchemy.ENGINE_REGISTRY["default"]
        assert "ro_engine" in salt.sqlalchemy.ENGINE_REGISTRY["default"]
        assert "ro_session" in salt.sqlalchemy.ENGINE_REGISTRY["default"]

        # Since dsn_opts doesn't have ro_dsn or ro_host, ro_engine should equal engine
        assert (
            salt.sqlalchemy.ENGINE_REGISTRY["default"]["engine"]
            is salt.sqlalchemy.ENGINE_REGISTRY["default"]["ro_engine"]
        )
        assert (
            salt.sqlalchemy.ENGINE_REGISTRY["default"]["session"]
            is salt.sqlalchemy.ENGINE_REGISTRY["default"]["ro_session"]
        )

        # Check that model registry was populated
        mock_populate.assert_called_once()


def test_configure_orm_with_ro_settings(ro_connection_opts, mock_engine):
    """
    Test configure_orm function with read-only configuration
    """
    # Create a separate mock for the read-only engine
    mock_ro_engine = MagicMock()
    mock_ro_engine.dialect.name = "postgresql"

    with patch("salt.sqlalchemy._make_engine") as mock_make_engine, patch(
        "sqlalchemy.orm.sessionmaker", return_value=MagicMock()
    ), patch("sqlalchemy.orm.scoped_session", return_value=MagicMock()), patch(
        "salt.sqlalchemy.models.populate_model_registry"
    ):

        # Make _make_engine return different engines based on prefix
        def side_effect_make_engine(opts, prefix=None):
            return mock_ro_engine if prefix == "ro_" else mock_engine

        mock_make_engine.side_effect = side_effect_make_engine

        # Clear any existing registry
        salt.sqlalchemy.ENGINE_REGISTRY = {}

        salt.sqlalchemy.configure_orm(ro_connection_opts)

        # Verify _make_engine was called twice - once for main engine, once for ro_engine
        assert mock_make_engine.call_count == 2

        # Check that the engines and sessions are separate
        assert "default" in salt.sqlalchemy.ENGINE_REGISTRY
        assert salt.sqlalchemy.ENGINE_REGISTRY["default"]["engine"] == mock_engine
        assert salt.sqlalchemy.ENGINE_REGISTRY["default"]["ro_engine"] == mock_ro_engine
        assert (
            salt.sqlalchemy.ENGINE_REGISTRY["default"]["engine"]
            is not salt.sqlalchemy.ENGINE_REGISTRY["default"]["ro_engine"]
        )
        assert (
            salt.sqlalchemy.ENGINE_REGISTRY["default"]["session"]
            is not salt.sqlalchemy.ENGINE_REGISTRY["default"]["ro_session"]
        )


def test_configure_orm_with_ro_dsn(ro_dsn_opts, mock_engine):
    """
    Test configure_orm function with read-only DSN configuration
    """
    # Create a separate mock for the read-only engine
    mock_ro_engine = MagicMock()
    mock_ro_engine.dialect.name = "postgresql"

    with patch("salt.sqlalchemy._make_engine") as mock_make_engine, patch(
        "sqlalchemy.orm.sessionmaker", return_value=MagicMock()
    ), patch("sqlalchemy.orm.scoped_session", return_value=MagicMock()), patch(
        "salt.sqlalchemy.models.populate_model_registry"
    ):

        # Make _make_engine return different engines based on prefix
        def side_effect_make_engine(opts, prefix=None):
            return mock_ro_engine if prefix == "ro_" else mock_engine

        mock_make_engine.side_effect = side_effect_make_engine

        # Clear any existing registry
        salt.sqlalchemy.ENGINE_REGISTRY = {}

        salt.sqlalchemy.configure_orm(ro_dsn_opts)

        # Verify _make_engine was called twice - once for main engine, once for ro_engine
        assert mock_make_engine.call_count == 2

        # Check that the engines and sessions are separate
        assert "default" in salt.sqlalchemy.ENGINE_REGISTRY
        assert salt.sqlalchemy.ENGINE_REGISTRY["default"]["engine"] == mock_engine
        assert salt.sqlalchemy.ENGINE_REGISTRY["default"]["ro_engine"] == mock_ro_engine
        assert (
            salt.sqlalchemy.ENGINE_REGISTRY["default"]["engine"]
            is not salt.sqlalchemy.ENGINE_REGISTRY["default"]["ro_engine"]
        )
        assert (
            salt.sqlalchemy.ENGINE_REGISTRY["default"]["session"]
            is not salt.sqlalchemy.ENGINE_REGISTRY["default"]["ro_session"]
        )

        # Verify that _make_engine was called with correct prefixes
        config_with_defaults = {
            **salt.sqlalchemy.SQLA_DEFAULT_OPTS,
            **strip_prefix(ro_dsn_opts),
        }

        calls = [
            call(config_with_defaults, prefix=None),
            call(config_with_defaults, prefix="ro_"),
        ]
        mock_make_engine.assert_has_calls(calls, any_order=True)


def test_configure_orm_without_ro_settings(connection_opts, mock_engine):
    """
    Test configure_orm function without read-only configuration
    """
    with patch("salt.sqlalchemy._make_engine", return_value=mock_engine), patch(
        "sqlalchemy.orm.sessionmaker", return_value=MagicMock()
    ), patch("sqlalchemy.orm.scoped_session", return_value=MagicMock()), patch(
        "salt.sqlalchemy.models.populate_model_registry"
    ):

        # Clear any existing registry
        salt.sqlalchemy.ENGINE_REGISTRY = {}

        salt.sqlalchemy.configure_orm(connection_opts)

        # Verify _make_engine was called only once
        salt.sqlalchemy._make_engine.assert_called_once()

        # Check that ro_engine and engine are the same instance
        assert "default" in salt.sqlalchemy.ENGINE_REGISTRY
        assert (
            salt.sqlalchemy.ENGINE_REGISTRY["default"]["engine"]
            == salt.sqlalchemy.ENGINE_REGISTRY["default"]["ro_engine"]
        )
        assert (
            salt.sqlalchemy.ENGINE_REGISTRY["default"]["session"]
            == salt.sqlalchemy.ENGINE_REGISTRY["default"]["ro_session"]
        )


def test_configure_orm_already_configured(dsn_opts, mock_engine):
    """
    Test configure_orm when already configured
    """
    # Simulate already configured ORM
    salt.sqlalchemy.ENGINE_REGISTRY = {"default": {"engine": mock_engine}}

    with patch("salt.sqlalchemy._make_engine") as mock_make_engine:
        salt.sqlalchemy.configure_orm(dsn_opts)
        mock_make_engine.assert_not_called()


def test_dispose_orm(mock_engine):
    """
    Test dispose_orm function
    """
    mock_session = MagicMock()
    salt.sqlalchemy.ENGINE_REGISTRY = {
        "default": {
            "engine": mock_engine,
            "session": mock_session,
            "ro_engine": mock_engine,
            "ro_session": mock_session,
        }
    }

    salt.sqlalchemy.dispose_orm()

    # Check that engine and session were disposed
    mock_engine.dispose.assert_called()
    mock_session.remove.assert_called()

    # Check that registry was cleared
    assert len(salt.sqlalchemy.ENGINE_REGISTRY) == 0


def test_reconfigure_orm(dsn_opts):
    """
    Test reconfigure_orm function
    """
    with patch("salt.sqlalchemy.dispose_orm") as mock_dispose, patch(
        "salt.sqlalchemy.configure_orm"
    ) as mock_configure:
        salt.sqlalchemy.reconfigure_orm(dsn_opts)
        mock_dispose.assert_called_once()
        mock_configure.assert_called_once_with(dsn_opts)


def test_session(mock_engine):
    """
    Test Session function
    """
    mock_session = MagicMock()
    mock_session_instance = MagicMock()
    mock_session.return_value = mock_session_instance

    salt.sqlalchemy.ENGINE_REGISTRY = {
        "default": {
            "engine": mock_engine,
            "session": mock_session,
        }
    }

    session = salt.sqlalchemy.Session()
    assert session is mock_session_instance
    mock_session.assert_called_once()

    # Test with specific engine name
    salt.sqlalchemy.ENGINE_REGISTRY["test"] = {"session": mock_session}
    session = salt.sqlalchemy.Session("test")
    assert session is mock_session_instance


def test_session_not_configured():
    """
    Test Session function with unconfigured ORM
    """
    salt.sqlalchemy.ENGINE_REGISTRY = {}

    with pytest.raises(salt.exceptions.SaltInvocationError):
        salt.sqlalchemy.Session()


def test_ro_session(mock_engine):
    """
    Test ROSession function
    """
    mock_session = MagicMock()
    mock_ro_session = MagicMock()
    mock_session_instance = MagicMock()
    mock_ro_session_instance = MagicMock()
    mock_session.return_value = mock_session_instance
    mock_ro_session.return_value = mock_ro_session_instance

    # Test with ro_session available
    salt.sqlalchemy.ENGINE_REGISTRY = {
        "default": {
            "engine": mock_engine,
            "session": mock_session,
            "ro_session": mock_ro_session,
        }
    }

    session = salt.sqlalchemy.ROSession()
    assert session is mock_ro_session_instance
    mock_ro_session.assert_called_once()

    # Test with only session available (no ro_session)
    salt.sqlalchemy.ENGINE_REGISTRY = {
        "test": {
            "engine": mock_engine,
            "session": mock_session,
        }
    }

    session = salt.sqlalchemy.ROSession("test")
    assert session is mock_session_instance


def test_ro_session_not_configured():
    """
    Test ROSession function with unconfigured ORM
    """
    salt.sqlalchemy.ENGINE_REGISTRY = {}

    with pytest.raises(salt.exceptions.SaltInvocationError):
        salt.sqlalchemy.ROSession()


def test_serialize():
    """
    Test _serialize function
    """
    # Test with normal dict
    data = {"key": "value"}
    serialized = salt.sqlalchemy._serialize(data)
    assert serialized == json.dumps(data)

    # Test with bytes
    data = b"binary data"
    serialized = salt.sqlalchemy._serialize(data)
    expected = json.dumps({"_base64": "YmluYXJ5IGRhdGE="})
    assert serialized == expected

    # Test with NUL bytes
    data = {"key": "value\u0000with\u0000nulls"}
    serialized = salt.sqlalchemy._serialize(data)
    expected = json.dumps(data).replace("\\u0000", "")
    assert serialized == expected


def test_deserialize():
    """
    Test _deserialize function
    """
    # Test with normal JSON
    data = json.dumps({"key": "value"})
    deserialized = salt.sqlalchemy._deserialize(data)
    assert deserialized == {"key": "value"}

    # Test with base64 encoded data
    data = json.dumps({"_base64": "YmluYXJ5IGRhdGE="})
    deserialized = salt.sqlalchemy._deserialize(data)
    assert deserialized == b"binary data"


def test_create_all(mock_engine):
    """
    Test create_all function
    """
    mock_session = MagicMock()
    mock_session_instance = MagicMock()
    mock_session.return_value = mock_session_instance

    salt.sqlalchemy.ENGINE_REGISTRY = {
        "default": {
            "engine": mock_engine,
            "session": mock_session,
        }
    }

    with patch("salt.sqlalchemy.Session") as mock_session_constructor, patch(
        "salt.sqlalchemy.models.model_for"
    ) as mock_model_for:
        mock_session_constructor.return_value.__enter__.return_value = (
            mock_session_instance
        )
        mock_base = MagicMock()
        mock_model_for.return_value = mock_base

        salt.sqlalchemy.create_all()

        mock_model_for.assert_called_once_with("Base", engine_name=None)
        mock_base.metadata.create_all.assert_called_once_with(
            mock_session_instance.get_bind()
        )


def test_drop_all(mock_engine):
    """
    Test drop_all function
    """
    mock_session = MagicMock()
    mock_session_instance = MagicMock()
    mock_session.return_value = mock_session_instance

    salt.sqlalchemy.ENGINE_REGISTRY = {
        "default": {
            "engine": mock_engine,
            "session": mock_session,
        }
    }

    with patch("salt.sqlalchemy.Session") as mock_session_constructor, patch(
        "salt.sqlalchemy.models.model_for"
    ) as mock_model_for:
        mock_session_constructor.return_value.__enter__.return_value = (
            mock_session_instance
        )
        mock_base = MagicMock()
        mock_model_for.return_value = mock_base

        salt.sqlalchemy.drop_all()

        mock_model_for.assert_called_once_with("Base", engine_name=None)
        mock_base.metadata.drop_all.assert_called_once_with(
            mock_session_instance.get_bind()
        )


def test_event_listeners_registered(connection_opts, mock_engine):
    """
    Test that event listeners are registered for engine
    """
    with patch("sqlalchemy.create_engine", return_value=mock_engine), patch(
        "sqlalchemy.engine.url.URL"
    ) as mock_url, patch("sqlalchemy.event.listens_for") as mock_listens_for:

        mock_url.return_value = "postgresql://salt:salt@localhost:5432/salt"

        salt.sqlalchemy._make_engine(strip_prefix(connection_opts))

        # Check that event listeners were registered
        assert mock_listens_for.call_count >= 5

        # Verify specific event listeners
        expected_events = [
            "do_connect",
            "connect",
            "checkout",
            "before_cursor_execute",
            "after_cursor_execute",
        ]

        for event_name in expected_events:
            event_registered = False
            for call_args in mock_listens_for.call_args_list:
                if call_args[0][1] == event_name:
                    event_registered = True
                    break
            assert (
                event_registered
            ), f"Event listener for {event_name} was not registered"
