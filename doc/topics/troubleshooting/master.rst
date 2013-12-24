===============================
Troubleshooting the Salt Master
===============================

Running in the Foreground
=========================

A great deal of information is available via the debug logging system, if you
are having issues with minions connecting or not starting run the master in
the foreground:

.. code-block:: bash

  salt-master -l debug

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
that your minion has connected, it could very well be a firewall.

There is also a :doc:`firewall configuration</topics/tutorials/firewall>`
document that might help as well.

If you've enabled the right TCP ports on your operating system or Linux
distribution's firewall and still aren't seeing connections, check that no
additional access control system such as `SELinux`_ or `AppArmor`_ is blocking
Salt.

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

And modify that value to be at least equal to the number of minions x 2.
This setting can be changed in limits.conf as the nofile value(s),
and activated upon new a login of the specified user.

So, an environment with 1800 minions, would need 1800 x 2 = 3600 as a minimum.
To set this value add the following line to your ``/etc/security/limits.conf``
if running Salt as the root user:

.. code-block:: bash
    
    root        hard    nofile        3600
    root        soft    nofile        3600

.. note::

    The above is simply an example of how to set these values, and you may
    wish to increase them if your Salt master is doing more than just running
    Salt.

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

If the master seems to be unresponsive, a SIGUSR1 can be passed to
the processes to display where in the code they are running. If encountering a
situation like this, this debug information can be invaluable. First make
sure the master is running in the foreground:

.. code-block:: bash

    salt-master -l debug

Then pass the signal to the master when it seems to be unresponsive:

.. code-block:: bash

    killall -SIGUSR1 salt-master

When filing an issue or sending questions to the mailing list for a problem
with an unresponsive daemon this information can be invaluable.
