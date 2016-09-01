# -*- coding: utf-8 -*-
'''
Classification of Salt exit codes.  These are intended to augment
universal exit codes (found in Python's `os` module with the `EX_`
prefix or in `sysexits.h`).

Lower value exit codes are, in-general, considered more serious.

:32-63: Reserved for Salt internal failures
:64-78: BSD-standardized exit values
:80-125: Reserved for Salt remote execution failures
:=> 80-89: remote execution: state system failures
:=> 90-95: remote execution: build failures
'''

EX_UNSET = -1             # The exit status is unset.
                          # NOTE: While this is a convention that is
                          # currently in use in Salt, -1 *is* a valid
                          # return status (it is often cast to a uint8
                          # and is manifest as 255.  This would likely
                          # be better as None

EX_OK = 0                 # successful termination

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

EX_TIMEDOUT = 63          # timeout expired

# BSD range 64 - 78
EX_USAGE = 64             # command line usage error
EX_DATAERR = 65           # data format error
EX_NOINPUT = 66           # cannot open input
EX_NOUSER = 67            # addressee unknown
EX_NOHOST = 68            # host name unknown
EX_UNAVAILABLE = 69       # service unavailable
EX_SOFTWARE = 70          # internal software error
EX_OSERR = 71             # system error (e.g. cannot fork)
EX_OSFILE = 72            # necessary OS file missing
EX_CANTCREAT = 73         # can't create (user) output file
EX_IOERR = 74             # input/output error
EX_TEMPFAIL = 75          # temp failure; user is invited to retry
EX_PROTOCOL = 76          # remote error in protocol
EX_NOPERM = 77            # permission denied
EX_CONFIG = 78            # configuration failure


# The Salt specific exit codes are defined below:

# keepalive exit code is a hint that the process should be restarted
SALT_KEEPALIVE = 99

# SALT_BUILD_FAIL is used when salt fails to build something, like a container
SALT_BUILD_FAIL = 101
