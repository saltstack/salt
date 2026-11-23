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

Grain and pillar targeting on PostgreSQL
----------------------------------------

With ``minion_data_cache`` enabled on PostgreSQL, grain and pillar targets
(``-G``, ``-P``, ``-I``, ``-J`` and those engines in compound targets) are
answered from an index instead of reading every cached document. When a master
stores grains or pillar, it records what Salt's matcher could match in the
document as an array of terms: values and list members at each path,
dictionary keys, and markers for data the terms cannot describe. A GIN index
over ``array_to_tsvector(terms)`` on each bank partition serves the lookup; it
treats each term as one lexeme, so it finds exact terms and terms starting
with a given prefix of any length.

Results always equal Salt's Python matcher. Documents a term proves to match
are returned directly; documents the terms cannot decide, such as ones with
lists of dictionaries, floats, or a glob with wildcards inside it, are fetched
and checked with the matcher. Targets the terms cannot restrict at all, such
as ``*:`` wildcard path segments, scan the cached data; each such fallback is
logged at info level and counted by the ``salt.targeting.sql.fallback``
metric with the reason. Exact values, list members, key existence, and globs
or regular expressions that are a literal followed by a trailing wildcard
(``ubu*``, ``ubu.*``) are answered by the index alone. Other globs and regular
expressions check every document whose value starts with their literal start;
those with no literal start, such as ``*buntu``, check every document with the
path, and remain slow on large fleets.

Checks and scans fetch only the top-level keys the target can read, but still
cost roughly a millisecond per minion they examine; a target on a path without
terms scans every minion that has the path's first key.

A document whose terms would exceed about 1 MB, the limit of a PostgreSQL
``tsvector``, stores only a marker and is checked with the matcher for every
target.

Choosing indexed paths
~~~~~~~~~~~~~~~~~~~~~~

By default every grain and pillar path has terms. The index costs roughly the
number of distinct values per minion: values unique to each host, such as
serial numbers or inventory records, are the most expensive and rarely
targeted. Two settings choose what is indexed:

.. code-block:: yaml

    # leave subtrees out of the index
    sqlalchemy.term_exclude:
      - sor
      - cpu_flags

    # or index only these subtrees
    sqlalchemy.term_paths:
      - os
      - roles
      - bb:bbcpu

Paths use ``:`` between keys. Targets reading a path without terms still match
correctly by scanning. On synthetic grains shaped like a large production
fleet, 41 KB per minion with about 2,100 leaves, indexing everything cost about
145 KB per minion; excluding one large inventory subtree cut that to about
24 KB per minion, or 23 GB for one million minions.

Each row records a fingerprint of the configuration its terms were built
with, and rows built with another configuration are always rechecked until a
master stores them again, so targeting stays correct after changing either
setting, only slower.

Upgrading
~~~~~~~~~

``salt-run sqlalchemy.upgrade`` adds the terms (migration ``0002``) and
computes them for existing rows. Offline upgrades (``sql=True``) cannot compute
terms; rows without terms are rechecked on every lookup until a master stores
them again.
