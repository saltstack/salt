import base64
import json
import logging
import os
import time

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

    url = None

    if opts.get(f"{prefix}dsn"):
        url = opts[f"{prefix}dsn"]

    _opts = {}

    for kw in ["drivername", "host", "username", "password", "database", "port"]:
        if opts.get(f"{prefix}{kw}"):
            _opts[kw] = opts[f"{prefix}{kw}"]
        elif prefix and kw == "drivername" and "drivername" in opts:
            # if we are ro, just take the non _ro drivername if unset. it should be the same
            _opts[kw] = opts["drivername"]
        elif not url:
            raise salt.exceptions.SaltConfigurationError(
                f"Missing required config opts parameter 'sqlalchemy.{prefix}{kw}'"
            )

    for kw in ["sslmode", "sslcert", "sslkey", "sslrootcert", "sslcrl"]:
        if f"sqlalchemy.{prefix}{kw}" in opts:
            _opts.setdefault("query", {})[kw] = opts[f"{prefix}{kw}"]

    if url and _opts:
        raise salt.exceptions.SaltConfigurationError(
            "Can define dsn, or individual attributes, but not both"
        )
    elif not url:
        _opts.setdefault("query", {})
        url = sqlalchemy.engine.url.URL(**_opts)

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

    if opts.get(f"{prefix}schema"):
        _engine = _engine.execution_options(
            schema_translate_map={None: opts[f"{prefix}schema"]}
        )

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
                opts["slow_query_threshold"],
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

    # we let certain configs in the 'default' namespace apply to all engines
    for global_default in ["echo", "slow_query_threshold"]:
        if global_default in engine_configs.get("default", {}):
            SQLA_DEFAULT_OPTS[global_default] = engine_configs["default"][
                global_default
            ]

    if not engine_configs:
        raise salt.exceptions.SaltConfigurationError(
            "Expected sqlalchemy configuration but got none."
        )

    for name, defined_config in engine_configs.items():
        engine_config = {**SQLA_DEFAULT_OPTS, **defined_config}

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
    if not name:
        name = "default"
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
    if not name:
        name = "default"
    try:
        try:
            return ENGINE_REGISTRY[name]["ro_session"]()
        except KeyError:
            return ENGINE_REGISTRY[name]["session"]()
    except KeyError:
        raise salt.exceptions.SaltInvocationError(
            f"ORM not configured for '{name}' yet. Did you forget to call salt.sqlalchemy.configure_orm?"
        )


def _serialize(data):
    """
    Serialize and base64 encode the data
    Also remove NUL bytes because they make postgres jsonb unhappy
    """
    # handle bytes input
    if isinstance(data, bytes):
        data = base64.b64encode(data).decode("ascii")
        data = {"_base64": data}

    encoded = json.dumps(data).replace("\\u0000", "")

    return encoded


def _deserialize(data):
    """
    Deserialize and base64 decode the data
    """
    inflated = json.loads(data)

    if isinstance(inflated, dict) and "_base64" in inflated:
        inflated = base64.b64decode(inflated["_base64"])

    return inflated


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
