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

    # Import the salt client library
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
    as either a pcre regular expression or as a python list.

.. cmdoption:: fun

    The name of the function to call on the specified minions. The
    documentation for these functions can be seen by running on the
    salt-master: salt '*' sys.doc

.. cmdoption:: arg

    The optional arg parameter is used to pass a list of options on to the
    remote function

.. cmdoption:: timeout

    The number of seconds to wait after the last minion returns but before all
    minions return.

.. cmdoption:: expr_form

    The type of tgt that is passed in, the allowed values are:

    * 'glob' - Bash glob completion - Default
    * 'pcre' - Perl style regular expression
    * 'list' - Python list of hosts

Compound Command Execution With the Salt API
============================================

The Salt client API can also send what is called a compound command. Often
a collection of commands need to be executed on the targeted minions, rather
than send the commands one after another, they can be send in a single publish
containing a series of commands. This can dramatically lower overhead and
speed up the application communicating with Salt.

When commands are executed with compound execution the minion functions called
are executed in serial on the minion and the return value is sent back in a
different fashion. The return value is a dict, with the function names as keys
to the function returns as values.

Using the compound command execution system via the API requires that the fun
value and the arg value are lists matching by index. This ensures that the
order of the executions can be controlled. Any function that has no arguments
MUST have an empty array in the corresponding arg index.

.. code-block:: python

    # Import the salt client library
    import salt.client
    # create a local client object
    client = salt.client.LocalClient()
    # make compound execution calls with the cmd method
    ret = client.cmd('*', ['cmd.run', 'test.ping', 'test.echo'], [['ls -l'], [], ['foo']])

This will execute ``cmd.run ls -l`` then ``test.ping`` and finally
``test.echo foo``.
The return data from the minion will look like this:

.. code-block:: python

    {'cmd.run': '<output from ls -l>',
     'test.ping': True,
     'test.echo': 'foo'}
