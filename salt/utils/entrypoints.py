import functools
import logging
import sys
import time
import types

if sys.version_info >= (3, 10):
    # Python 3.10 will include a fix in importlib.metadata which allows us to
    # get the distribution of a loaded entry-point
    import importlib.metadata  # pylint: disable=no-member,no-name-in-module

    USE_IMPORTLIB_METADATA_STDLIB = True
else:
    USE_IMPORTLIB_METADATA_STDLIB = False
    try:
        from salt._compat import importlib_metadata

        USE_IMPORTLIB_METADATA = True
    except ImportError:
        USE_IMPORTLIB_METADATA = False

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
    if USE_IMPORTLIB_METADATA_STDLIB:
        log.debug("Using importlib.metadata to load entry points")
        entry_points = importlib.metadata.entry_points()
    elif USE_IMPORTLIB_METADATA:
        log.debug("Using importlib_metadata to load entry points")
        entry_points = importlib_metadata.entry_points()
    else:
        return entry_points_listing

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
