"""
Salt-idiomatic pydantic types for use in module signatures.

These exist so a module author can write a plain Python signature like::

    from salt.loader.annotations import Duration, ByteSize, MinionID

    def retry(interval: Duration = "30s",
              max_memory: ByteSize = "500MB",
              target: MinionID = "*"): ...

and get CLI-string coercion, validation, and JSON Schema emission for
free -- all via the loader-level validation layer in
:mod:`salt.loader.validation`.

Named ``annotations`` (rather than the more natural ``types``) because
``salt.types`` or ``salt.loader.types`` as a package shadows Python's
stdlib ``types`` module in Salt code paths that depend on it (e.g.
``salt/loader/__init__.py`` uses ``types.SimpleNamespace``).

Two patterns are used here:

* **Annotated pattern** (``MinionID``, ``Port``): a type alias combining
  an existing primitive with ``pydantic.Field`` or a functional
  validator. Reads as a type at the call site; costs one line to define.

* **Custom core-schema pattern** (``Duration``, ``ByteSize``): a class
  with ``__get_pydantic_core_schema__`` that owns multi-form coercion
  (e.g. ``"30s"`` -> seconds, ``"500MB"`` -> bytes). Use when the type
  needs to accept several surface representations and store a single
  canonical form.

Both patterns round-trip through ``model_json_schema()`` so the published
JSON Schema reflects their constraints.
"""

import re
from datetime import timedelta
from typing import Annotated

from salt.utils.versions import reqs

if reqs.pydantic:
    from pydantic import AfterValidator, Field, GetJsonSchemaHandler
    from pydantic_core import CoreSchema, core_schema


if reqs.pydantic:
    # -----------------------------------------------------------------
    # Annotated pattern: trivial declarative types.
    # -----------------------------------------------------------------

    def _validate_minion_id(v: str) -> str:
        if not v:
            raise ValueError("minion id cannot be empty")
        if len(v) > 253:
            raise ValueError(f"minion id too long: {len(v)} > 253")
        if not re.fullmatch(r"[A-Za-z0-9._\-*?\[\]]+", v):
            raise ValueError(
                f"minion id {v!r} contains characters outside " "[A-Za-z0-9._-*?[]]"
            )
        return v

    MinionID = Annotated[str, AfterValidator(_validate_minion_id)]
    """Minion id or target glob. Alphanumeric + ``.``, ``_``, ``-`` plus
    glob metacharacters ``*?[]``. Max 253 chars (hostname rules)."""

    Port = Annotated[int, Field(ge=1, le=65535)]
    """IP port number, 1-65535 inclusive."""

    # -----------------------------------------------------------------
    # Custom core-schema pattern: multi-form coercion.
    # -----------------------------------------------------------------

    class Duration(timedelta):
        """A time duration that accepts several surface forms and stores
        a canonical :class:`datetime.timedelta`.

        Accepts:

        * :class:`timedelta` -- passed through.
        * Numeric (``int`` or ``float``) -- treated as seconds.
        * Short string ``"30s"`` / ``"5m"`` / ``"2h"`` / ``"1d"`` --
          decimal values allowed (``"1.5h"`` = 5400s).
        * ISO-8601 ``"PT1H30M"`` -- delegated to pydantic's built-in
          timedelta parser.
        """

        _UNITS = {"s": 1, "m": 60, "h": 3600, "d": 86400}
        _SHORT = re.compile(r"(\d+(?:\.\d+)?)\s*([smhd])$")

        @classmethod
        def _coerce(cls, v):
            if isinstance(v, timedelta):
                return v
            if isinstance(v, (int, float)):
                return timedelta(seconds=float(v))
            if isinstance(v, str):
                m = cls._SHORT.fullmatch(v.strip())
                if m:
                    return timedelta(seconds=float(m.group(1)) * cls._UNITS[m.group(2)])
            # Fall through to pydantic's ISO-8601 timedelta parser.
            return v

        @classmethod
        def __get_pydantic_core_schema__(cls, source, handler) -> CoreSchema:
            return core_schema.no_info_before_validator_function(
                cls._coerce,
                core_schema.timedelta_schema(),
            )

        @classmethod
        def __get_pydantic_json_schema__(cls, schema, handler: GetJsonSchemaHandler):
            js = handler(schema)
            js["title"] = "Duration"
            js["description"] = (
                "Time duration: timedelta, seconds (number), "
                "short form (30s, 5m, 2h, 1d), or ISO-8601 (PT1H30M)."
            )
            js["examples"] = ["30s", "5m", "2h", "1d", "PT1H30M", 3600]
            return js

    class ByteSize(int):
        """A size in bytes that accepts human-readable multipliers and
        stores a canonical :class:`int` byte count.

        Accepts:

        * ``int`` -- passed through.
        * ``str`` -- integer or decimal followed by a multiplier:

          - Decimal (SI): ``KB=1e3``, ``MB=1e6``, ``GB=1e9``, ``TB=1e12``.
          - Binary (IEC): ``KiB=2**10``, ``MiB=2**20``, ``GiB=2**30``,
            ``TiB=2**40``.
          - Bare suffix (``B``) or no suffix -- raw bytes.

        Case-insensitive. Whitespace between the number and suffix is
        tolerated.
        """

        _MULTIPLIERS = {
            "": 1,
            "B": 1,
            "KB": 10**3,
            "MB": 10**6,
            "GB": 10**9,
            "TB": 10**12,
            "KIB": 2**10,
            "MIB": 2**20,
            "GIB": 2**30,
            "TIB": 2**40,
        }
        _PATTERN = re.compile(r"(\d+(?:\.\d+)?)\s*([A-Za-z]*)$")

        @classmethod
        def _coerce(cls, v):
            if isinstance(v, bool):
                # bool is an int subclass; reject explicitly so True/False
                # don't silently coerce to 1/0 bytes.
                raise ValueError("ByteSize does not accept bool")
            if isinstance(v, int):
                return v
            if isinstance(v, float):
                return int(v)
            if isinstance(v, str):
                m = cls._PATTERN.fullmatch(v.strip())
                if not m:
                    raise ValueError(
                        f"ByteSize: cannot parse {v!r} "
                        "(expected e.g. '500MB' or '1.5GiB')"
                    )
                num = float(m.group(1))
                unit = m.group(2).upper()
                if unit not in cls._MULTIPLIERS:
                    raise ValueError(
                        f"ByteSize: unknown unit {m.group(2)!r} "
                        f"(known: {sorted(cls._MULTIPLIERS)})"
                    )
                return int(num * cls._MULTIPLIERS[unit])
            raise ValueError(f"ByteSize: cannot coerce {type(v).__name__}")

        @classmethod
        def __get_pydantic_core_schema__(cls, source, handler) -> CoreSchema:
            return core_schema.no_info_before_validator_function(
                cls._coerce,
                core_schema.int_schema(ge=0),
            )

        @classmethod
        def __get_pydantic_json_schema__(cls, schema, handler: GetJsonSchemaHandler):
            js = handler(schema)
            js["title"] = "ByteSize"
            js["description"] = (
                "Size in bytes. Accepts int, or string with SI (KB/MB/GB/TB) "
                "or IEC (KiB/MiB/GiB/TiB) suffix."
            )
            js["examples"] = ["500MB", "1.5GiB", "4096", 1048576]
            return js

else:  # pragma: no cover
    MinionID = str  # type: ignore[misc,assignment]
    Port = int  # type: ignore[misc,assignment]
    Duration = timedelta  # type: ignore[misc,assignment]
    ByteSize = int  # type: ignore[misc,assignment]


__all__ = ["MinionID", "Port", "Duration", "ByteSize"]
