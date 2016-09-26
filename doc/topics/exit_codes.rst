.. _exit-codes:

========================
Salt :index:`Exit Codes`
========================

The `exitcodes` definitions and values are found in :py:func:`exitcodes
<salt.defaults.exitcodes>`.

Command Line Executables - Exit Status
======================================

Command line executables provide an `exit code`_ or status upon process termination.  This
is an integer value that, on POSIX systems, is often truncated to an 8-bit, signed
integer.  Process "success" is represented with an exit code of zero (0) and "failure"
situations are represented by non-zero values.

Salt executables (`salt`, `salt-master`, `salt-minion`, etc.) adhere to the zero/non-zero
model with specific failure circumstances represented by specific values.  Additional,
more-detailed failure information is possibly available as messages to `stderr` and/or
logging channels.


`salt`
------

The exit code of the `salt` executable not only represents success or failure in its
execution but also represents the success or failure of minion commands and states.  This
allows aggregate failures in minion processes to be represented as a non-zero exit for
easy integration in scripts calling the `salt` executable.

Command line arguments change this behavior:

:--retcode-passthrough: Minion failures will cause a non-zero exit status for the `salt`
                        executable.

:--cli-retcode: The exit status of the `salt` executable only represents the correctness
                of its execution and minion failures will not cause a non-zero exit
                status.

For both behaviors minion success/failure information is recorded in the job cache and can
be queried using `salt-run jobs.*` and other techniques.  When there are failures in
minions as well as the `salt` executable then executable failures have precedence in being
represented by the exit code.


Salt Modules - `retcode`
========================

Minion command results are returned in a dictionary with a `retcode` key and associated
value that represents success or failure.  The `retcode` must be a value specified in
`exitcodes <salt.defaults.exitcodes>` with `EX_OK` representing success and any of the
other values representing a nuanced form of failure.


.. _`exit code`: https://en.wikipedia.org/wiki/Exit_status
