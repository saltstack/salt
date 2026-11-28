"""
Match and list keys with SQL queries over the SQLAlchemy key cache.

:func:`salt.key.get_key` imports this module only when
``keys.cache_driver`` is ``sqlalchemy``, so masters using other drivers do
not load SQLAlchemy.
"""

import fnmatch
import logging
import os

import salt.sqlalchemy
from salt.key import Key

log = logging.getLogger(__name__)


try:
    from sqlalchemy import ARRAY, any_, literal, or_, select, union_all

    from salt.sqlalchemy.models import model_for, utcnow
except ImportError:
    # stubs to appease pyright
    model_for = utcnow = select = or_ = ARRAY = any_ = literal = union_all = print


def _sqlite_glob_class(members, negated):
    """Render character ranges without SQLite's special ], ^ and - positions."""
    special = set()
    ranges = []
    for lower, upper in members:
        for char in "-]^":
            point = ord(char)
            if lower <= point <= upper:
                if lower < point:
                    ranges.append((lower, point - 1))
                special.add(char)
                lower = point + 1
        if lower <= upper:
            ranges.append((lower, upper))
    body = ("]" if "]" in special else "") + "".join(
        chr(lower) if lower == upper else chr(lower) + "-" + chr(upper)
        for lower, upper in ranges
    )
    if not negated and not body and "^" in special:
        return "[-^]" if "-" in special else "^"
    body += ("^" if "^" in special else "") + ("-" if "-" in special else "")
    return "[" + ("^" if negated else "") + body + "]"


def _sql_key_glob(key, pattern, dialect):
    """Translate fnmatch syntax into complete database glob predicates."""
    sqlite = dialect == "sqlite"
    like = []
    regex = [r"(?s)\A" if dialect == "postgresql" else r"(?s-i)\A"]
    has_class = False
    i = 0

    def escape_regex(point):
        # Character-entry escapes also make ], \, ^ and - literal in a class.
        return rf"\U{point:08x}" if dialect == "postgresql" else rf"\x{{{point:x}}}"

    while i < len(pattern):
        char = pattern[i]
        i += 1
        if char == "*":
            if i == 1 or pattern[i - 2] != "*":
                like.append("*" if sqlite else "%")
                regex.append(".*")
            continue
        if char == "?":
            like.append("?" if sqlite else "_")
            regex.append(".")
            continue
        if char == "[":
            end = i
            if end < len(pattern) and pattern[end] == "!":
                end += 1
            if end < len(pattern) and pattern[end] == "]":
                end += 1
            while end < len(pattern) and pattern[end] != "]":
                end += 1
            if end < len(pattern):
                has_class = True
                body = pattern[i:end]
                negated = body.startswith("!")
                if negated:
                    body = body[1:]
                members = []
                j = 0
                while j < len(body):
                    if j + 2 < len(body) and body[j + 1] == "-":
                        # fnmatch removes descending ranges instead of raising.
                        if body[j] <= body[j + 2]:
                            members.append((ord(body[j]), ord(body[j + 2])))
                        j += 3
                    else:
                        members.append((ord(body[j]), ord(body[j])))
                        j += 1
                if not members:
                    if not negated:
                        return literal(False)
                    regex.append(".")
                    like.append("?" if sqlite else "_")
                elif sqlite:
                    like.append(_sqlite_glob_class(members, negated))
                else:
                    escaped_members = []
                    for lower, upper in members:
                        part = escape_regex(lower)
                        if lower != upper:
                            part += "-" + escape_regex(upper)
                        escaped_members.append(part)
                    regex.append(
                        "[" + ("^" if negated else "") + "".join(escaped_members) + "]"
                    )
                    like.append("_")
                i = end + 1
                continue
        if sqlite:
            like.append("[[]" if char == "[" else char)
        else:
            like.append("\\" + char if char in "\\_%" else char)
            regex.append(escape_regex(ord(char)))

    if sqlite:
        return key.bool_op("GLOB")("".join(like))
    like_key = key
    if dialect in {"mysql", "mariadb"}:
        # utf8mb4_bin pads with spaces, so a LIKE prefix range starts above
        # keys continuing with a control character ("web\n-prod" sorts before
        # "web") and skips them. A NO PAD collation keeps them, giving up the
        # range on key but not the bank prefix of the primary key.
        like_key = key.collate(
            "utf8mb4_nopad_bin" if dialect == "mariadb" else "utf8mb4_0900_bin"
        )
    condition = like_key.like("".join(like), escape="\\")
    if has_class:
        if dialect == "postgresql":
            # C collation keeps ranges in character-code order, like fnmatch.
            regex_key = key.collate("C")
            operator, end = "~", r"\Z"
        else:
            regex_key = key.collate("utf8mb4_bin")
            operator, end = "REGEXP", r"\z"
        # Retain LIKE on the original column for its literal-prefix index path.
        condition &= regex_key.bool_op(operator)("".join(regex) + end)
    return condition


class SqlAlchemyKey(Key):
    KEYS_CACHE = "keys"
    DENIED_CACHE = "denied_keys"

    def __init__(self, opts, *args, **kwargs):
        # A real NULL cannot be used as a primary key on every backend.
        self.cluster_id = opts.get("cluster_id") or salt.sqlalchemy.STANDALONE_CLUSTER
        super().__init__(opts, *args, **kwargs)

    def _key_rows(self, *conditions, glob_patterns=None, key_names=None):
        """Fetch live key metadata without loading each key's public key."""
        Cache = model_for("Cache")
        stmt = select(Cache.key, Cache.bank, Cache.data["state"]).where(
            Cache.cluster == self.cluster_id,
            Cache.bank.in_((self.KEYS_CACHE, self.DENIED_CACHE)),
            or_(Cache.expires_at.is_(None), Cache.expires_at > utcnow()),
            *conditions,
        )
        with salt.sqlalchemy.Session() as session:
            if glob_patterns is not None:
                dialect = session.bind.dialect
                if getattr(dialect, "is_mariadb", False):
                    dialect = "mariadb"
                else:
                    dialect = dialect.name
                # SQLite repeats metadata binds in each branch. Keep below its
                # historical 999-variable and 500-compound-SELECT limits.
                batch_size = 100 if dialect == "sqlite" else 500
                # Complete, constant patterns let SQL use their prefixes.
                # UNION ALL preserves overlapping and duplicate matches.
                queries = (
                    union_all(
                        *(
                            stmt.where(_sql_key_glob(Cache.key, pattern, dialect))
                            for pattern in glob_patterns[start : start + batch_size]
                        )
                    )
                    for start in range(0, len(glob_patterns), batch_size)
                )
            elif key_names is not None:
                queries = (
                    stmt.where(Cache.key.in_(key_names[start : start + 500]))
                    for start in range(0, len(key_names), 500)
                )
            else:
                queries = (stmt,)
            rows = [row for query in queries for row in session.execute(query)]
            session.commit()
        return rows

    def _key_status(self, id_, bank, state):
        if bank == self.DENIED_CACHE:
            return self.DEN
        if isinstance(state, str) and state in self.STATE_MAP:
            return self.STATE_MAP[state]
        log.error("unexpected key state returned for %s: %s", id_, state)
        return None

    def list_keys(self):
        """Return keys grouped by state, using Salt's display ordering."""
        ret = {self.PEND: [], self.REJ: [], self.ACC: [], self.DEN: []}
        for id_, bank, state in self._key_rows():
            status = self._key_status(id_, bank, state)
            if status is not None:
                ret[status].append(id_)
        return {
            status: sorted(keys, key=lambda name: (name.lower(), name))
            for status, keys in ret.items()
        }

    def list_match(self, match):
        """Look up exact key names in bulk, preserving the requested order."""
        if isinstance(match, str):
            match = match.split(",")
        match = list(match)
        Cache = model_for("Cache")
        if salt.sqlalchemy.get_engine().dialect.name == "postgresql":
            rows = self._key_rows(
                Cache.key == any_(literal(match, type_=ARRAY(Cache.key.type))),
            )
        else:
            rows = self._key_rows(key_names=list(dict.fromkeys(match)))
        rows = {(bank, id_): state for id_, bank, state in rows}
        ret = {}
        for id_ in match:
            for bank in (self.KEYS_CACHE, self.DENIED_CACHE):
                if (bank, id_) not in rows:
                    continue
                status = self._key_status(id_, bank, rows[bank, id_])
                if status is not None:
                    ret.setdefault(status, []).append(id_)
        return ret

    def glob_match(self, match, full=False):
        """Match complete globs in SQL, including large pattern lists."""
        if os.path.normcase("A") != "A":
            return super().glob_match(match, full=full)
        if salt.sqlalchemy.get_engine().dialect.name not in {
            "postgresql",
            "mysql",
            "mariadb",
            "sqlite",
        }:
            return super().glob_match(match, full=full)
        patterns = match.split(",") if isinstance(match, str) else match
        if not patterns:
            return {}
        if not any(char in pattern for pattern in patterns for char in "*?["):
            ret = self.list_match(patterns)
        else:
            ret = {}
            for id_, bank, state in self._key_rows(glob_patterns=patterns):
                status = self._key_status(id_, bank, state)
                if status is not None:
                    ret.setdefault(status, []).append(id_)
        ret = {
            status: sorted(keys, key=lambda name: (name.lower(), name))
            for status, keys in ret.items()
        }
        if full:
            # Local master keys are few and are stored outside the managed banks.
            for status, keys in self.local_keys().items():
                matches = (
                    keys
                    if patterns == ["*"]
                    else [
                        name
                        for name in salt.utils.data.sorted_ignorecase(keys)
                        for pattern in patterns
                        if fnmatch.fnmatchcase(name, pattern)
                    ]
                )
                if matches:
                    ret[status] = matches
        return ret
