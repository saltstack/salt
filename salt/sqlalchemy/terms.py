"""
Flatten cached grains and pillar into searchable terms, and compile targets
into term lookups.

Each document is stored with an array of strings describing what Salt's
``subdict_match`` can match in it. A target compiles into two term sets:

* ``certain`` terms: a document containing one matches the target.
* ``candidate`` terms: a document containing one may match, and is checked
  with ``subdict_match``.

A document matching the target always contains a certain or candidate term,
so a lookup returns exactly the matching documents. Targets the terms cannot
restrict compile to a ``fallback`` reason and are matched by scanning.

Only PostgreSQL stores and uses terms. TODO: MySQL 8.0.17+ could index
exact terms with a multi-valued index on ``CAST(terms AS CHAR(200) ARRAY)``
queried through ``JSON_OVERLAPS``, falling back to scans for prefixes.
Check index use at scale, the ~64 KB per-row cap on indexed values, and
use a writer flag that cannot leak across pooled sessions. MariaDB has no
multi-valued indexes.

Term layout: a kind character, ``SEP`` before each path segment, then
``VALUE_SEP`` and the value where the kind has one. Paths keep the case of
dictionary keys, which traversal matches exactly; values and keys matched
at the end of a path are lowercased like ``subdict_match`` does.

``sqlalchemy.term_paths`` limits terms to listed subtrees and
``sqlalchemy.term_exclude`` leaves subtrees out. Targets reading a path
without terms are matched by scanning. Each row records the fingerprint of
the configuration its terms were built with; rows built with another
configuration are always rechecked.
"""

import functools
import hashlib
import json
from typing import NamedTuple, Optional

import salt.utils.args

SEP = "\x1f"
VALUE_SEP = "\x1e"
# Banks whose cache rows carry terms.
BANKS = ("grains", "pillar")
# Terms longer than this are stored as a digest to fit index entry limits.
MAX_TERM = 200
# array_to_tsvector addresses lexeme text with 20-bit offsets, so documents
# whose terms pass 1 MiB would be indexed with corrupted terms rather than
# rejected. Larger documents keep only the recheck marker.
MAX_TERMS_BYTES = 1_000_000
# Bound on the number of path interpretations a target expands into.
MAX_READINGS = 64
# Changes whenever the meaning of terms changes, invalidating stored terms.
VERSION = 1
# Writers maintaining terms set this for their transaction; see
# trigger_statements.
WRITER_SETTING = "salt.cache_terms"
GUARD = "salt_cache_terms_guard"

VALUE = "v"  # scalar value or list member at a path
KEY = "k"  # dictionary key at a path
LIST = "l"  # a list at a path, which traversal can index or search
NESTED = "n"  # a list at a path holding dictionaries or lists
RECHECK = "r"  # the document holds data terms cannot describe
UNCERTAIN = "u"  # a value at a path may read back differently from storage
LONG = "x"  # a value or key at a path was digested, so prefixes cannot find it

_GLOB = "*?["
_REGEX = ".^$*+?{}[]\\|()"


def _encode(kind, path=(), value=None):
    text = kind + "".join(SEP + segment for segment in path)
    if value is not None:
        text += VALUE_SEP + value
    return text


def _digest(text):
    if len(text) > MAX_TERM:
        return "h" + hashlib.sha256(text.encode("utf-8")).hexdigest()
    return text


def term(kind, path=(), value=None):
    """Encode one term."""
    return _digest(_encode(kind, path, value))


def _add_term(terms, kind, path, value):
    """Add a value or key term, marking the path when it must be digested."""
    text = _encode(kind, path, value)
    if len(text) > MAX_TERM:
        terms.add(term(LONG, path))
    terms.add(_digest(text))


def _plain(text):
    # PostgreSQL text cannot hold NUL.
    return SEP not in text and VALUE_SEP not in text and "\0" not in text


class Paths(NamedTuple):
    """Which document paths carry terms."""

    # None indexes every path; otherwise only these subtrees.
    include: Optional[tuple]
    exclude: tuple = ()
    fingerprint: str = ""

    def covered(self, path):
        """Whether the node at ``path`` and its subtree have terms."""
        if any(path[: len(prefix)] == prefix for prefix in self.exclude):
            return False
        if self.include is None:
            return True
        return any(path[: len(prefix)] == prefix for prefix in self.include)

    def leads_to_covered(self, path):
        """
        Whether ``path`` is an ancestor of an included subtree.

        Ancestors carry terms for their own value, list members and keys, but
        not for children outside the included subtrees.
        """
        return self.include is not None and any(
            len(prefix) > len(path) and prefix[: len(path)] == path
            for prefix in self.include
            if not any(prefix[: len(other)] == other for other in self.exclude)
        )


def _parse_paths(value, setting):
    if value is None:
        return None
    if isinstance(value, str) or not all(isinstance(item, str) for item in value):
        raise ValueError(f"sqlalchemy.{setting} must be a list of paths")
    # Paths use the default delimiter, like grain targets.
    return tuple(sorted({tuple(item.split(":")) for item in value}))


@functools.lru_cache(maxsize=8)
def _paths(include, exclude):
    included = _parse_paths(include, "term_paths")
    excluded = _parse_paths(exclude, "term_exclude") or ()
    fingerprint = hashlib.sha256(
        json.dumps([VERSION, included, excluded]).encode("utf-8")
    ).hexdigest()[:16]
    return Paths(included, excluded, fingerprint)


def paths(config):
    """Return the term paths from an engine configuration."""
    include = config.get("term_paths")
    exclude = config.get("term_exclude") or ()
    if isinstance(include, str) or isinstance(exclude, str):
        raise ValueError("sqlalchemy.term_paths and term_exclude must be lists")
    return _paths(
        None if include is None else tuple(include),
        tuple(exclude),
    )


ALL = _paths(None, ())


def flatten(data, paths=ALL):
    """Return the sorted terms describing a grains or pillar document."""
    terms = set()

    def scalar(value, path):
        if isinstance(value, (float, set, frozenset)):
            # JSONB normalizes numbers (-0.0 reads back as 0.0, 1e+20 as an
            # integer), and str() of a set depends on hash order, so the value
            # the matcher later reads can differ from this one.
            terms.add(term(UNCERTAIN, path))
            return
        text = str(value).lower()
        if not _plain(text):
            terms.add(RECHECK)
            return
        _add_term(terms, VALUE, path, text)

    def walk(node, path):
        if not (paths.covered(path) or paths.leads_to_covered(path)):
            return
        if isinstance(node, dict):
            for key, value in node.items():
                if not isinstance(key, str) or not _plain(key):
                    # Traversal reaches non-string keys through YAML parsing.
                    terms.add(RECHECK)
                    continue
                _add_term(terms, KEY, path, key.lower())
                walk(value, path + (key,))
        elif isinstance(node, (list, tuple)):
            terms.add(term(LIST, path))
            for member in node:
                if isinstance(member, (dict, list, tuple)):
                    terms.add(term(NESTED, path))
                else:
                    scalar(member, path)
        else:
            scalar(node, path)

    if isinstance(data, dict):
        walk(data, ())
    else:
        terms.add(RECHECK)
    # A character is at most four UTF-8 bytes; only count bytes near the limit.
    if sum(map(len, terms)) * 4 > MAX_TERMS_BYTES and (
        sum(len(entry.encode("utf-8")) for entry in terms) > MAX_TERMS_BYTES
    ):
        return [RECHECK]
    return sorted(terms)


class Plan(NamedTuple):
    certain: frozenset = frozenset()
    candidates: frozenset = frozenset()
    # Terms that match any stored term starting with them.
    certain_prefixes: frozenset = frozenset()
    candidate_prefixes: frozenset = frozenset()
    # First path segments subdict_match can read, for fetching rechecks.
    keys: frozenset = frozenset()
    fallback: Optional[str] = None
    never: bool = False


class _Fallback(Exception):
    pass


def _readings(prefix, expr, delimiter, out):
    """Collect the (path, pattern) pairs subdict_match tries for ``expr``."""
    tokens = expr.split(delimiter)
    for idx in range(len(tokens) - 1, 0, -1):
        key = delimiter.join(tokens[:idx])
        if key == "*":
            raise _Fallback("wildcard-root")
        pattern = delimiter.join(tokens[idx:])
        if pattern.startswith("*:"):
            raise _Fallback("wildcard-segment")
        path = prefix + tuple(key.split(delimiter))
        out.append((path, pattern))
        if len(out) > MAX_READINGS:
            raise _Fallback("too-many-readings")
        if delimiter != ":":
            # Dictionaries also match the rest with the default delimiter.
            # With ":" itself, the outer loop already produced those readings.
            _readings(path, pattern, ":", out)


def _path_variants(path):
    """Literal path first, then paths through YAML-normalized keys."""
    variants = [()]
    for segment in path:
        options = [segment]
        loaded = salt.utils.args.yamlify_arg(segment)
        if loaded != segment and isinstance(loaded, str) and _plain(loaded):
            options.append(loaded)
        variants = [variant + (option,) for variant in variants for option in options]
        if len(variants) > MAX_READINGS:
            raise _Fallback("too-many-readings")
    return variants


def _literal_prefix(pattern, regex):
    """Return the literal start of a glob or regex and whether that is all."""
    if not regex:
        for idx, char in enumerate(pattern):
            if char in _GLOB:
                rest = pattern[idx:]
                return pattern[:idx], rest == "*"
        return pattern, True
    if "|" in pattern:
        return "", False
    for idx, char in enumerate(pattern):
        if char in _REGEX:
            literal = pattern[:idx]
            if char in "*?{":
                # The quantifier makes the preceding character optional.
                return literal[:-1], False
            return literal, pattern[idx:] == ".*"
    # re.match is anchored only at the start.
    return pattern, True


def compile_target(
    expr, delimiter=":", regex_match=False, exact_match=False, paths=ALL
):
    """Compile a grain or pillar target into a lookup plan."""
    if not isinstance(expr, str) or not isinstance(delimiter, str) or not delimiter:
        return Plan(fallback="unsupported-arguments")
    if "*" in delimiter:
        return Plan(fallback="wildcard-delimiter")
    if not _plain(expr):
        return Plan(fallback="unsupported-characters")
    if delimiter not in expr:
        return Plan(never=True)
    readings = []
    try:
        _readings((), expr, delimiter, readings)
        certain, candidates = set(), {RECHECK}
        prefixes = {"certain": set(), "candidates": set()}
        keys = set()
        for path, pattern in readings:
            for variant in _path_variants(path):
                if not (paths.covered(variant) or paths.leads_to_covered(variant)):
                    raise _Fallback("path-not-indexed")
                exact = variant == path
                keys.add(variant[0])
                _pattern_terms(
                    variant,
                    pattern,
                    exact,
                    regex_match,
                    exact_match,
                    certain,
                    candidates,
                    prefixes,
                )
                # Traversal searches and indexes lists along the path.
                for end in range(1, len(variant)):
                    candidates.add(term(LIST, variant[:end]))
                candidates.add(term(NESTED, variant))
                candidates.add(term(UNCERTAIN, variant))
    except _Fallback as exc:
        return Plan(fallback=str(exc))
    return Plan(
        certain=frozenset(certain),
        candidates=frozenset(candidates - certain),
        certain_prefixes=frozenset(prefixes["certain"]),
        candidate_prefixes=frozenset(prefixes["candidates"] - prefixes["certain"]),
        keys=frozenset(keys),
    )


def _pattern_terms(
    path, pattern, exact, regex_match, exact_match, certain, candidates, prefixes
):
    lowered = pattern.lower()
    sure = certain if exact else candidates
    # The node at the path exists: any non-empty dictionary matches "*".
    exists = term(KEY, path[:-1], path[-1].lower())
    if lowered == "*":
        candidates.add(exists)
    if regex_match or (not exact_match and any(char in lowered for char in _GLOB)):
        literal, complete = _literal_prefix(lowered, regex_match)
        searchable = [_encode(kind, path, literal) for kind in (VALUE, KEY)]
        if not literal or any(len(text) > MAX_TERM for text in searchable):
            candidates.add(exists)
            return
        # Values and keys starting with the literal. When the pattern is only
        # the literal and a trailing wildcard, those are exactly the matches.
        found = prefixes["certain" if exact and complete else "candidates"]
        found.update(searchable)
        # Digested values and keys cannot be found by prefix.
        candidates.add(term(LONG, path))
        return
    sure.add(term(VALUE, path, lowered))
    sure.add(term(KEY, path, lowered))


def index_statements(preparer, schema, banks=BANKS, concurrently=False):
    """
    Return DDL indexing terms on each bank partition.

    A GIN index answers term lookups. An index on the configuration
    fingerprint finds rows whose terms are missing or were built with another
    configuration, which lookups recheck.
    """
    prefix = f"{preparer.quote_schema(schema)}." if schema else ""
    statements = []
    for bank in banks:
        partition = f"cache_{bank}"
        table = prefix + preparer.quote(partition)
        create = "CREATE INDEX CONCURRENTLY" if concurrently else "CREATE INDEX"
        # Each term becomes one lexeme, verbatim, so the index answers exact
        # terms and prefix searches of any length.
        statements.append(
            f"{create} IF NOT EXISTS {preparer.quote(f'ix_{partition}_terms')} "
            f"ON {table} USING gin (array_to_tsvector(terms)) "
            f"WITH (fastupdate = off)"
        )
        statements.append(
            f"{create} IF NOT EXISTS "
            f"{preparer.quote(f'ix_{partition}_terms_config')} "
            f"ON {table} (terms_config)"
        )
    return statements


def _qualify(preparer, schema, name):
    prefix = f"{preparer.quote_schema(schema)}." if schema else ""
    return prefix + preparer.quote(name)


def trigger_statements(preparer, schema, banks=BANKS):
    """
    Return DDL clearing terms that a write did not maintain.

    A master without term support, such as one not yet upgraded, updates
    data but leaves the terms describing the old data. Writers maintaining
    terms set ``WRITER_SETTING`` for their transaction; other updates of data
    clear the terms so lookups recheck the row.
    """
    function = _qualify(preparer, schema, GUARD)
    statements = [
        f"""
        CREATE OR REPLACE FUNCTION {function}() RETURNS trigger
        LANGUAGE plpgsql AS $$
        BEGIN
            IF current_setting('{WRITER_SETTING}', true) IS DISTINCT FROM 'on'
               AND NEW.data IS DISTINCT FROM OLD.data THEN
                NEW.terms := NULL;
                NEW.terms_config := NULL;
            END IF;
            RETURN NEW;
        END
        $$
        """
    ]
    for bank in banks:
        table = _qualify(preparer, schema, f"cache_{bank}")
        statements.append(f"DROP TRIGGER IF EXISTS {preparer.quote(GUARD)} ON {table}")
        statements.append(
            f"CREATE TRIGGER {preparer.quote(GUARD)} BEFORE UPDATE OF data "
            f"ON {table} FOR EACH ROW EXECUTE FUNCTION {function}()"
        )
    return statements


def drop_trigger_statements(preparer, schema, banks=BANKS):
    """Return DDL removing the triggers and function trigger_statements makes."""
    statements = [
        f"DROP TRIGGER IF EXISTS {preparer.quote(GUARD)} "
        f"ON {_qualify(preparer, schema, f'cache_{bank}')}"
        for bank in banks
    ]
    statements.append(f"DROP FUNCTION IF EXISTS {_qualify(preparer, schema, GUARD)}()")
    return statements


def rebuild(connection, schema, paths, banks=BANKS, stale_only=True, batch=1000):
    """
    Compute terms for cached grains and pillar, returning rows processed per bank.

    ``connection`` must autocommit, so each batch commits on its own rather
    than rewriting every row in one transaction. With ``stale_only``, rows
    whose terms match ``paths`` are left alone. A row a master stores while
    this runs keeps the terms that master wrote.
    """
    import sqlalchemy as sa
    from sqlalchemy.dialects.postgresql import ARRAY, JSONB

    cache = sa.table(
        "cache",
        sa.column("bank", sa.Text),
        sa.column("key", sa.Text),
        sa.column("cluster", sa.Text),
        sa.column("data", JSONB),
        sa.column("created_at"),
        sa.column("terms", ARRAY(sa.Text)),
        sa.column("terms_config", sa.Text),
        schema=schema,
    )
    update = (
        sa.update(cache)
        .where(
            cache.c.bank == sa.bindparam("b_bank"),
            cache.c.cluster == sa.bindparam("b_cluster"),
            cache.c.key == sa.bindparam("b_key"),
            # Stores refresh created_at, so a changed row is not overwritten.
            cache.c.created_at == sa.bindparam("b_seen"),
        )
        .values(terms=sa.bindparam("b_terms"), terms_config=paths.fingerprint)
    )
    rebuilt = {}
    for bank in banks:
        rebuilt[bank] = 0
        last = None
        while True:
            # Walk the primary key in batches rather than holding a cursor.
            stmt = sa.select(
                cache.c.cluster, cache.c.key, cache.c.created_at, cache.c.data
            ).where(cache.c.bank == bank)
            if last is not None:
                stmt = stmt.where(sa.tuple_(cache.c.cluster, cache.c.key) > last)
            if stale_only:
                stmt = stmt.where(
                    cache.c.terms_config.is_distinct_from(paths.fingerprint)
                )
            rows = connection.execute(
                stmt.order_by(cache.c.cluster, cache.c.key).limit(batch)
            ).all()
            if not rows:
                break
            connection.execute(
                update,
                [
                    {
                        "b_bank": bank,
                        "b_cluster": cluster,
                        "b_key": key,
                        "b_seen": seen,
                        "b_terms": flatten(data, paths),
                    }
                    for cluster, key, seen, data in rows
                ],
            )
            rebuilt[bank] += len(rows)
            last = (rows[-1].cluster, rows[-1].key)
    return rebuilt


def tsquery(exact=(), prefixes=()):
    """
    Return a tsquery matching any of the terms, or any term starting with one
    of the prefixes, or None when there are neither.
    """

    def quote(text):
        return "'" + text.replace("\\", "\\\\").replace("'", "''") + "'"

    parts = [quote(text) for text in sorted(exact)]
    parts.extend(quote(text) + ":*" for text in sorted(prefixes))
    return " | ".join(parts) or None
