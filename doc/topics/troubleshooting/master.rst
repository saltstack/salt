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
with the connection. See our :doc:`firewall configuration
</topics/tutorials/firewall>` page for help opening the firewall on various
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
``/etc/default/salt-master`` if upstart isn't respecting your resource limits::

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

Commands Time Out or Do Not Return Output
=========================================

Depending on your OS (this is most common on Ubuntu due to apt-get) you may
sometimes encounter times where your highstate, or other long running commands
do not return output. This is most commonly due to the timeout being reached.
By default the timeout is set to 5 seconds. The timeout value can easily be
increased by modifying the ``timeout`` line within your ``/etc/salt/master``
configuration file.


Passing the -c Option to Salt Returns a Permissions Error
=========================================================

Using the ``-c`` option with the Salt command modifies the configuration
directory. When the configuratio file is read it will still base data off of
the ``root_dir`` setting. This can result in unintended behavior if you are
expecting files such as ``/etc/salt/pki`` to be pulled from the location
specified with ``-c``. Modify the ``root_dir`` setting to address this
behavior.
