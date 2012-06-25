=================
Python client API
=================

Salt is written to be completely API centric, Salt minions and master can be
built directly into third party applications as a communication layer. The Salt
client API is very straightforward.

A number of client command methods are available depending on the exact
behaviour desired.

Using the LocalClient API
=========================

Sending information through the client is simple:

.. code-block:: python

    # Import the Salt client library
    import salt.client
    # create a local client object
    client = salt.client.LocalClient()
    # make calls with the cmd method
    ret = client.cmd('*', 'cmd.run', ['ls -l'])


The LocalClient object only works running as root on the salt-master, it is the
same interface used by the ``salt`` command line tool.

.. function:: LocalClient.cmd(tgt, fun, arg=[], timeout=5, expr_form='glob', ret='')

    The cmd method will execute and wait for the timeout period for all minions
    to reply, then it will return all minion data at once.

.. cmdoption:: tgt

    The tgt option is the target specification, by default a target is passed
    in as a bash shell glob. The expr_form option allows the tgt to be passed
    as either a pcre regular expression or as a Python list.

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
    * 'grain' - Match based on a grain comparison
    * 'grain_pcre' - Grain comparison with a regex
    * 'pillar' - Pillar data comparison
    * 'nodegroup' - Match on nodegroup
    * 'range' - Use a Range server for matching
    * 'compound' - Pass a compound match string

.. cmdoption:: ret

    Specify the returner to use. The value passed can be single returner, or
    a comma delimited list of returners to call in order on the minions

.. function:: LocalClient.cmd_cli(tgt, fun, arg=[], timeout=5, verbose=False, expr_form='glob', ret='')

    The cmd_cli method is used by the salt command, it is a generator. This
    method returns minion returns as the come back and attempts to block
    until all minions return.

.. cmdoption:: tgt

    The tgt option is the target specification, by default a target is passed
    in as a bash shell glob. The expr_form option allows the tgt to be passed
    as either a pcre regular expression or as a Python list.

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
    * 'grain' - Match based on a grain comparison
    * 'grain_pcre' - Grain comparison with a regex
    * 'pillar' - Pillar data comparison
    * 'nodegroup' - Match on nodegroup
    * 'range' - Use a Range server for matching
    * 'compound' - Pass a compound match string

.. cmdoption:: ret

    Specify the returner to use. The value passed can be single returner, or
    a comma delimited list of returners to call in order on the minions

.. cmdoption:: verbose

    Print extra information about the running command to the terminal

.. function:: LocalClient.cmd_iter(tgt, fun, arg=[], timeout=5, expr_form='glob', ret='')

    The cmd_iter method is a generator which yields the individual minion
    returns as the come in.

.. cmdoption:: tgt

    The tgt option is the target specification, by default a target is passed
    in as a bash shell glob. The expr_form option allows the tgt to be passed
    as either a pcre regular expression or as a Python list.

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
    * 'grain' - Match based on a grain comparison
    * 'grain_pcre' - Grain comparison with a regex
    * 'pillar' - Pillar data comparison
    * 'nodegroup' - Match on nodegroup
    * 'range' - Use a Range server for matching
    * 'compound' - Pass a compound match string

.. cmdoption:: ret

    Specify the returner to use. The value passed can be single returner, or
    a comma delimited list of returners to call in order on the minions

.. function:: LocalClient.cmd_iter_no_block(tgt, fun, arg=[], timeout=5, expr_form='glob', ret='')

    The cmd_iter method will block waiting for individual minions to return,
    the cmd_iter_no_block method will return None until the next minion
    returns. This allows for actions to be injected in between minion returns

.. cmdoption:: tgt

    The tgt option is the target specification, by default a target is passed
    in as a bash shell glob. The expr_form option allows the tgt to be passed
    as either a pcre regular expression or as a Python list.

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
    * 'grain' - Match based on a grain comparison
    * 'grain_pcre' - Grain comparison with a regex
    * 'pillar' - Pillar data comparison
    * 'nodegroup' - Match on nodegroup
    * 'range' - Use a Range server for matching
    * 'compound' - Pass a compound match string

.. cmdoption:: ret

    Specify the returner to use. The value passed can be single returner, or
    a comma delimited list of returners to call in order on the minions

Compound Command Execution With the Salt API
============================================

The Salt client API can also send what is called a compound command. Often
a collection of commands need to be executed on the targeted minions, rather
than send the commands one after another, they can be sent in a single publish
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

All client command methods can execute compound commands.

.. code-block:: python

    # Import the Salt client library
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

Salt Caller API
===============

The Salt minion caller api can be used to simplify the execution and use of
minion elements. The caller api is useful for accessing the Salt api, direct
access to the state functions, using the matcher interface on a single minion,
and as an api for the peer interface. Using the api is fairly straightforward:

.. code-block:: yaml

    # Import the Salt client library
    import salt.client
    # Create the caller object
    caller = salt.client.Caller()
    # call a function
    caller.function('test.ping')
    # Call objects directly:
    caller.sminion.functions['cmd.run']('ls -l')
