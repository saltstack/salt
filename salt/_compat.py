"""
Salt compatibility code
"""
# pylint: disable=unused-import
import sys

# The ipaddress module included in Salt is from Python 3.9.5.
# When running from Py3.9.5+ use the standard library module, use ours otherwise
if sys.version_info >= (3, 9, 5):
    import ipaddress
else:
    import salt.ext.ipaddress as ipaddress

# importlib_metadata before version 3.3.0 does not include the functionality we need.
try:
    import importlib_metadata

    importlib_metadata_version = [
        int(part)
        for part in importlib_metadata.version("importlib_metadata").split(".")
        if part.isdigit()
    ]
    if tuple(importlib_metadata_version) < (3, 3, 0):
        # Use the vendored importlib_metadata
        import salt.ext.importlib_metadata as importlib_metadata
except ImportError:
    # Use the vendored importlib_metadata
    import salt.ext.importlib_metadata as importlib_metadata
