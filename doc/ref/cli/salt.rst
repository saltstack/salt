.. _ref-cli-salt:

========
``salt``
========

Synopsis
========

    salt '*' [ options ] sys.doc

    salt -E '.*' [ options ] sys.doc cmd

    salt -G 'os:Arch.*' [ options ] test.version

    salt -C 'G@os:Arch.* and webserv* or G@kernel:FreeBSD' [ options ] test.version

Description
===========

Salt allows for commands to be executed across a swath of remote systems in
parallel. This means that remote systems can be both controlled and queried
with ease.

Options
=======

.. program:: salt

.. include:: _includes/common-options.rst

.. include:: _includes/timeout-option.rst
.. |timeout| replace:: 5

.. option:: -s, --static

    By default as of version 0.9.8 the salt command returns data to the
    console as it is received from minions, but previous releases would return
    data only after all data was received. Use the static option to only return
    the data with a hard timeout and after all minions have returned.
    Without the static option, you will get a separate JSON string per minion
    which makes JSON output invalid as a whole.

.. option:: --async

    Instead of waiting for the job to run on minions only print the job id of
    the started execution and complete.

.. option:: --subset=SUBSET

    Execute the routine on a random subset of the targeted minions.  The
    minions will be verified that they have the named function before
    executing. The SUBSET argument is the count of the minions to target.

.. option:: -v VERBOSE, --verbose

    Turn on verbosity for the salt call, this will cause the salt command to
    print out extra data like the job id.

.. option:: --hide-timeout

    Instead of showing the return data for all minions. This option
    prints only the online minions which could be reached.

.. option:: -b BATCH, --batch-size=BATCH

    Instead of executing on all targeted minions at once, execute on a
    progressive set of minions. This option takes an argument in the form of
    an explicit number of minions to execute at once, or a percentage of
    minions to execute on.

.. option:: --batch-wait=BATCH_WAIT

   Wait the specified time in seconds after each job is done before
   freeing the slot in the batch of the next one.

.. option:: --batch-safe-limit=BATCH_SAFE_LIMIT

   Execute the salt job in batch mode if the job would have executed
   on at least this many minions.

.. option:: --batch-safe-size=BATCH_SAFE_SIZE

   Batch size to use for batch jobs created by --batch-safe-limit.

.. option:: -a EAUTH, --auth=EAUTH

    Pass in an external authentication medium to validate against. The
    credentials will be prompted for. The options are `auto`,
    `keystone`, `ldap`, and `pam`. Can be used with the -T
    option.

.. option:: -T, --make-token

    Used in conjunction with the -a option. This creates a token that allows
    for the authenticated user to send commands without needing to
    re-authenticate.

.. option:: --return=RETURNER

    Choose an alternative returner to call on the minion, if an
    alternative returner is used then the return will not come back to
    the command line but will be sent to the specified return system.
    The options are `carbon`, `cassandra`, `couchbase`, `couchdb`,
    `elasticsearch`, `etcd`, `hipchat`, `local`, `local_cache`,
    `memcache`, `mongo`, `mysql`, `odbc`, `postgres`, `redis`,
    `sentry`, `slack`, `sms`, `smtp`, `sqlite3`, `syslog`, and `xmpp`.

.. option:: -d, --doc, --documentation

    Return the documentation for the module functions available on the minions

.. option:: --args-separator=ARGS_SEPARATOR

    Set the special argument used as a delimiter between command arguments of
    compound commands. This is useful when one wants to pass commas as
    arguments to some of the commands in a compound command.

.. include:: _includes/logging-options.rst
.. |logfile| replace:: /var/log/salt/master
.. |loglevel| replace:: ``warning``

.. include:: _includes/target-selection.rst
.. include:: _includes/extended-target-selection.rst

.. include:: _includes/output-options.rst

.. note::
    If using ``--out=json``, you will probably want ``--static`` as well.
    Without the static option, you will get a separate JSON string per minion
    which makes JSON output invalid as a whole.
    This is due to using an iterative outputter. So if you want to feed it
    to a JSON parser, use ``--static`` as well.

See also
========

:manpage:`salt(7)`
:manpage:`salt-master(1)`
:manpage:`salt-minion(1)`
