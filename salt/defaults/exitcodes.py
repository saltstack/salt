# -*- coding: utf-8 -*-
'''
Classification of Salt exit codes.  These are intended to augment
universal exit codes (found in Python's `os` module with the `EX_`
prefix or in `sysexits.h`).
'''

# Too many situations use "exit 1" - try not to use it when something
# else is more appropriate.
EX_GENERIC = 1

# Salt SSH "Thin" deployment failures
EX_THIN_PYTHON_OLD = 10
EX_THIN_DEPLOY = 11
EX_THIN_CHECKSUM = 12
EX_MOD_DEPLOY = 13
EX_SCP_NOT_FOUND = 14

# The os.EX_* exit codes are Unix only so in the interest of cross-platform
# compatiblility define them explicitly here.
#
# These constants are documented here:
# https://docs.python.org/2/library/os.html#os.EX_OK

EX_OK = 0
EX_NOUSER = 67
EX_UNAVAILABLE = 69
EX_CANTCREAT = 73
EX_SOFTWARE = 70
EX_USAGE = 64
