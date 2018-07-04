# -*- coding: utf-8 -*-
'''
Salt exit codes.

Salt allocates free range in POSIX classification from 200 to 220.
Here are also redefined all os.EX_* exit codes since they are Unix only,
while needed on non-Unix platforms as well. See `sysexits.h` for more information.

NOTE: Original Windows exit codes at this range are overwritten.
'''

EX_GENERIC = 1  # Catchall for general errors (division by zero etc)
                # NOTE: for uncaught exceptions, please use EX_SOFTWARE error.

# Carbon copy of the os.EX_* exit codes from Unix-only.
# More info: https://docs.python.org/3/library/os.html
EX_OK = 0            # No error occurred
EX_USAGE = 64        # The command was used incorrectly, such as when the wrong number of arguments are given.
EX_DATAERR = 65      # The input data was incorrect.
EX_NOINPUT = 66      # An input file did not exist or was not readable.
EX_NOUSER = 67       # Specified user did not exist.
EX_NOHOST = 68       # Specified host did not exist.
EX_UNAVAILABLE = 69  # Required service is unavailable.
EX_SOFTWARE = 70     # Internal software error was detected.
EX_OSERR = 71        # Operating system error was detected, such as the inability to fork or create a pipe.
EX_OSFILE = 72       # Some system file did not exist, could not be opened, or had some other kind of error.
EX_CANTCREAT = 73    # User specified output file could not be created.
EX_IOERR = 74        # Error occurred while doing I/O on some file.
EX_TEMPFAIL = 75     # Temporary failure occurred. This indicates something that may not really be an error,
                     # such as a network connection that couldn’t be made during a retryable operation.
EX_PROTOCOL = 76     # Protocol exchange was illegal, invalid, or not understood.
EX_NOPERM = 77       # Insufficient permissions to perform the operation (but not intended for file system problems).
EX_CONFIG = 78       # Configuration error occurred.
EX_NOTFOUND = 79     # Means something like “an entry was not found”.

# The Salt specific exit codes are defined within the range 200~220:

EX_THIN_PYTHON_INVALID = 200  # SaltSSH python interpreter invalid
EX_THIN_DEPLOY = 201          # SaltSSH thin archive deploy failure
EX_THIN_CHECKSUM = 202        # SaltSSH thin archive checksum do not match
EX_MOD_DEPLOY = 203           # SaltSSH thin archive module deployment failure
EX_SCP_NOT_FOUND = 204        # SaltSSH 'scp' command was not found
EX_AGGREGATE = 205            # SaltSSH One of a collection failed

SALT_BUILD_FAIL = 210  # Salt fails to build something, e.g. a container
SALT_KEEPALIVE = 211   # Keepalive exit code is a hint that the process should be restarted

EX_CLI_ERR = 212    # State contains at least one failed process
EX_CLI_FAIL = 213   # State contains at least one crashed process
