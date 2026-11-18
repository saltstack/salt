salt.runners.sqlalchemy
=======================

.. automodule:: salt.runners.sqlalchemy
    :members:

Schema migrations
-----------------

The schema is versioned with Alembic, which must be installed on the master
running these commands. Create or upgrade the schema explicitly; masters never
migrate it at startup::

    salt-run sqlalchemy.upgrade
    salt-run sqlalchemy.current
    salt-run sqlalchemy.history

``sqlalchemy.create_all`` is equivalent to ``sqlalchemy.upgrade`` and
``sqlalchemy.drop_all`` to ``sqlalchemy.downgrade base``.

Online upgrades hold a database lock (an advisory lock on PostgreSQL, a named
lock on MySQL and MariaDB), so masters running an upgrade at the same time
apply each revision once. SQLite relies on its own file locking.

To review SQL before applying it, generate it without connecting::

    salt-run sqlalchemy.upgrade sql=True
    salt-run sqlalchemy.downgrade 0001:base sql=True

Offline SQL is not available when ``sqlalchemy.partman.enabled`` is set,
because pg_partman setup queries the installed extension.

The schema records structural settings when it is created. Upgrades refuse to
run if ``sqlalchemy.partman.enabled`` has since changed on PostgreSQL, because
converting tables to or from partitions requires a manual data migration.

``sqlalchemy.stamp`` records a revision as applied without running it, for
databases whose schema was created or repaired by hand.

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
