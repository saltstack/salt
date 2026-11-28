"""
Match minions with bulk SQL queries over the SQLAlchemy cache.

:meth:`salt.utils.minions.CkMinions.factory` imports this module only when
the sqlalchemy cache is configured, so masters using other drivers do not
load SQLAlchemy.
"""

import contextlib
import logging
import threading
import time

import salt.sqlalchemy
import salt.sqlalchemy.key
import salt.utils.args
import salt.utils.metrics
from salt.utils.minions import CkMinions, TargetingError, TargetingTimeout

log = logging.getLogger(__name__)


try:
    from sqlalchemy import (
        ARRAY,
        Boolean,
        Text,
        any_,
        case,
        cast,
        column,
        false,
        func,
        literal,
        null,
        or_,
        select,
        table,
        text,
        type_coerce,
        union_all,
    )
    from sqlalchemy.dialects.postgresql import TSQUERY

    from salt.sqlalchemy import terms
    from salt.sqlalchemy.models import model_for, utcnow
except ImportError:
    # stubs to appease pyright
    model_for = utcnow = select = func = or_ = ARRAY = any_ = case = literal = print
    Boolean = Text = null = text = type_coerce = union_all = terms = print
    cast = false = TSQUERY = column = table = print

# SQLSTATE PostgreSQL reports when statement_timeout cancels a query.
QUERY_CANCELED = "57014"


class _TargetingTimeout(Exception):
    """A cache lookup ran past sqlalchemy.targeting_timeout."""


class SQLAlchemyCkMinions(CkMinions):
    """Use bulk SQL queries while retaining Salt's Python matcher semantics."""

    def __init__(self, opts):
        if not salt.sqlalchemy.orm_configured():
            salt.sqlalchemy.configure_orm(opts)

        self.dialect_name = salt.sqlalchemy.get_engine().dialect.name
        # Per-thread request state: accepted minions memoized for one request.
        self._local = threading.local()

        super().__init__(opts)

    @contextlib.contextmanager
    def _request_scope(self):
        """Share accepted minions across one target or ACL evaluation."""
        depth = getattr(self._local, "depth", 0)
        if not depth:
            self._local.pki = None
        self._local.depth = depth + 1
        try:
            yield
        finally:
            self._local.depth = depth
            if not depth:
                self._local.pki = None

    def _pki_minions(self):
        """Memoize accepted minions within a request; each call lists every key."""
        if not getattr(self._local, "depth", 0):
            return super()._pki_minions()
        if self._local.pki is None:
            self._local.pki = super()._pki_minions()
        return set(self._local.pki)

    def check_minions(self, *args, **kwargs):
        with self._request_scope():
            return super().check_minions(*args, **kwargs)

    def auth_check(self, *args, **kwargs):
        with self._request_scope():
            return super().auth_check(*args, **kwargs)

    def _check_cache_minions(
        self,
        expr,
        delimiter,
        greedy,
        search_type,
        regex_match=False,
        exact_match=False,
        minions=None,
    ):
        """
        Match cached grains or pillar through their indexed terms.

        Rows the terms cannot decide are checked with ``subdict_match``.
        Targets the terms cannot restrict are matched by scanning. Failures,
        including running past ``sqlalchemy.targeting_timeout``, raise
        TargetingError, which check_minions lets through.
        """
        bank = "pillar" if search_type.startswith("pillar") else "grains"
        budget = salt.sqlalchemy.ENGINE_REGISTRY["default"]["config"].get(
            "targeting_timeout"
        )
        deadline = time.monotonic() + budget / 1000 if budget else None
        try:
            return self._match_cache(
                bank,
                expr,
                delimiter,
                greedy,
                search_type,
                regex_match,
                exact_match,
                minions,
                deadline,
            )
        except TargetingError:
            raise
        except Exception as exc:  # pylint: disable=broad-except
            canceled = getattr(getattr(exc, "orig", None), "sqlstate", None)
            if not isinstance(exc, _TargetingTimeout) and canceled != QUERY_CANCELED:
                raise TargetingError(
                    f"Could not evaluate {bank} target {expr!r}: {exc}"
                ) from exc
            message = (
                f"Matching {bank} target {expr!r} took longer than "
                f"sqlalchemy.targeting_timeout ({budget} ms)"
            )
            log.error("%s; the target fails", message)
            salt.utils.metrics.counter(
                "salt.targeting.sql.timeout",
                description="Grain and pillar targets abandoned after the time limit.",
            ).add(1, attributes={"bank": bank})
            raise TargetingTimeout(message) from exc

    def _match_cache(
        self,
        bank,
        expr,
        delimiter,
        greedy,
        search_type,
        regex_match,
        exact_match,
        minions,
        deadline,
    ):
        stmt = plan = None
        if self.dialect_name == "postgresql" and self.opts.get(
            "minion_data_cache", False
        ):
            paths = terms.paths(salt.sqlalchemy.ENGINE_REGISTRY["default"]["config"])
            plan = terms.compile_target(
                expr, delimiter, regex_match, exact_match, paths
            )
            if plan.never:
                return {"minions": [], "missing": []}
            if not plan.fallback:
                stmt = self._terms_statement(bank, plan, paths)
            else:
                log.info(
                    "Matching %s target %r by scanning cached data: %s",
                    bank,
                    expr,
                    plan.fallback,
                )
                salt.utils.metrics.counter(
                    "salt.targeting.sql.fallback",
                    description="Grain and pillar targets the cache terms cannot answer.",
                ).add(1, attributes={"bank": bank, "reason": plan.fallback})
                stmt = self._scan_statement(
                    bank, expr, delimiter, minions if greedy else None
                )
        if stmt is None:
            return super()._check_cache_minions(
                expr, delimiter, greedy, search_type, regex_match, exact_match, minions
            )
        hits = self._stream_matches(
            stmt,
            expr,
            delimiter,
            regex_match,
            exact_match,
            deadline,
            indexed=not plan.fallback,
        )
        if greedy:
            if minions:
                hits &= set(minions)
            else:
                self._check_deadline(deadline)
                hits = self._accepted(hits)
                self._check_deadline(deadline)
        # Unsorted: callers combine results as sets, and sorting a large
        # result costs more than the rest of the lookup.
        return {"minions": list(hits), "missing": []}

    # Above this many matches, listing every accepted key once is cheaper than
    # looking up each match. Backends reading a file per key reach that much
    # sooner than one bulk query, which costs about 15 us per key against 6 us
    # per key for a full listing at a million minions.
    ACCEPTED_LOOKUP_LIMIT = 10000
    BULK_ACCEPTED_LOOKUP_LIMIT = 250000

    def _bulk_key_lookup(self):
        """Whether the key backend looks up many keys in one query."""
        return isinstance(self.key, salt.sqlalchemy.key.SqlAlchemyKey)

    def _accepted(self, keys):
        """
        Return the minions among ``keys`` whose key is accepted.

        Greedy targets only match accepted minions, since cached data outlives
        deleted, rejected and pending keys. Looking up just the matched keys
        costs what the result costs, rather than listing the whole fleet.
        """
        keys = set(keys)
        listed = getattr(self._local, "pki", None)
        if listed is not None and getattr(self._local, "depth", 0):
            return keys & listed
        limit = (
            self.BULK_ACCEPTED_LOOKUP_LIMIT
            if self._bulk_key_lookup()
            else self.ACCEPTED_LOOKUP_LIMIT
        )
        if len(keys) > limit:
            return keys & self._pki_minions()
        if not keys:
            return keys
        # Errors propagate: treating them as no accepted minions would make a
        # compound "not" match every minion.
        found = self.key.list_match(list(keys))
        return keys & set(found.get(self.key.ACC, ()))

    @staticmethod
    def _check_deadline(deadline):
        if deadline is not None and time.monotonic() > deadline:
            raise _TargetingTimeout()

    @staticmethod
    def _limit_session(session, deadline):
        """Bound the session's statements by what remains of the deadline."""
        if deadline is not None:
            remaining = max(int((deadline - time.monotonic()) * 1000), 1)
            session.execute(text(f"SET LOCAL statement_timeout = {remaining}"))

    @staticmethod
    def _readable_document(data, keys):
        """
        Select only the top-level keys of ``data`` that subdict_match can read
        for a target.

        Tagged documents need the codec on the whole value.
        """
        entry = func.jsonb_each(data).table_valued("key", "value")
        subtree = (
            select(
                func.coalesce(
                    func.jsonb_object_agg(entry.c.key, entry.c.value),
                    func.jsonb_build_object(),
                )
            )
            .where(entry.c.key == any_(literal(sorted(keys), type_=ARRAY(Text))))
            .scalar_subquery()
        )
        return type_coerce(
            case(
                (
                    or_(
                        func.jsonb_typeof(data) != "object",
                        data.has_key(salt.sqlalchemy._JSON_TAG),
                    ),
                    data,
                ),
                else_=subtree,
            ),
            data.type,
        )

    def _terms_statement(self, bank, plan, paths):
        """
        Select (key, certain, readable subtrees) for rows a plan's terms find.
        """
        Cache = model_for("Cache")
        # Query the bank's partition directly, with no bank condition, so the
        # terms index is the only access path for the term conditions.
        # Otherwise, when most rows match, the planner picks the bank or
        # fingerprint index and builds every row's tsvector to filter it.
        partition = table(
            f"cache_{bank}",
            column("key", Cache.key.type),
            column("cluster", Cache.cluster.type),
            column("data", Cache.data.type),
            column("expires_at", Cache.expires_at.type),
            column("terms", Cache.terms.type),
            column("terms_config", Cache.terms_config.type),
            schema=salt.sqlalchemy.ENGINE_REGISTRY["default"]["config"].get("schema")
            or None,
        )
        rows = partition.c
        vector = func.array_to_tsvector(rows.terms)

        def matching(exact, prefixes):
            query = terms.tsquery(exact, prefixes)
            if query is None:
                return false()
            return vector.op("@@")(cast(literal(query), TSQUERY))

        live = (
            rows.cluster == self.cache.kwargs["cluster_id"],
            or_(rows.expires_at.is_(None), rows.expires_at > utcnow()),
        )
        # Certain rows only return their key, so their terms and documents are
        # never read from storage. They come first, so their keys skip
        # rechecks.
        certain = select(
            rows.key,
            type_coerce(literal(True), Boolean).label("certain"),
            type_coerce(null(), Cache.data.type).label("data"),
        ).where(
            *live,
            matching(plan.certain, plan.certain_prefixes),
            # Not indexable on purpose, for the same reason as the bank:
            # nearly every row has the current fingerprint.
            func.coalesce(rows.terms_config, "") == paths.fingerprint,
        )
        candidates = select(
            rows.key,
            type_coerce(literal(False), Boolean).label("certain"),
            self._readable_document(rows.data, plan.keys).label("data"),
        ).where(
            *live,
            or_(
                matching(plan.candidates, plan.candidate_prefixes),
                # Rows without terms, or with terms built for other term
                # paths, are always rechecked. Two ranges keep this on the
                # fingerprint index.
                rows.terms_config.is_(None),
                rows.terms_config < paths.fingerprint,
                rows.terms_config > paths.fingerprint,
            ),
        )
        return union_all(certain, candidates)

    def _scan_statement(self, bank, expr, delimiter, minions):
        """
        Select (key, certain, readable subtrees) for every row a target may
        match, or None when the base matcher has to evaluate it.
        """
        if not isinstance(expr, str) or not isinstance(delimiter, str):
            return None
        first_token, separator, _ = expr.partition(delimiter)
        if not separator or not delimiter or "*" in delimiter or "\0" in first_token:
            return None
        Cache = model_for("Cache")
        readable = None
        conditions = []
        if first_token != "*":
            # Traversal only reads the subtree under the first segment, and
            # retries a missing literal key through YAML normalization.
            readable = {first_token}
            loaded_token = salt.utils.args.yamlify_arg(first_token)
            if isinstance(loaded_token, str) and loaded_token != first_token:
                if "\0" in loaded_token:
                    return None
                readable.add(loaded_token)
            conditions.append(
                or_(
                    *(Cache.data.has_key(key) for key in sorted(readable)),
                    # Non-string/NUL dictionary keys and reserved tags use the
                    # codec.
                    Cache.data.has_key(salt.sqlalchemy._JSON_TAG),
                    # traverse_dict_and_list also searches dictionaries inside
                    # lists.
                    func.jsonb_typeof(Cache.data) == "array",
                )
            )
        if minions:
            conditions.append(
                Cache.key == any_(literal(list(minions), type_=ARRAY(Cache.key.type)))
            )
        return select(
            Cache.key,
            type_coerce(literal(False), Boolean).label("certain"),
            (
                Cache.data
                if readable is None
                else self._readable_document(Cache.data, readable)
            ).label("data"),
        ).where(
            Cache.bank == bank,
            Cache.cluster == self.cache.kwargs["cluster_id"],
            or_(Cache.expires_at.is_(None), Cache.expires_at > utcnow()),
            *conditions,
        )

    def _stream_matches(
        self, stmt, expr, delimiter, regex_match, exact_match, deadline, indexed
    ):
        """
        Return the keys of rows from ``stmt`` that are certain or that
        subdict_match accepts, streaming rather than holding every document.
        """
        hits = set()
        stmt = stmt.execution_options(yield_per=500)
        with salt.sqlalchemy.ROSession() as session:
            if indexed:
                # When most rows match, the planner prefers a sequential or
                # primary key scan, which decompresses every row's terms.
                session.execute(text("SET LOCAL enable_seqscan = off"))
                session.execute(text("SET LOCAL enable_indexscan = off"))
            self._limit_session(session, deadline)
            with session.execute(stmt) as result:
                for count, (key, certain, data) in enumerate(result):
                    if count % 500 == 0:
                        # statement_timeout only bounds each fetch.
                        self._check_deadline(deadline)
                    if certain:
                        hits.add(key)
                        continue
                    self._check_deadline(deadline)
                    if key not in hits and salt.utils.data.subdict_match(
                        data,
                        expr,
                        delimiter=delimiter,
                        regex_match=regex_match,
                        exact_match=exact_match,
                    ):
                        hits.add(key)
            session.commit()
        self._check_deadline(deadline)
        return hits

    def _iter_minion_grains_addresses(self, subset=None):
        """Yield live cached addresses in bulk, retaining their address family."""
        subset_ids = set(subset or ())
        with salt.sqlalchemy.ROSession() as session:
            Cache = model_for("Cache")

            stmt = select(
                Cache.key,
                Cache.data["ipv4"].label("ipv4"),
                Cache.data["ipv6"].label("ipv6"),
                case(
                    (
                        Cache.data[salt.sqlalchemy._JSON_TAG].as_string().is_not(None),
                        Cache.data,
                    ),
                    else_=None,
                ).label("tagged_data"),
            )

            stmt = stmt.where(
                Cache.bank == "grains",
                Cache.cluster == self.cache.kwargs["cluster_id"],
                or_(Cache.expires_at.is_(None), Cache.expires_at > utcnow()),
            )

            if subset:
                if self.dialect_name == "postgresql":
                    stmt = stmt.where(
                        Cache.key
                        == any_(literal(list(subset_ids), type_=ARRAY(Cache.key.type)))
                    )
                elif len(subset_ids) <= 500:
                    # Larger subsets are filtered below to bound SQL parameters.
                    stmt = stmt.where(Cache.key.in_(subset_ids))

            rows = session.execute(stmt).all()
            for row in rows:
                if subset and row.key not in subset_ids:
                    continue
                for family in ("ipv4", "ipv6"):
                    addresses = (
                        row.tagged_data.get(family)
                        if row.tagged_data is not None
                        else getattr(row, family)
                    )
                    for addr in addresses or []:
                        yield (row.key, family, str(addr))
            session.commit()
