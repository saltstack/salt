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
