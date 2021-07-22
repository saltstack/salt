import logging
import sys
import types

USE_IMPORTLIB_METADATA_STDLIB = USE_IMPORTLIB_METADATA = USE_PKG_RESOURCES = False

if sys.version_info >= (3, 10):
    # Python 3.10 will include a fix in importlib.metadata which allows us to
    # get the distribution of a loaded entry-point
    import importlib.metadata  # pylint: disable=no-member,no-name-in-module

    USE_IMPORTLIB_METADATA_STDLIB = True
else:
    if sys.version_info >= (3, 6):
        # importlib_metadata available for python version lower than 3.6 do not
        # include the functionality we need.
        try:
            import importlib_metadata

            importlib_metadata_version = [
                int(part)
                for part in importlib_metadata.version("importlib_metadata").split(".")
                if part.isdigit()
            ]
            if tuple(importlib_metadata_version) >= (3, 3, 0):
                # Version 3.3.0 of importlib_metadata includes a fix which allows us to
                # get the distribution of a loaded entry-point
                USE_IMPORTLIB_METADATA = True
        except ImportError:
            # We don't have importlib_metadata but USE_IMPORTLIB_METADATA is set to false by default
            pass

if not USE_IMPORTLIB_METADATA_STDLIB and not USE_IMPORTLIB_METADATA:
    # Try to use pkg_resources
    try:
        import pkg_resources

        USE_PKG_RESOURCES = True
    except ImportError:
        # We don't have pkg_resources but USE_PKG_RESOURCES is set to false by default
        pass


log = logging.getLogger(__name__)


def iter_entry_points(group, name=None):
    entry_points_listing = []
    if USE_IMPORTLIB_METADATA_STDLIB:
        log.debug("Using importlib.metadata to load entry points")
        entry_points = importlib.metadata.entry_points()
    elif USE_IMPORTLIB_METADATA:
        log.debug("Using importlib_metadata to load entry points")
        entry_points = importlib_metadata.entry_points()
    elif USE_PKG_RESOURCES:
        log.debug("Using pkg_resources to load entry points")
        entry_points_listing = list(pkg_resources.iter_entry_points(group, name=name))
    else:
        return entry_points_listing

    if USE_IMPORTLIB_METADATA_STDLIB or USE_IMPORTLIB_METADATA:
        for entry_point_group, entry_points_list in entry_points.items():
            if entry_point_group != group:
                continue
            for entry_point in entry_points_list:
                if name is not None and entry_point.name != name:
                    continue
                entry_points_listing.append(entry_point)

    return entry_points_listing


def name_and_version_from_entry_point(entry_point):
    if USE_IMPORTLIB_METADATA_STDLIB or USE_IMPORTLIB_METADATA:
        return types.SimpleNamespace(
            name=entry_point.dist.metadata["name"], version=entry_point.dist.version,
        )
    elif USE_PKG_RESOURCES:
        return types.SimpleNamespace(
            name=entry_point.dist.key, version=entry_point.dist.version
        )
