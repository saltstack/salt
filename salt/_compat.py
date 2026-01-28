"""
Salt compatibility code
"""

# pylint: disable=unused-import
import sys

# pragma: no cover

# The ipaddress module included in Salt is from Python 3.9.5.
# When running from Py3.9.5+ use the standard library module, use ours otherwise
if sys.version_info >= (3, 9, 5):
    import ipaddress
else:
    import salt.ext.ipaddress as ipaddress

import importlib.metadata as importlib_metadata
