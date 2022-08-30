# Copyright 2007 Google Inc.
#  Licensed to PSF under a Contributor Agreement.
#
#

# This is test_ipaddress.py from Python 3.9.5 ported to use pytest
#    https://github.com/python/cpython/blob/v3.9.5/Lib/test/test_ipaddress.py
#
# Previously, this was a verbatim copy with the following changes...
#  - Switch the ipaddress import to salt._compat
#  - Copy the `LARGEST` and `SMALLEST` implementation, from 3.9.1
#  - Adjust IpaddrUnitTest.testNetworkElementCaching because we're not using cached_property
#
# These changes have also been ported to pytest
