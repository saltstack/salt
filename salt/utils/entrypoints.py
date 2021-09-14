import imp
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
    try:
        from salt._compat import importlib_metadata

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
        # We have to reload pkg_resources because it caches information and extensions installed while
        # salt is running are not discovered until a python process restart, or, us reloading pkg_resources
        if "pkg_resources" in sys.modules:
            # This is really weird, but it's because of the following traceback seen during CI testing
            #  Traceback (most recent call last):
            #    File "/tmp/kitchen/testing/salt/utils/parsers.py", line 210, in parse_args
            #      mixin_after_parsed_func(self)
            #    File "/tmp/kitchen/testing/salt/utils/parsers.py", line 880, in __setup_extended_logging
            #      log.setup_extended_logging(self.config)
            #    File "/tmp/kitchen/testing/salt/log/setup.py", line 414, in setup_extended_logging
            #      providers = salt.loader.log_handlers(opts)
            #    File "/tmp/kitchen/testing/salt/loader.py", line 674, in log_handlers
            #      base_path=os.path.join(SALT_BASE_PATH, "log"),
            #    File "/tmp/kitchen/testing/salt/loader.py", line 145, in _module_dirs
            #      for entry_point in entrypoints.iter_entry_points("salt.loader"):
            #    File "/tmp/kitchen/testing/salt/utils/entrypoints.py", line 59, in iter_entry_points
            #      imp.reload(pkg_resources)
            #    File "/usr/lib/python3.7/imp.py", line 314, in reload
            #      return importlib.reload(module)
            #    File "/usr/lib/python3.7/importlib/__init__.py", line 148, in reload
            #      raise ImportError(msg.format(name), name=name)
            #  ImportError: module pkg_resources not in sys.modules

            # Lets re-inject it into sys.modules since we have a reference to the module
            sys.modules["pkg_resources"] = pkg_resources
        imp.reload(pkg_resources)
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
            name=entry_point.dist.metadata["name"],
            version=entry_point.dist.version,
        )
    elif USE_PKG_RESOURCES:
        return types.SimpleNamespace(
            name=entry_point.dist.key, version=entry_point.dist.version
        )
