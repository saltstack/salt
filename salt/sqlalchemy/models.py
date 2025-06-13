import logging
from datetime import datetime, timezone

try:
    from sqlalchemy import DDL, JSON, DateTime, Index, String, Text, event
    from sqlalchemy.dialects.mysql import JSON as MySQL_JSON
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

log = logging.getLogger(__name__)

REGISTRY = {}


class DateTimeUTC(TypeDecorator):  # type: ignore
    """Timezone Aware DateTimeUTC.

    Ensure UTC is stored in the database and that TZ aware dates are returned for all dialects.
    Accepts datetime or string (ISO8601 or dateutil formats).
    """

    impl = DateTime(timezone=True)
    cache_ok = True

    @property
    def python_type(self) -> type[datetime]:
        return datetime

    def process_bind_param(
        self, value: datetime | str | None, dialect: Dialect
    ) -> datetime | None:
        if value is None:
            return value
        if isinstance(value, str):
            value = datetime.fromisoformat(value)
        if not isinstance(value, datetime):
            raise TypeError("created_at must be a datetime or ISO 8601 string")
        if value.tzinfo is None:
            value = value.replace(tzinfo=timezone.utc)
        return value.astimezone(timezone.utc)

    def process_literal_param(self, value: datetime | None, dialect: Dialect) -> str:
        return super().process_literal_param(value, dialect)

    def process_result_value(
        self, value: datetime | None, dialect: Dialect
    ) -> datetime | None:
        if value is None:
            return value
        if isinstance(value, datetime) and value.tzinfo is None:
            return value.replace(tzinfo=timezone.utc)
        return value


def model_for(*names, engine_name=None):
    if not engine_name:
        engine_name = "default"

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
    elif engine.dialect.name == "mysql":
        return MySQL_JSON
    else:
        return JSON


def get_text_type(engine):
    if engine.dialect.name == "postgresql":
        return Text
    else:
        return String(255)


class utcnow(FunctionElement):
    type = t_DateTime()


@compiles(utcnow, "postgresql")
def postgresql_utcnow(element, compiler, **kw):
    """
    SQLAlchemy compiler function for PostgreSQL dialect.

    Generates the PostgreSQL-specific SQL expression for UTC timestamp.
    """
    return "TIMEZONE('utc', CURRENT_TIMESTAMP)"


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
    return "UTC_TIMESTAMP()"


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

    class PartmanBase(Base):
        __abstract__ = True

        @classmethod
        def __declare_last__(cls):
            after_create_ddl = DDL(
                f"""
                SELECT {opts["partman.schema"]}.create_parent(
                    p_parent_table := '%(schema)s.{cls.__tablename__}',
                    p_control := 'created_at',
                    p_interval := '{opts["partman.interval"]}',
                    p_type := 'native',
                    p_constraint_cols := '{{jid}}',
                    p_jobmon := {str(opts["partman.jobmon"]).lower()}
                )
            """
            )
            event.listen(cls.__table__, "after_create", after_create_ddl)

            if opts["partman.retention"]:
                after_create_retention_ddl = DDL(
                    f"""
                    UPDATE {opts["partman.schema"]}.part_config
                    SET retention = INTERVAL '{opts["partman.retention"]}', retention_keep_table=false
                    WHERE parent_table = '%(schema)s.{cls.__tablename__}'
                """
                )
                event.listen(cls.__table__, "after_create", after_create_retention_ddl)

            after_drop_part_config_ddl = DDL(
                f"""
                DELETE FROM {opts["partman.schema"]}.part_config where parent_table = '%(schema)s.{cls.__tablename__}'
            """
            )
            event.listen(cls.__table__, "after_drop", after_drop_part_config_ddl)

            after_drop_template_ddl = DDL(
                f"""
                DROP TABLE IF EXISTS {opts["partman.schema"]}.template_{cls.__tablename__}
            """
            )
            event.listen(cls.__table__, "after_drop", after_drop_template_ddl)

    # shortcircuit partman behavior if not turned on
    if not opts["partman.enabled"] or not is_postgres:
        PartmanBase = Base

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
        expires_at: Mapped[datetime | None] = mapped_column(DateTimeUTC)

        if is_postgres:

            @classmethod
            def __declare_last__(cls):
                ddl = DDL(
                    """
                CREATE TABLE IF NOT EXISTS %(table)s_default PARTITION OF %(table)s DEFAULT;
                CREATE TABLE IF NOT EXISTS %(table)s_keys PARTITION OF %(table)s FOR VALUES IN ('keys', 'denied_keys', 'master_keys');
                CREATE TABLE IF NOT EXISTS %(table)s_grains PARTITION OF %(table)s FOR VALUES IN ('grains');
                CREATE TABLE IF NOT EXISTS %(table)s_pillar PARTITION OF %(table)s FOR VALUES IN ('pillar');
                CREATE TABLE IF NOT EXISTS %(table)s_tokens PARTITION OF %(table)s FOR VALUES IN ('tokens');
                CREATE TABLE IF NOT EXISTS %(table)s_mine PARTITION OF %(table)s FOR VALUES IN ('mine');
            """
                )
                event.listen(cls.__table__, "after_create", ddl)

    class Events(PartmanBase):
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
        cluster: Mapped[str] = mapped_column(get_text_type(engine), nullable=True)
        created_at: Mapped[datetime | None] = mapped_column(
            "created_at",
            DateTimeUTC,
            server_default=utcnow(),
            index=True,
            nullable=False,
        )

    class Jids(PartmanBase):
        __tablename__ = "jids"
        __mapper_args__ = {"primary_key": ["created_at"]}
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

        jid: Mapped[str] = mapped_column(get_text_type(engine), index=True)
        load: Mapped[dict] = mapped_column(get_json_type(engine))
        minions: Mapped[list | None] = mapped_column(
            get_json_type(engine), default=list
        )
        cluster: Mapped[str] = mapped_column(get_text_type(engine), nullable=True)
        created_at: Mapped[datetime] = mapped_column(
            "created_at",
            DateTimeUTC,
            server_default=utcnow(),
            nullable=False,
        )

    class Returns(PartmanBase):
        __tablename__ = "returns"
        __mapper_args__ = {"primary_key": ["created_at"]}
        table_args = []
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

        fun: Mapped[str] = mapped_column(get_text_type(engine), index=True)
        jid: Mapped[str] = mapped_column(get_text_type(engine), index=True)
        id: Mapped[str] = mapped_column(get_text_type(engine), index=True)
        success: Mapped[str] = mapped_column(get_text_type(engine))
        ret: Mapped[dict] = mapped_column("ret", get_json_type(engine))
        cluster: Mapped[str] = mapped_column(get_text_type(engine), nullable=True)
        created_at: Mapped[datetime | None] = mapped_column(
            "createD_at",
            DateTimeUTC,
            server_default=utcnow(),
            nullable=False,
        )

    configure_mappers()

    REGISTRY.setdefault(name, {})
    REGISTRY[name]["Base"] = Base
    REGISTRY[name]["Returns"] = Returns
    REGISTRY[name]["Events"] = Events
    REGISTRY[name]["Cache"] = Cache
    REGISTRY[name]["Jids"] = Jids
