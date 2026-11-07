import logging
from datetime import datetime, timezone
from typing import Optional, Type, Union

try:
    from sqlalchemy import (
        JSON,
        Boolean,
        CheckConstraint,
        DateTime,
        Index,
        String,
        Text,
        event,
        text,
    )
    from sqlalchemy.dialects.mysql import DATETIME as MySQL_DATETIME
    from sqlalchemy.dialects.mysql import JSON as MySQL_JSON
    from sqlalchemy.dialects.mysql import TEXT as MySQL_TEXT
    from sqlalchemy.dialects.mysql import VARCHAR as MySQL_VARCHAR
    from sqlalchemy.dialects.postgresql import JSONB
    from sqlalchemy.engine import Dialect
    from sqlalchemy.ext.compiler import compiles
    from sqlalchemy.orm import DeclarativeBase, Mapped, configure_mappers, mapped_column
    from sqlalchemy.sql.expression import FunctionElement
    from sqlalchemy.types import DateTime as t_DateTime
    from sqlalchemy.types import TypeDecorator
except ImportError:
    # stubs so below passively compiles even if sqlalchemy isn't installed
    # all consuming code is gated by salt.sqlalchemy.configure_orm
    TypeDecorator = object
    FunctionElement = object
    Dialect = None

    def DateTime(timezone=None):
        pass

    t_DateTime = DateTime

    def compiles(cls, dialect=None):
        def decorator(fn):
            return fn

        return decorator


import salt.exceptions
import salt.sqlalchemy

log = logging.getLogger(__name__)

REGISTRY = {}


class DateTimeUTC(TypeDecorator):  # type: ignore
    """Timezone Aware DateTimeUTC.

    Ensure UTC is stored in the database and that TZ aware dates are returned for all dialects.
    Accepts datetime or ISO 8601 strings.
    """

    impl = DateTime(timezone=True)
    cache_ok = True

    def __init__(self, precision=6):
        self.precision = precision
        super().__init__(timezone=True)

    def load_dialect_impl(self, dialect):
        if dialect.name in {"mysql", "mariadb"}:
            return dialect.type_descriptor(MySQL_DATETIME(fsp=self.precision))
        return dialect.type_descriptor(DateTime(timezone=True))

    @property
    def python_type(self) -> Type[datetime]:
        return datetime

    def process_bind_param(
        self, value: Union[datetime, str, None], dialect: Dialect
    ) -> Optional[datetime]:
        if value is None:
            return value
        if isinstance(value, str):
            value = datetime.fromisoformat(value.replace("Z", "+00:00"))
        if not isinstance(value, datetime):
            raise TypeError("created_at must be a datetime or ISO 8601 string")
        if value.tzinfo is None:
            value = value.replace(tzinfo=timezone.utc)
        value = value.astimezone(timezone.utc)
        if dialect.name in {"mysql", "mariadb"}:
            return value.replace(tzinfo=None)
        return value

    def process_result_value(
        self, value: Optional[datetime], dialect: Dialect
    ) -> Optional[datetime]:
        if value is None:
            return value
        if isinstance(value, datetime) and value.tzinfo is None:
            return value.replace(tzinfo=timezone.utc)
        return value.astimezone(timezone.utc)


def model_for(*names, engine_name=None):
    engine_name = salt.sqlalchemy._engine_name(engine_name)

    models = []
    for name in names:
        try:
            models.append(REGISTRY[engine_name][name])
        except KeyError:
            raise salt.exceptions.SaltInvocationError(
                f"Unrecognized model name {name}. Did you forget to call salt.sqlalchemy.configure_orm?"
            )

    if len(names) == 1:
        return models[0]
    else:
        return tuple(models)


def get_json_type(engine):
    if engine.dialect.name == "postgresql":
        return JSONB
    elif engine.dialect.name in {"mysql", "mariadb"}:
        return MySQL_JSON
    else:
        return JSON


def get_text_type(engine):
    if engine.dialect.name == "postgresql":
        return Text
    elif engine.dialect.name in {"mysql", "mariadb"}:
        return MySQL_VARCHAR(255, charset="utf8mb4", collation="utf8mb4_bin")
    else:
        return String(255)


class utcnow(FunctionElement):
    type = t_DateTime()
    inherit_cache = True


@compiles(utcnow, "postgresql")
def postgresql_utcnow(element, compiler, **kw):
    """
    SQLAlchemy compiler function for PostgreSQL dialect.

    Generates the PostgreSQL-specific SQL expression for UTC timestamp.
    """
    return "CURRENT_TIMESTAMP"


@compiles(utcnow, "mssql")
def mssql_utcnow(element, compiler, **kw):
    """
    SQLAlchemy compiler function for Microsoft SQL Server dialect.

    Generates the MSSQL-specific SQL expression for UTC timestamp.

    Args:
        element: The SQLAlchemy FunctionElement instance
        compiler: The SQLAlchemy statement compiler
        **kw: Additional keyword arguments passed to the compiler

    Returns:
        str: MSSQL-specific UTC timestamp function call
    """
    return "GETUTCDATE()"


@compiles(utcnow, "mysql")
@compiles(utcnow, "mariadb")
def myqsql_utcnow(element, compiler, **kw):
    """
    SQLAlchemy compiler function for MySQL dialect.

    Generates the MySQL-specific SQL expression for UTC timestamp.

    Args:
        element: The SQLAlchemy FunctionElement instance
        compiler: The SQLAlchemy statement compiler
        **kw: Additional keyword arguments passed to the compiler

    Returns:
        str: MySQL-specific UTC timestamp function call
    """
    return "UTC_TIMESTAMP(6)"


@compiles(utcnow, "sqlite")
def sqlite_utcnow(element, compiler, **kw):
    """
    SQLAlchemy compiler function for SQLite dialect.

    Generates the SQLite-specific SQL expression for UTC timestamp.

    Args:
        element: The SQLAlchemy FunctionElement instance
        compiler: The SQLAlchemy statement compiler
        **kw: Additional keyword arguments passed to the compiler

    Returns:
        str: SQLite-specific UTC datetime function call
    """
    return "datetime('now')"


class jid_timestamp(FunctionElement):
    """The UTC timestamp encoded in the first twenty digits of a Salt JID."""

    type = t_DateTime(timezone=True)
    inherit_cache = True


def _jid_timestamp_sql(element, compiler, **kw):
    jid = compiler.process(list(element.clauses)[0], **kw)
    parts = [(1, 4), (5, 2), (7, 2), (9, 2), (11, 2), (13, 2), (15, 6)]
    return [f"substr({jid}, {start}, {length})" for start, length in parts]


@compiles(jid_timestamp, "postgresql")
def postgresql_jid_timestamp(element, compiler, **kw):
    year, month, day, hour, minute, second, micro = _jid_timestamp_sql(
        element, compiler, **kw
    )
    value = f"{year} || '-' || {month} || '-' || {day} || ' ' || {hour} || ':' || {minute} || ':' || {second} || '.' || {micro}"
    return f"(CAST(({value}) AS timestamp) AT TIME ZONE 'UTC')"


@compiles(jid_timestamp, "mysql")
@compiles(jid_timestamp, "mariadb")
def mysql_jid_timestamp(element, compiler, **kw):
    jid = compiler.process(list(element.clauses)[0], **kw)
    fmt = compiler.render_literal_value("%Y%m%d%H%i%s%f", String())
    return f"STR_TO_DATE(substr({jid}, 1, 20), {fmt})"


@compiles(jid_timestamp, "sqlite")
def sqlite_jid_timestamp(element, compiler, **kw):
    year, month, day, hour, minute, second, micro = _jid_timestamp_sql(
        element, compiler, **kw
    )
    return f"({year} || '-' || {month} || '-' || {day} || ' ' || {hour} || ':' || {minute} || ':' || {second} || '.' || {micro})"


def _table_name(table, connection):
    schema = connection.schema_for_object(table) or connection.scalar(
        text("SELECT current_schema()")
    )
    preparer = connection.dialect.identifier_preparer
    qualified = f"{preparer.quote_schema(schema)}.{preparer.quote(table.name)}"
    return schema, qualified


def _create_cache_partitions(table, connection, **kwargs):
    schema, parent = _table_name(table, connection)
    preparer = connection.dialect.identifier_preparer
    partitions = {
        "default": None,
        "keys": "'keys', 'denied_keys', 'master_keys'",
        "grains": "'grains'",
        "pillar": "'pillar'",
        "tokens": "'tokens'",
        "mine": "'mine'",
    }
    for suffix, values in partitions.items():
        child = f"{preparer.quote_schema(schema)}.{preparer.quote(table.name + '_' + suffix)}"
        bounds = "DEFAULT" if values is None else f"FOR VALUES IN ({values})"
        connection.exec_driver_sql(
            f"CREATE TABLE IF NOT EXISTS {child} PARTITION OF {parent} {bounds}"
        )


def _create_partman_parent(table, connection, opts):
    version = connection.scalar(
        text(
            "SELECT extversion FROM pg_catalog.pg_extension WHERE extname = 'pg_partman'"
        )
    )
    if version is None:
        raise salt.exceptions.SaltConfigurationError(
            "pg_partman is enabled but not installed"
        )
    major, minor = [int(value) for value in version.split(".")[:2]]
    if major not in {4, 5} or (major == 4 and minor < 7):
        raise salt.exceptions.SaltConfigurationError(
            "Supported pg_partman versions are 4.7.x and 5.x"
        )
    schema, _ = _table_name(table, connection)
    partman = connection.dialect.identifier_preparer.quote_schema(
        opts["partman.schema"]
    )
    intervals = {
        "yearly": "1 year",
        "quarterly": "3 months",
        "monthly": "1 month",
        "weekly": "1 week",
        "daily": "1 day",
        "hourly": "1 hour",
        "half-hour": "30 minutes",
        "quarter-hour": "15 minutes",
    }
    interval = intervals.get(opts["partman.interval"], opts["partman.interval"])
    parent = f"{schema}.{table.name}"
    # pg_partman truncates timestamptz boundaries using the session time zone.
    connection.exec_driver_sql("SET LOCAL TIME ZONE 'UTC'")
    connection.execute(
        text(f"""SELECT {partman}.create_parent(
            p_parent_table := :parent,
            p_control := 'created_at',
            p_type := :partition_type,
            p_interval := CAST(:interval AS text),
            p_start_partition := CASE WHEN CAST(:interval AS interval) = INTERVAL '1 week'
                THEN (date_trunc('week', CURRENT_TIMESTAMP AT TIME ZONE 'UTC') AT TIME ZONE 'UTC')::text
                ELSE NULL END,
            p_constraint_cols := :constraint_cols,
            p_jobmon := :jobmon
        )"""),
        {
            "parent": parent,
            "partition_type": "native" if major == 4 else "range",
            "interval": interval,
            "constraint_cols": ["jid"] if "jid" in table.c else None,
            "jobmon": opts["partman.jobmon"],
        },
    )
    if opts["partman.retention"]:
        connection.execute(
            text(
                f"UPDATE {partman}.part_config SET retention = :retention, retention_keep_table = false WHERE parent_table = :parent"
            ),
            {"retention": opts["partman.retention"], "parent": parent},
        )


def _drop_partman_parent(table, connection, opts):
    schema, _ = _table_name(table, connection)
    preparer = connection.dialect.identifier_preparer
    partman = preparer.quote_schema(opts["partman.schema"])
    params = {"parent": f"{schema}.{table.name}"}
    template = connection.scalar(
        text(
            f"SELECT template_table FROM {partman}.part_config WHERE parent_table = :parent"
        ),
        params,
    )
    connection.execute(
        text(f"DELETE FROM {partman}.part_config WHERE parent_table = :parent"), params
    )
    if template:
        qualified = ".".join(
            preparer.quote(part) for part in preparer.unformat_identifiers(template)
        )
        connection.exec_driver_sql(f"DROP TABLE IF EXISTS {qualified}")


def populate_model_registry(opts, name, engine):
    """
    Creates and registers SQLAlchemy models in the global registry.

    Defines ORM models for various Salt data structures and registers them
    in the REGISTRY dictionary for later retrieval. Configures PostgreSQL
    table partitioning via pg_partman when applicable.

    Args:
        opts (dict): Salt configuration options dictionary
        name (str): Registry name, defaults to "default" if not provided
        engine: SQLAlchemy engine instance for database connections

    Returns:
        None: Models are registered in the global REGISTRY dictionary
    """
    if not name:
        name = "default"

    is_postgres = engine.dialect.name == "postgresql"

    class Base(DeclarativeBase):
        pass

    class Cache(Base):
        __tablename__ = "cache"
        table_args = []
        if is_postgres:
            table_args.append(
                Index(
                    None,
                    "data",
                    postgresql_using="gin",
                    postgresql_with={"FASTUPDATE": "OFF"},
                )
            )
        table_args.append({"postgresql_partition_by": "LIST (bank)"})
        __table_args__ = tuple(table_args)

        bank: Mapped[str] = mapped_column(
            get_text_type(engine), primary_key=True, index=True
        )
        key: Mapped[str] = mapped_column(
            get_text_type(engine), primary_key=True, index=True
        )
        data: Mapped[dict] = mapped_column(get_json_type(engine))
        cluster: Mapped[str] = mapped_column(get_text_type(engine), primary_key=True)
        created_at: Mapped[datetime] = mapped_column(
            DateTimeUTC(6),
            server_default=utcnow(),
            nullable=False,
        )
        expires_at: Mapped[Optional[datetime]] = mapped_column(DateTimeUTC)

    class Events(Base):
        __tablename__ = "events"
        __mapper_args__ = {"primary_key": ["created_at"]}
        table_args = []
        if is_postgres:
            table_args.append(
                Index(
                    None,
                    "data",
                    postgresql_using="gin",
                    postgresql_with={"FASTUPDATE": "OFF"},
                )
            )

            if opts["partman.enabled"]:
                table_args.append({"postgresql_partition_by": "RANGE (created_at)"})
        __table_args__ = tuple(table_args) if table_args else ()

        tag: Mapped[str] = mapped_column(get_text_type(engine), index=True)
        data: Mapped[dict] = mapped_column(get_json_type(engine))
        master_id: Mapped[str] = mapped_column(get_text_type(engine))
        cluster: Mapped[str] = mapped_column(get_text_type(engine), nullable=False)
        created_at: Mapped[Optional[datetime]] = mapped_column(
            "created_at",
            DateTimeUTC,
            server_default=utcnow(),
            index=True,
            nullable=False,
        )

    class Jids(Base):
        __tablename__ = "jids"
        table_args = []
        if is_postgres:
            table_args.append(
                Index(
                    None,
                    "load",
                    postgresql_using="gin",
                    postgresql_with={"FASTUPDATE": "OFF"},
                )
            )

            if opts["partman.enabled"]:
                table_args.append(
                    {
                        "postgresql_partition_by": "RANGE (created_at)",
                    },
                )
        __table_args__ = tuple(table_args) if table_args else ()

        jid: Mapped[str] = mapped_column(get_text_type(engine), primary_key=True)
        load: Mapped[dict] = mapped_column(get_json_type(engine))
        minions: Mapped[Optional[list]] = mapped_column(
            get_json_type(engine), default=list
        )
        cluster: Mapped[str] = mapped_column(get_text_type(engine), primary_key=True)
        created_at: Mapped[datetime] = mapped_column(
            "created_at",
            DateTimeUTC,
            primary_key=True,
            index=True,
        )

    class Returns(Base):
        __tablename__ = "returns"
        __mapper_args__ = {"primary_key": ["created_at"]}
        table_args = [Index(None, "fun", mysql_length=255, mariadb_length=255)]
        if is_postgres:
            table_args.append(
                Index(
                    None,
                    "ret",
                    postgresql_using="gin",
                    postgresql_with={"FASTUPDATE": "OFF"},
                )
            )
            if opts["partman.enabled"]:
                table_args.append(
                    {
                        "postgresql_partition_by": "RANGE (created_at)",
                    }
                )
        __table_args__ = tuple(table_args) if table_args else ()

        fun: Mapped[str] = mapped_column(
            Text().with_variant(
                MySQL_TEXT(charset="utf8mb4", collation="utf8mb4_bin"),
                "mysql",
                "mariadb",
            )
        )
        jid: Mapped[str] = mapped_column(get_text_type(engine), index=True)
        id: Mapped[str] = mapped_column(get_text_type(engine), index=True)
        success: Mapped[bool] = mapped_column(Boolean)
        ret: Mapped[dict] = mapped_column("ret", get_json_type(engine))
        cluster: Mapped[str] = mapped_column(get_text_type(engine), nullable=False)
        created_at: Mapped[Optional[datetime]] = mapped_column(
            "created_at",
            DateTimeUTC,
            server_default=utcnow(),
            index=True,
            nullable=False,
        )

    Jids.__table__.append_constraint(
        CheckConstraint(
            (Jids.created_at == jid_timestamp(Jids.jid))
            & jid_timestamp(Jids.jid).is_not(None),
            name="jids_timestamp_matches_jid",
        )
    )
    if is_postgres:
        event.listen(Cache.__table__, "after_create", _create_cache_partitions)
        if opts["partman.enabled"]:
            for model in (Events, Jids, Returns):
                event.listen(
                    model.__table__,
                    "after_create",
                    lambda table, connection, **kw: _create_partman_parent(
                        table, connection, opts
                    ),
                )
                event.listen(
                    model.__table__,
                    "after_drop",
                    lambda table, connection, **kw: _drop_partman_parent(
                        table, connection, opts
                    ),
                )

    configure_mappers()

    REGISTRY.setdefault(name, {})
    REGISTRY[name]["Base"] = Base
    REGISTRY[name]["Returns"] = Returns
    REGISTRY[name]["Events"] = Events
    REGISTRY[name]["Cache"] = Cache
    REGISTRY[name]["Jids"] = Jids
