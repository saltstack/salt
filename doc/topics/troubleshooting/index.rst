.. _troubleshooting:

===============
Troubleshooting
===============

The intent of the troubleshooting section is to introduce solutions to a
number of common issues encountered by users and the tools that are available
to aid in developing States and Salt code.

Troubleshooting the Salt Master
===============================

If your Salt master is having issues such as minions not returning data, slow
execution times, or a variety of other issues, the following links contain
details on troubleshooting the most common issues encountered:

.. toctree::
    :maxdepth: 2

    master

Troubleshooting the Salt Minion
===============================

In the event that your Salt minion is having issues, a variety of solutions
and suggestions are available. Please refer to the following links for more information:

.. toctree::
    :maxdepth: 2

    minion

Running in the Foreground
=========================

A great deal of information is available via the debug logging system, if you
are having issues with minions connecting or not starting run the minion and/or
master in the foreground:

.. code-block:: bash

  salt-master -l debug
  salt-minion -l debug

Anyone wanting to run Salt daemons via a process supervisor such as `monit`_,
`runit`_, or `supervisord`_, should omit the ``-d`` argument to the daemons and
run them in the foreground.

.. _`monit`: http://mmonit.com/monit/
.. _`runit`: http://smarden.org/runit/
.. _`supervisord`: http://supervisord.org/

What Ports do the Master and Minion Need Open?
==============================================

No ports need to be opened up on each minion. For the master, TCP ports 4505
and 4506 need to be open. If you've put both your Salt master and minion in
debug mode and don't see an acknowledgment that your minion has connected,
it could very well be a firewall.

You can check port connectivity from the minion with the nc command:

.. code-block:: bash

  nc -v -z salt.master.ip 4505
  nc -v -z salt.master.ip 4506

There is also a :ref:`firewall configuration<firewall>`
document that might help as well.

If you've enabled the right TCP ports on your operating system or Linux
distribution's firewall and still aren't seeing connections, check that no
additional access control system such as `SELinux`_ or `AppArmor`_ is blocking
Salt.

.. _`SELinux`: https://en.wikipedia.org/wiki/Security-Enhanced_Linux
.. _`AppArmor`: http://wiki.apparmor.net/index.php/Main_Page


.. _using-salt-call:

Using salt-call
===============

The ``salt-call`` command was originally developed for aiding in the development
of new Salt modules. Since then, many applications have been developed for
running any Salt module locally on a minion. These range from the original
intent of salt-call, development assistance, to gathering more verbose output
from calls like :mod:`state.apply <salt.modules.state.apply_>`.

When initially creating your state tree, it is generally recommended to invoke
:mod:`state.apply <salt.modules.state.apply_>` directly from the minion with
``salt-call``, rather than remotely from the master. This displays far more
information about the execution than calling it remotely. For even more
verbosity, increase the loglevel using the ``-l`` argument:

.. code-block:: bash

    salt-call -l debug state.apply

The main difference between using ``salt`` and using ``salt-call`` is that
``salt-call`` is run from the minion, and it only runs the selected function on
that minion. By contrast, ``salt`` is run from the master, and requires you to
specify the minions on which to run the command using salt's :ref:`targeting
system <targeting>`.

Too many open files
===================

The salt-master needs at least 2 sockets per host that connects to it, one for
the Publisher and one for response port. Thus, large installations may, upon
scaling up the number of minions accessing a given master, encounter:

.. code-block:: bash

    12:45:29,289 [salt.master    ][INFO    ] Starting Salt worker process 38
    Too many open files
    sock != -1 (tcp_listener.cpp:335)

The solution to this would be to check the number of files allowed to be
opened by the user running salt-master (root by default):

.. code-block:: bash

    [root@salt-master ~]# ulimit -n
    1024

And modify that value to be at least equal to the number of minions x 2.
This setting can be changed in limits.conf as the nofile value(s),
and activated upon new a login of the specified user.

So, an environment with 1800 minions, would need 1800 x 2 = 3600 as a minimum.


Salt Master Stops Responding
============================

There are known bugs with ZeroMQ versions less than 2.1.11 which can cause the
Salt master to not respond properly. If you're running a ZeroMQ version greater
than or equal to 2.1.9, you can work around the bug by setting the sysctls
``net.core.rmem_max`` and ``net.core.wmem_max`` to 16777216. Next, set the third
field in ``net.ipv4.tcp_rmem`` and ``net.ipv4.tcp_wmem`` to at least 16777216.

You can do it manually with something like:

.. code-block:: bash

    # echo 16777216 > /proc/sys/net/core/rmem_max
    # echo 16777216 > /proc/sys/net/core/wmem_max
    # echo "4096 87380 16777216" > /proc/sys/net/ipv4/tcp_rmem
    # echo "4096 87380 16777216" > /proc/sys/net/ipv4/tcp_wmem

Or with the following Salt state:

.. code-block:: yaml
    :linenos:

    net.core.rmem_max:
      sysctl:
        - present
        - value: 16777216

    net.core.wmem_max:
      sysctl:
        - present
        - value: 16777216

    net.ipv4.tcp_rmem:
      sysctl:
        - present
        - value: 4096 87380 16777216

    net.ipv4.tcp_wmem:
      sysctl:
        - present
        - value: 4096 87380 16777216

Salt and SELinux
================

Currently there are no SELinux policies for Salt. For the most part Salt runs
without issue when SELinux is running in Enforcing mode. This is because when
the minion executes as a daemon the type context is changed to ``initrc_t``.
The problem with SELinux arises when using salt-call or running the minion in
the foreground, since the type context stays ``unconfined_t``.

This problem is generally manifest in the rpm install scripts when using the
pkg module. Until a full SELinux Policy is available for Salt the solution
to this issue is to set the execution context of ``salt-call`` and
``salt-minion`` to rpm_exec_t:

.. code-block:: bash

    # CentOS 5 and RHEL 5:
    chcon -t system_u:system_r:rpm_exec_t:s0 /usr/bin/salt-minion
    chcon -t system_u:system_r:rpm_exec_t:s0 /usr/bin/salt-call

    # CentOS 6 and RHEL 6:
    chcon system_u:object_r:rpm_exec_t:s0 /usr/bin/salt-minion
    chcon system_u:object_r:rpm_exec_t:s0 /usr/bin/salt-call

This works well, because the ``rpm_exec_t`` context has very broad control over
other types.

Red Hat Enterprise Linux 5
==========================

Salt requires Python 2.6 or 2.7. Red Hat Enterprise Linux 5 and its variants
come with Python 2.4 installed by default. When installing on RHEL 5 from the
`EPEL repository`_ this is handled for you. But, if you run Salt from git, be
advised that its dependencies need to be installed from EPEL and that Salt
needs to be run with the ``python26`` executable.

.. _`EPEL repository`: http://fedoraproject.org/wiki/EPEL

Common YAML Gotchas
===================

An extensive list of YAML idiosyncrasies has been compiled:

.. toctree::
    :maxdepth: 2

    yaml_idiosyncrasies

Live Python Debug Output
========================

If the minion or master seems to be unresponsive, a SIGUSR1 can be passed to
the processes to display where in the code they are running. If encountering a
situation like this, this debug information can be invaluable. First make
sure the master of minion are running in the foreground:

.. code-block:: bash

    salt-master -l debug
    salt-minion -l debug

Then pass the signal to the master or minion when it seems to be unresponsive:

.. code-block:: bash

    killall -SIGUSR1 salt-master
    killall -SIGUSR1 salt-minion

Also under BSD and macOS in addition to SIGUSR1 signal, debug subroutine set
up for SIGINFO which has an advantage of being sent by Ctrl+T shortcut.

When filing an issue or sending questions to the mailing list for a problem
with an unresponsive daemon this information can be invaluable.

Salt 0.16.x minions cannot communicate with a 0.17.x master
===========================================================

As of release 0.17.1 you can no longer run different versions of Salt on your
Master and Minion servers. This is due to a protocol change for security
purposes. The Salt team will continue to attempt to ensure versions are as
backwards compatible as possible.


Debugging the Master and Minion
===============================

A list of common :ref:`master<troubleshooting-salt-master>` and
:ref:`minion<troubleshooting-minion-salt-call>` troubleshooting steps provide a
starting point for resolving issues you may encounter.
