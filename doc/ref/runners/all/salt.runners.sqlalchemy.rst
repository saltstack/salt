salt.runners.sqlalchemy
=======================

.. automodule:: salt.runners.sqlalchemy
    :members:

Named connections can be managed without configuring a default connection::

    salt-run sqlalchemy.create_all target_engine=jobs

This selects the connection configured under ``sqlalchemy.jobs.*``. Built-in
cache and returner use still requires a default connection.

The ``sqlalchemy.sslmode``, ``sslcert``, ``sslkey``, ``sslrootcert`` and ``sslcrl``
connection settings are PostgreSQL-only. For other databases, use the driver's
DSN options or ``connect_args`` in the JSON ``sqlalchemy.engine_opts`` value.
Read connections configured through ``ro_host`` inherit these SSL settings unless
overridden with ``ro_ssl*`` settings. An explicit ``ro_dsn`` supplies its own
connection settings.

Connection pools
----------------

Set pool limits through the JSON ``sqlalchemy.engine_opts`` value, for example::

    sqlalchemy.engine_opts: '{"pool_size": 8, "max_overflow": 8, "pool_timeout": 30}'

Each engine in each worker process owns a pool. Budget up to
``pool_size + max_overflow`` connections per engine across all processes and
masters. A separate reader engine has its own pool, configured through
``sqlalchemy.ro_engine_opts``. Request executor concurrency is independent of
``worker_threads``; pool sizes are not increased automatically.
