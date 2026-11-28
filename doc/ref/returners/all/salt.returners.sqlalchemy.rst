salt.returners.sqlalchemy
==========================

.. automodule:: salt.returners.sqlalchemy
    :members:

The returner uses the default connection configured with ``sqlalchemy.dsn`` or
``sqlalchemy.drivername`` and its connection attributes. Configuring only named
connections does not provide a default for ``master_job_cache: sqlalchemy``.

Job identity and retention
--------------------------

Each JID has one load per cluster. Repeated saves preserve the first load and
published minion list. ``save_minions`` adds forwarded and syndic minions to
``jid_minions`` with duplicate identities ignored. ``get_load`` merges those
IDs with the published list, without duplicates. Additions may arrive before
the load. Job loads and returns are read from the primary even when a replica
is configured.

``jids.created_at`` and ``jid_minions.created_at`` use the UTC timestamp encoded
in the JID, including when ``unique_jid`` appends a process ID. Jobs already older than
``keep_jobs_seconds`` are not saved; setting it to zero disables this cutoff.
Returns and events retain their own timestamps.

Database JID generation uses microsecond UTC timestamps and advisory locks to
reduce simultaneous collisions. It does not reserve JIDs after releasing a lock.

PostgreSQL partitioning supports pg_partman 4.7.x and 5.x using native range
partitions. Legacy interval names such as ``weekly`` are accepted; weekly
partitions start on Monday at midnight UTC. Install the extension in the configured
``sqlalchemy.partman.schema`` before creating tables. Configure pg_partman
maintenance separately and run its maintenance sessions in UTC.
The ``jid_minions`` table uses the same partition interval and retention.
Its primary key includes ``created_at``, as required for uniqueness across
range partitions. No foreign key couples its partition lifecycle to ``jids``.
