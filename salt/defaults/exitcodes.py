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
EX_THIN_PYTHON_INVALID = 10
EX_THIN_DEPLOY = 11
EX_THIN_CHECKSUM = 12
EX_MOD_DEPLOY = 13
EX_SCP_NOT_FOUND = 14

# One of a collection failed
EX_AGGREGATE = 20

# The os.EX_* exit codes are Unix only so in the interest of cross-platform
# compatiblility define them explicitly here.
#
# These constants are documented here:
# https://docs.python.org/2/library/os.html#os.EX_OK

EX_OK = 0                 # successful termination
EX_USAGE = 64             # command line usage error
EX_NOUSER = 67            # addressee unknown
EX_UNAVAILABLE = 69       # service unavailable
EX_SOFTWARE = 70          # internal software error
EX_CANTCREAT = 73         # can't create (user) output file
EX_TEMPFAIL = 75          # temp failure; user is invited to retry

# The Salt specific exit codes are defined below:

# keepalive exit code is a hint that the process should be restarted
SALT_KEEPALIVE = 99

# SALT_BUILD_FAIL is used when salt fails to build something, like a container
SALT_BUILD_FAIL = 101
