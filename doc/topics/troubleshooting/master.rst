.. _troubleshooting-salt-master:

===============================
Troubleshooting the Salt Master
===============================

Running in the Foreground
=========================

A great deal of information is available via the debug logging system, if you
are having issues with minions connecting or not starting run the master in
the foreground:

.. code-block:: bash

    # salt-master -l debug

Anyone wanting to run Salt daemons via a process supervisor such as `monit`_,
`runit`_, or `supervisord`_, should omit the ``-d`` argument to the daemons and
run them in the foreground.

.. _`monit`: http://mmonit.com/monit/
.. _`runit`: http://smarden.org/runit/
.. _`supervisord`: http://supervisord.org/

What Ports does the Master Need Open?
=====================================

For the master, TCP ports 4505 and 4506 need to be open. If you've put both
your Salt master and minion in debug mode and don't see an acknowledgment
that your minion has connected, it could very well be a firewall interfering
with the connection. See our :ref:`firewall configuration
<firewall>` page for help opening the firewall on various
platforms.

If you've opened the correct TCP ports and still aren't seeing connections,
check that no additional access control system such as `SELinux`_ or
`AppArmor`_ is blocking Salt.

.. _`SELinux`: https://en.wikipedia.org/wiki/Security-Enhanced_Linux
.. _`AppArmor`: http://wiki.apparmor.net/index.php/Main_Page

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

If this value is not equal to at least twice the number of minions, then it
will need to be raised. For example, in an environment with 1800 minions, the
``nofile`` limit should be set to no less than 3600. This can be done by
creating the file ``/etc/security/limits.d/99-salt.conf``, with the following
contents::

    root        hard    nofile        4096
    root        soft    nofile        4096

Replace ``root`` with the user under which the master runs, if different.

If your master does not have an ``/etc/security/limits.d`` directory, the lines
can simply be appended to ``/etc/security/limits.conf``.

As with any change to resource limits, it is best to stay logged into your
current shell and open another shell to run ``ulimit -n`` again and verify that
the changes were applied correctly. Additionally, if your master is running
upstart, it may be necessary to specify the ``nofile`` limit in
``/etc/default/salt-master`` if upstart isn't respecting your resource limits:

.. code-block:: text

    limit nofile 4096 4096

.. note::

    The above is simply an example of how to set these values, and you may
    wish to increase them even further if your Salt master is doing more than
    just running Salt.

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

Live Python Debug Output
========================

If the master seems to be unresponsive, a SIGUSR1 can be passed to the
salt-master threads to display what piece of code is executing. This debug
information can be invaluable in tracking down bugs.

To pass a SIGUSR1 to the master, first make sure the minion is running in the
foreground. Stop the service if it is running as a daemon, and start it in the
foreground like so:

.. code-block:: bash

    # salt-master -l debug

Then pass the signal to the master when it seems to be unresponsive:

.. code-block:: bash

    # killall -SIGUSR1 salt-master

When filing an issue or sending questions to the mailing list for a problem
with an unresponsive daemon, be sure to include this information if possible.


Live Salt-Master Profiling
==========================

When faced with performance problems one can turn on master process profiling by
sending it SIGUSR2.

.. code-block:: bash

    # killall -SIGUSR2 salt-master

This will activate ``yappi`` profiler inside salt-master code, then after some
time one must send SIGUSR2 again to stop profiling and save results to file. If
run in foreground salt-master will report filename for the results, which are
usually located under ``/tmp`` on Unix-based OSes and ``c:\temp`` on windows.

Results can then be analyzed with `kcachegrind`_ or similar tool.

.. _`kcachegrind`: http://kcachegrind.sourceforge.net/html/Home.html


Commands Time Out or Do Not Return Output
=========================================

Depending on your OS (this is most common on Ubuntu due to apt-get) you may
sometimes encounter times where a :py:func:`state.apply
<salt.modules.state.apply_>`, or other long running commands do not return
output.

By default the timeout is set to 5 seconds. The timeout value can easily be
increased by modifying the ``timeout`` line within your ``/etc/salt/master``
configuration file.

Having keys accepted for Salt minions that no longer exist or are not reachable
also increases the possibility of timeouts, since the Salt master waits for
those systems to return command results.

Passing the -c Option to Salt Returns a Permissions Error
=========================================================

Using the ``-c`` option with the Salt command modifies the configuration
directory. When the configuration file is read it will still base data off of
the ``root_dir`` setting. This can result in unintended behavior if you are
expecting files such as ``/etc/salt/pki`` to be pulled from the location
specified with ``-c``. Modify the ``root_dir`` setting to address this
behavior.

Salt Master Doesn't Return Anything While Running jobs
======================================================

When a command being run via Salt takes a very long time to return
(package installations, certain scripts, etc.) the master may drop you back
to the shell. In most situations the job is still running but Salt has
exceeded the set timeout before returning. Querying the job queue will
provide the data of the job but is inconvenient. This can be resolved by
either manually using the ``-t`` option to set a longer timeout when running
commands (by default it is 5 seconds) or by modifying the master
configuration file: ``/etc/salt/master`` and setting the ``timeout`` value to
change the default timeout for all commands, and then restarting the
salt-master service.

Salt Master Auth Flooding
=========================

In large installations, care must be taken not to overwhealm the master with
authentication requests. Several options can be set on the master which
mitigate the chances of an authentication flood from causing an interruption in
service.

.. note::
    recon_default:

    The average number of seconds to wait between reconnection attempts.

    recon_max:
       The maximum number of seconds to wait between reconnection attempts.

    recon_randomize:
        A flag to indicate whether the recon_default value should be randomized.

    acceptance_wait_time:
        The number of seconds to wait for a reply to each authentication request.

    random_reauth_delay:
        The range of seconds across which the minions should attempt to randomize
        authentication attempts.

    auth_timeout:
        The total time to wait for the authentication process to complete, regardless
        of the number of attempts.


=====================
Running state locally
=====================

To debug the states, you can use call locally.

.. code-block:: bash

    salt-call -l trace --local state.highstate


The top.sls file is used to map what SLS modules get loaded onto what minions via the state system.

It is located in the file defined in the ``file_roots`` variable of the salt master
configuration file which is defined by found in ``CONFIG_DIR/master``, normally ``/etc/salt/master``

The default configuration for the ``file_roots`` is:

.. code-block:: yaml

   file_roots:
     base:
       - /srv/salt

So the top file is defaulted to the location ``/srv/salt/top.sls``


Salt Master Umask
=================

The salt master uses a cache to track jobs as they are published and returns come back.
The recommended umask for a salt-master is `022`, which is the default for most users
on a system. Incorrect umasks can result in permission-denied errors when the master
tries to access files in its cache.
