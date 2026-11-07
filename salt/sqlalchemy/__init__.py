import base64
import json
import logging
import math
import os
import time
from collections.abc import Mapping, Sequence, Set
from datetime import date, datetime, time as datetime_time

try:
    import sqlalchemy
    import sqlalchemy.engine.url
    from sqlalchemy import event, exc
    from sqlalchemy.orm import scoped_session, sessionmaker
    from sqlalchemy.pool import NullPool

    HAS_SQLA = True
except ImportError:
    HAS_SQLA = False

import salt.config
import salt.exceptions

log = logging.getLogger(__name__)

SQLA_DEFAULT_OPTS = {
    k[len("sqlalchemy.") :]: v
    for (k, v) in salt.config.DEFAULT_MASTER_OPTS.items()
    if k.startswith("sqlalchemy")
}

ENGINE_REGISTRY = {}


def orm_configured():
    """
    Check if the ORM is configured.

    Returns:
        bool: True if the ORM has been configured, False otherwise
    """
    return bool(ENGINE_REGISTRY)


def _make_engine(opts, prefix=None):
    """
    Create and configure a SQLAlchemy engine instance.

    Creates a SQLAlchemy engine with appropriate connection settings,
    serialization functions, and event listeners for monitoring performance.
    Supports both direct DSN strings and individual connection parameters.

    Args:
        opts (dict): Configuration options dictionary with connection parameters
        prefix (str, optional): Prefix for connection parameters, used for read-only connections

    Returns:
        Engine: Configured SQLAlchemy engine instance

    Raises:
        SaltConfigurationError: When required configuration parameters are missing
    """
    if not prefix:
        prefix = ""

    url = opts.get(f"{prefix}dsn")
    fields = ("drivername", "host", "username", "password", "database", "port")
    _opts = {
        kw: opts[f"{prefix}{kw}"]
        for kw in fields
        if opts.get(f"{prefix}{kw}") is not None
    }
    if url and _opts:
        raise salt.exceptions.SaltConfigurationError(
            "Can define dsn, or individual attributes, but not both"
        )
    if not url:
        if prefix:
            for kw in fields:
                if kw not in _opts and opts.get(kw) is not None:
                    _opts[kw] = opts[kw]
        if not _opts.get("drivername"):
            raise salt.exceptions.SaltConfigurationError(
                f"Missing required config opts parameter 'sqlalchemy.{prefix}drivername'"
            )
        url = sqlalchemy.engine.url.URL.create(**_opts)
    else:
        url = sqlalchemy.engine.url.make_url(url)

    ssl_opts = {}
    for kw in ("sslmode", "sslcert", "sslkey", "sslrootcert", "sslcrl"):
        value = opts.get(f"{prefix}{kw}")
        if value is None and prefix and not opts.get(f"{prefix}dsn"):
            value = opts.get(kw)
        if value is not None:
            ssl_opts[kw] = str(value)
    if ssl_opts:
        if url.get_backend_name() != "postgresql":
            raise salt.exceptions.SaltConfigurationError(
                "SQLAlchemy sslmode, sslcert, sslkey, sslrootcert and sslcrl "
                "settings are PostgreSQL-only. Use dialect-specific DSN or "
                "engine_opts connection options for other databases."
            )
        url = url.update_query_dict(ssl_opts)

    # TODO: other pool types could be useful if we were to use threading
    engine_opts = {}
    if opts.get(f"{prefix}engine_opts"):
        try:
            engine_opts = json.loads(opts[f"{prefix}engine_opts"])
        except json.JSONDecodeError:
            log.error(
                f"Failed to deserialize {prefix}engine_opts value (%s). Did you make a typo?",
                opts[f"{prefix}engine_opts"],
            )

    if opts.get(f"{prefix}disable_connection_pool"):
        engine_opts["poolclass"] = NullPool

    _engine = sqlalchemy.create_engine(
        url,
        json_serializer=_serialize,
        json_deserializer=_deserialize,
        **engine_opts,
    )

    schema = opts.get(f"{prefix}schema") or opts.get("schema")
    if schema:
        _engine = _engine.execution_options(schema_translate_map={None: schema})

    if opts.get("echo") or os.environ.get("SQLALCHEMY_ECHO"):
        logging.getLogger("sqlalchemy.engine").setLevel(logging.INFO)

    @event.listens_for(_engine, "do_connect")
    def do_connect(dialect, connection_record, cargs, cparams):
        connection_record.info["pid"] = os.getpid()
        connection_record.info["connect_start_time"] = time.time()

    @event.listens_for(_engine, "connect")
    def connect(dbapi_connection, connection_record):
        total = time.time() - connection_record.info["connect_start_time"]
        if total >= opts["slow_connect_threshold"]:
            log.error(
                "%s Slow database connect exceeded threshold (%s s); total time: %f s",
                _engine,
                opts["slow_connect_threshold"],
                total,
            )

        if _engine.dialect.name == "sqlite":
            cursor = dbapi_connection.cursor()
            cursor.execute("PRAGMA journal_mode=WAL;")
            cursor.close()

    @event.listens_for(_engine, "checkout")
    def checkout(dbapi_connection, connection_record, connection_proxy):
        pid = os.getpid()
        if connection_record.info["pid"] != pid:
            connection_record.dbapi_connection = connection_proxy.dbapi_connection = (
                None
            )
            raise exc.DisconnectionError(
                "Connection record belongs to pid %s, "
                "attempting to check out in pid %s"
                % (connection_record.info["pid"], pid)
            )

    @event.listens_for(_engine, "before_cursor_execute")
    def before_cursor_execute(
        conn, cursor, statement, parameters, context, executemany
    ):
        conn.info.setdefault("query_start_time", []).append(time.time())

    @event.listens_for(_engine, "after_cursor_execute")
    def after_cursor_execute(conn, cursor, statement, parameters, context, executemany):
        total = time.time() - conn.info["query_start_time"].pop(-1)
        if (
            total >= opts["slow_query_threshold"]
            and "REFRESH MATERIALIZED" not in statement.upper()
        ):
            log.error(
                "%s Slow query exceeded threshold (%s s); total time: %f s,\nStatement: %s",
                _engine,
                opts["slow_query_threshold"],
                total,
                statement,
            )

    return _engine


def configure_orm(opts):
    """
    Configure the SQLAlchemy ORM with the provided options.

    Initializes SQLAlchemy engine(s) using the provided Salt configuration.
    Creates both read-write and read-only connections when configured.
    Registers models for the created engines.

    Args:
        opts (dict): Salt configuration options dictionary

    Raises:
        SaltException: When SQLAlchemy dependency is missing
        SaltConfigurationError: When required configuration is missing
    """
    if not HAS_SQLA:
        raise salt.exceptions.SaltException("Missing sqlalchemy dependency")

    # this only needs to run once
    if ENGINE_REGISTRY:
        return

    # many engines can be defined, in addition to the default
    engine_configs = {}
    for key in opts.keys():
        if not key.startswith("sqlalchemy."):
            continue

        _, _key = key.split(".", maxsplit=1)

        if _key.count(".") == 0 or _key.startswith("ddl") or _key.startswith("partman"):
            name = "default"
            engine_configs.setdefault(name, {})[_key] = opts[key]
        else:
            name, _key = _key.split(".", maxsplit=1)
            engine_configs.setdefault(name, {})[_key] = opts[key]

    global_config = engine_configs.get("default", {})
    connection_fields = (
        "dsn",
        "drivername",
        "host",
        "username",
        "password",
        "database",
        "port",
    )
    if len(engine_configs) > 1 and not any(
        global_config.get(kw) for kw in connection_fields
    ):
        engine_configs.pop("default", None)
    defaults = {**SQLA_DEFAULT_OPTS}
    for key in ("echo", "slow_query_threshold", "slow_connect_threshold"):
        if key in global_config:
            defaults[key] = global_config[key]

    if not engine_configs:
        raise salt.exceptions.SaltConfigurationError(
            "Expected sqlalchemy configuration but got none."
        )

    for name, defined_config in engine_configs.items():
        engine_config = {**defaults, **defined_config}

        _engine = _make_engine(engine_config, prefix=None)
        _Session = scoped_session(
            sessionmaker(
                autocommit=False,
                bind=_engine,
            )
        )

        # if configured for a readonly pool separate from the readwrite, configure it
        # else just alias it to the main pool
        if engine_config["ro_dsn"] or engine_config["ro_host"]:
            _ro_engine = _make_engine(engine_config, prefix="ro_")
            _ROSession = scoped_session(
                sessionmaker(
                    autocommit=False,
                    bind=_ro_engine,
                )
            )
        else:
            _ro_engine = _engine
            _ROSession = _Session

        ENGINE_REGISTRY[name] = {}
        ENGINE_REGISTRY[name]["engine"] = _engine
        ENGINE_REGISTRY[name]["session"] = _Session
        ENGINE_REGISTRY[name]["ro_engine"] = _ro_engine
        ENGINE_REGISTRY[name]["ro_session"] = _ROSession

        # the sqla models are behavior dependent on opts config
        # note this must be a late import ; salt.sqlalchemy must be importable
        # even if sqlalchemy isn't installed
        from salt.sqlalchemy.models import populate_model_registry

        populate_model_registry(engine_config, name, _engine)


def dispose_orm():
    """
    Clean up and dispose of all SQLAlchemy engine and session resources.

    Properly disposes all engine connection pools and removes session instances
    from the registry to prevent resource leaks.

    Raises:
        SaltException: When SQLAlchemy dependency is missing
    """
    if not HAS_SQLA:
        raise salt.exceptions.SaltException("Missing sqlalchemy dependency")

    if not ENGINE_REGISTRY:
        return

    for engine in list(ENGINE_REGISTRY):
        log.debug("Disposing DB connection pool for %s", engine)

        ENGINE_REGISTRY[engine]["engine"].dispose()
        ENGINE_REGISTRY[engine]["session"].remove()

        if "ro_engine" in ENGINE_REGISTRY[engine]:
            ENGINE_REGISTRY[engine]["ro_engine"].dispose()
        if "ro_session" in ENGINE_REGISTRY[engine]:
            ENGINE_REGISTRY[engine]["ro_session"].remove()

        ENGINE_REGISTRY.pop(engine)


def reconfigure_orm(opts):
    """
    Reconfigure the SQLAlchemy ORM with new options.

    Disposes of existing engine resources and then reconfigures the ORM
    with the provided options. This is useful for refreshing connections
    or updating configuration.

    Args:
        opts (dict): Salt configuration options dictionary
    """
    dispose_orm()
    configure_orm(opts)


def _engine_name(name):
    if name:
        return name
    if ENGINE_REGISTRY and "default" not in ENGINE_REGISTRY:
        raise salt.exceptions.SaltConfigurationError(
            "No default SQLAlchemy engine configured. Configure sqlalchemy.dsn "
            "or sqlalchemy.drivername for the built-in cache and returner, "
            "or explicitly select a named engine with engine_name."
        )
    return "default"


def Session(name=None):
    """
    Get a SQLAlchemy session for database operations.

    Creates and returns a new session from the appropriate session factory
    in the engine registry. Used for read-write operations on the database.

    Args:
        name (str, optional): Name of the engine to use. Defaults to "default".

    Returns:
        Session: A configured SQLAlchemy session object

    Raises:
        SaltInvocationError: When the requested engine name is not configured
    """
    name = _engine_name(name)
    try:
        return ENGINE_REGISTRY[name]["session"]()
    except KeyError:
        raise salt.exceptions.SaltInvocationError(
            f"ORM not configured for '{name}' yet. Did you forget to call salt.sqlalchemy.configure_orm?"
        )


def ROSession(name=None):
    """
    Get a read-only SQLAlchemy session for database operations.

    Creates and returns a new session from the read-only session factory
    in the engine registry. Falls back to standard session if read-only
    session is not available.

    Args:
        name (str, optional): Name of the engine to use. Defaults to "default".

    Returns:
        Session: A configured read-only SQLAlchemy session object

    Raises:
        SaltInvocationError: When the requested engine name is not configured
    """
    name = _engine_name(name)
    try:
        try:
            return ENGINE_REGISTRY[name]["ro_session"]()
        except KeyError:
            return ENGINE_REGISTRY[name]["session"]()
    except KeyError:
        raise salt.exceptions.SaltInvocationError(
            f"ORM not configured for '{name}' yet. Did you forget to call salt.sqlalchemy.configure_orm?"
        )


_JSON_TAG = "__salt_sqlalchemy__"


def _encode_json(data):
    """Keep ordinary JSON queryable and tag values it cannot represent."""
    if isinstance(data, Mapping):
        if _JSON_TAG not in data and all(
            isinstance(key, str) and "\0" not in key for key in data
        ):
            return {key: _encode_json(value) for key, value in data.items()}
        kind = "dict"
        value = [
            [_encode_json(key), _encode_json(value)] for key, value in data.items()
        ]
    elif isinstance(data, Sequence) and not isinstance(
        data, (str, bytes, bytearray, tuple)
    ):
        return [_encode_json(value) for value in data]
    elif isinstance(data, (bytes, bytearray)):
        kind = "bytes" if isinstance(data, bytes) else "bytearray"
        value = base64.b64encode(data).decode("ascii")
    elif isinstance(data, str) and "\0" in data:
        kind = "str"
        value = base64.b64encode(data.encode("utf-8")).decode("ascii")
    elif isinstance(data, (datetime, date, datetime_time)):
        kind = (
            "datetime"
            if isinstance(data, datetime)
            else "date"
            if isinstance(data, date)
            else "time"
        )
        value = data.isoformat()
    elif isinstance(data, tuple):
        kind = "tuple"
        value = [_encode_json(item) for item in data]
    elif isinstance(data, Set):
        kind = "frozenset" if isinstance(data, frozenset) else "set"
        value = [_encode_json(item) for item in data]
    elif isinstance(data, float) and not math.isfinite(data):
        kind = "float"
        value = str(data)
    else:
        return data
    return {_JSON_TAG: [kind, value]}


def _serialize(data):
    """Serialize Salt data without changing ordinary JSON field paths."""
    return json.dumps(_encode_json(data))


def _decode_json(data):
    """Restore tagged values, including dictionaries containing our tag."""
    if isinstance(data, list):
        return [_decode_json(value) for value in data]
    if not isinstance(data, dict):
        return data
    if set(data) != {_JSON_TAG}:
        return {key: _decode_json(value) for key, value in data.items()}
    kind, value = data[_JSON_TAG]
    if kind == "dict":
        return {_decode_json(key): _decode_json(value) for key, value in value}
    if kind in {"bytes", "bytearray", "str"}:
        value = base64.b64decode(value)
        if kind == "str":
            return value.decode("utf-8")
        return bytearray(value) if kind == "bytearray" else value
    if kind in {"datetime", "date", "time"}:
        return {"datetime": datetime, "date": date, "time": datetime_time}[
            kind
        ].fromisoformat(value)
    if kind == "float":
        return float(value)
    return {"tuple": tuple, "set": set, "frozenset": frozenset}[kind](
        _decode_json(item) for item in value
    )


def _deserialize(data):
    """Deserialize the queryable JSON representation of Salt data."""
    return _decode_json(json.loads(data))


def model_for(*args, **kwargs):
    """
    Get SQLAlchemy models by name from the registry.

    Acts as a pass-through to the model getter in the models module.

    Args:
        *args: Model names to retrieve
        **kwargs: Additional arguments to pass to the model getter

    Returns:
        Model or tuple of models: The requested SQLAlchemy model(s)

    Raises:
        SaltInvocationError: When SQLAlchemy is not installed
    """
    # pass through to the model getter
    # it is important this stay in this file as importing
    # salt.sqlalchemy.models requires sqlalchemy be installed
    if HAS_SQLA:
        from salt.sqlalchemy.models import model_for

        return model_for(*args, **kwargs)
    else:
        raise salt.exceptions.SaltInvocationError("SQLAlchemy must be installed")


def drop_all(engine_name=None):
    """
    Drop all tables in the database.

    Removes all tables defined in the SQLAlchemy metadata for the specified engine.

    Args:
        engine_name (str, optional): Name of the engine to use. Defaults to "default".
    """
    with Session(engine_name) as session:
        Base = model_for("Base", engine_name=engine_name)
        Base.metadata.drop_all(session.get_bind())


def create_all(engine_name=None):
    """
    Create all tables in the database.

    Creates all tables defined in the SQLAlchemy metadata for the specified engine.

    Args:
        engine_name (str, optional): Name of the engine to use. Defaults to "default".
    """
    with Session(engine_name) as session:
        Base = model_for("Base", engine_name=engine_name)
        Base.metadata.create_all(session.get_bind())
