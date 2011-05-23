=================
Python client API
=================

Salt is written to be completely API centric, Salt minions and master can be
built directly into third party applications as a communication layer. The Salt
client API is very straightforward.

Using the LocalClient API
=========================

Sending information through the client is simple:

.. code-block:: python

    # Import the salt client librairy
    import salt.client
    # create a local client object
    client = salt.client.LocalClient()
    # make calls with the cmd method
    ret = client.cmd('*', 'cmd.run', ['ls -l'])

The cmd call is the only one needed for the local client, the arguments are as
follows:

.. function:: LocalClient.cmd(tgt, fun, arg=[], timeout=5, expr_form='glob')

The LocalClient object only works running as root on the salt-master, it is the
same interface used by the salt command line tool. The arguments are as
follows.

.. cmdoption:: tgt

    The tgt option is the target specification, by default a target is passed
    in as a bash shell glob. The expr_form option allows the tgt to be passed
    as either a pcre regular expresion or as a python list.

.. cmdoption:: fun

    The name of the function to call on the specified minions. The
    documentation for these functions can be seen by running on the
    salt-master: salt '*' sys.doc

.. cmdoption:: arg

    The optional arg paramater is used to pass a list of options on to the
    remote function

.. cmdoption:: timeout

    The number of seconds to wait after the last minion returns but before all
    minions return.

.. cmdoption:: expr_form

    The type of tgt that is passed in, the allowed values are:

    * 'glob' - Bash glob completion - Default
    * 'pcre' - Perl style regular expresion
    * 'list' - Python list of hosts
