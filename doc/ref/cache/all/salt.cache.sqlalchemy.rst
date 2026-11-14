salt.cache.sqlalchemy
======================

.. automodule:: salt.cache.sqlalchemy
    :members:

``cache: sqlalchemy`` uses the default connection configured with
``sqlalchemy.dsn`` or ``sqlalchemy.drivername`` and its connection attributes.
Named connections do not automatically become the default. Python callers may
select one explicitly with ``salt.cache.Cache(opts, engine_name="jobs")``.

Writes use atomic upserts on PostgreSQL, SQLite, MySQL and MariaDB. Overwrites
replace the value and expiry and refresh the cache timestamp; writing without
an expiry clears a previous expiry. Other dialects use a checked update/insert
fallback with at most three attempts for concurrent key creation. Failed writes
raise rather than report success after updating no rows.

Read replicas
-------------

When ``sqlalchemy.ro_*`` configures a replica, only banks rooted at ``grains``,
``pillar`` or ``mine`` use it. All other banks, including keys, tokens, cluster
consensus state and unknown banks, read from the primary. This avoids replica
lag hiding committed authentication or consensus updates. Root-bank listings
also use the primary.

``list_all(bank)`` returns decoded data for live entries in the exact bank,
isolated by cluster. Both values of ``include_data`` return the full data.
Standalone masters use the reserved cluster identity ``__standalone__``;
the valid cluster name ``null`` remains separate.

JSON storage
------------

Ordinary string-key dictionaries, lists and scalar values retain their JSON
structure, so fields such as grains remain queryable through SQL JSON operators.
Values JSON cannot represent directly, including bytes, sets, dates, non-string
dictionary keys and strings containing NUL, use reversible tagged objects.
Dictionaries containing the reserved ``__salt_sqlalchemy__`` key are escaped.
