import functools
import logging
import time
import types

from salt._compat import importlib_metadata

log = logging.getLogger(__name__)


def timed_lru_cache(timeout_seconds, *, maxsize=256, typed=False):
    """
    This decorator is the same in behavior as functools.lru_cache with the
    exception that it times out after the provided ``timeout_seconds``
    """

    def _wrapper(f):
        # Apply @lru_cache to f
        f = functools.lru_cache(maxsize=maxsize, typed=typed)(f)
        f.delta = timeout_seconds
        f.expiration = time.monotonic() + f.delta

        @functools.wraps(f)
        def _wrapped(*args, **kwargs):
            now = time.monotonic()
            if now >= f.expiration:
                f.cache_clear()
                f.expiration = now + f.delta
            return f(*args, **kwargs)

        return _wrapped

    return _wrapper


@timed_lru_cache(timeout_seconds=0.5)
def iter_entry_points(group, name=None):
    entry_points_listing = []
    entry_points = importlib_metadata.entry_points()

    try:
        for entry_point in entry_points.select(group=group):
            if name is not None and entry_point.name != name:
                continue
            entry_points_listing.append(entry_point)
    except AttributeError:
        # importlib-metadata<5.0.0
        for entry_point_group, entry_points_list in entry_points.items():
            if entry_point_group != group:
                continue
            for entry_point in entry_points_list:
                if name is not None and entry_point.name != name:
                    continue
                entry_points_listing.append(entry_point)

    return entry_points_listing


def name_and_version_from_entry_point(entry_point):
    return types.SimpleNamespace(
        name=entry_point.dist.metadata["name"],
        version=entry_point.dist.version,
    )
