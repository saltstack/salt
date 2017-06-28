===============================
Troubleshooting the Salt Minion
===============================

Running in the Foreground
=========================

A great deal of information is available via the debug logging system, if you
are having issues with minions connecting or not starting run the minion in
the foreground:

.. code-block:: bash

    # salt-minion -l debug

Anyone wanting to run Salt daemons via a process supervisor such as `monit`_,
`runit`_, or `supervisord`_, should omit the ``-d`` argument to the daemons and
run them in the foreground.

.. _`monit`: http://mmonit.com/monit/
.. _`runit`: http://smarden.org/runit/
.. _`supervisord`: http://supervisord.org/


What Ports does the Minion Need Open?
=====================================

No ports need to be opened on the minion, as it makes outbound connections to
the master. If you've put both your Salt master and minion in debug mode and
don't see an acknowledgment that your minion has connected, it could very well
be a firewall interfering with the connection. See our :ref:`firewall
configuration <firewall>` page for help opening the firewall
on various platforms.

If you have netcat installed, you can check port connectivity from the minion
with the ``nc`` command:

.. code-block:: bash

    $ nc -v -z salt.master.ip.addr 4505
    Connection to salt.master.ip.addr 4505 port [tcp/unknown] succeeded!
    $ nc -v -z salt.master.ip.addr 4506
    Connection to salt.master.ip.addr 4506 port [tcp/unknown] succeeded!

The `Nmap`_ utility can also be used to check if these ports are open:

.. code-block:: bash

    # nmap -sS -q -p 4505-4506 salt.master.ip.addr

    Starting Nmap 6.40 ( http://nmap.org ) at 2013-12-29 19:44 CST
    Nmap scan report for salt.master.ip.addr (10.0.0.10)
    Host is up (0.0026s latency).
    PORT     STATE  SERVICE
    4505/tcp open   unknown
    4506/tcp open   unknown
    MAC Address: 00:11:22:AA:BB:CC (Intel)

    Nmap done: 1 IP address (1 host up) scanned in 1.64 seconds

If you've opened the correct TCP ports and still aren't seeing connections,
check that no additional access control system such as `SELinux`_ or
`AppArmor`_ is blocking Salt. Tools like `tcptraceroute`_ can also be used
to determine if an intermediate device or firewall is blocking the needed
TCP ports.

.. _`Nmap`: http://nmap.org/
.. _`SELinux`: https://en.wikipedia.org/wiki/Security-Enhanced_Linux
.. _`AppArmor`: http://wiki.apparmor.net/index.php/Main_Page
.. _`tcptraceroute`: http://linux.die.net/man/1/tcptraceroute

.. _troubleshooting-minion-salt-call:

Using salt-call
===============

The ``salt-call`` command was originally developed for aiding in the
development of new Salt modules. Since then, many applications have been
developed for running any Salt module locally on a minion. These range from the
original intent of salt-call (development assistance), to gathering more
verbose output from calls like :mod:`state.apply <salt.modules.state.apply_>`.

When initially creating your state tree, it is generally recommended to invoke
highstates by running :mod:`state.apply <salt.modules.state.apply_>` directly
from the minion with ``salt-call``, rather than remotely from the master. This
displays far more information about the execution than calling it remotely. For
even more verbosity, increase the loglevel using the ``-l`` argument:

.. code-block:: bash

    # salt-call -l debug state.apply

The main difference between using ``salt`` and using ``salt-call`` is that
``salt-call`` is run from the minion, and it only runs the selected function on
that minion. By contrast, ``salt`` is run from the master, and requires you to
specify the minions on which to run the command using salt's :ref:`targeting
system <targeting>`.

Live Python Debug Output
========================

If the minion seems to be unresponsive, a SIGUSR1 can be passed to the process
to display what piece of code is executing. This debug information can be
invaluable in tracking down bugs.

To pass a SIGUSR1 to the minion, first make sure the minion is running in the
foreground. Stop the service if it is running as a daemon, and start it in the
foreground like so:

.. code-block:: bash

    # salt-minion -l debug

Then pass the signal to the minion when it seems to be unresponsive:

.. code-block:: bash

    # killall -SIGUSR1 salt-minion

When filing an issue or sending questions to the mailing list for a problem
with an unresponsive daemon, be sure to include this information if possible.

Multiprocessing in Execution Modules
====================================

As is outlined in github issue #6300, Salt cannot use python's multiprocessing
pipes and queues from execution modules. Multiprocessing from the execution
modules is perfectly viable, it is just necessary to use Salt's event system
to communicate back with the process.

The reason for this difficulty is that python attempts to pickle all objects in
memory when communicating, and it cannot pickle function objects. Since the
Salt loader system creates and manages function objects this causes the pickle
operation to fail.

Salt Minion Doesn't Return Anything While Running Jobs Locally
==============================================================

When a command being run via Salt takes a very long time to return
(package installations, certain scripts, etc.) the minion may drop you back
to the shell. In most situations the job is still running but Salt has
exceeded the set timeout before returning. Querying the job queue will
provide the data of the job but is inconvenient. This can be resolved by
either manually using the ``-t`` option to set a longer timeout when running
commands (by default it is 5 seconds) or by modifying the minion
configuration file: ``/etc/salt/minion`` and setting the ``timeout`` value to
change the default timeout for all commands, and then restarting the
salt-minion service.

.. note::

    Modifying the minion timeout value is not required when running commands
    from a Salt Master. It is only required when running commands locally on
    the minion.
