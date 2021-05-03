"""
Salt compatibility code
"""
# pylint: disable=unused-import
import sys

# The ipaddress module included in Salt is from Python 3.9.1.
# When running from Py3.9.1+ use the standard library module, use ours otherwise
if sys.version_info >= (3, 9, 1):
    import ipaddress
else:
    import salt.ext.ipaddress as ipaddress
