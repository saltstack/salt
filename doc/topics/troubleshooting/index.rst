===============
Troubleshooting
===============

The intent of the  troubleshooting section is to introduce solutions to a
number of common issues encountered by users and the tools that are available
to aid in developing states and salt code.

Running in the Foreground
=========================

A great deal of information is available via the debug logging system, if you
are having issues with minions connecting or not starting run the minion and/or
master in the foreground:

.. code-block:: sh

  # salt-master -l debug
  # salt-minion -l debug

Anyone wanting to run salt daemons via a process supervisor such as monit,
runit, or supervisord, should omit the ``-d`` argument to the daemons and
run them in the foreground.


What Ports do the Master and Minion Need Open?
==============================================

No ports need to be opened up on each minion. For the master, tcp ports 4505
and 4506 need to be open. If you've put your salt master and minion both in
debug mode and don't see an acknowledgement that your minion has connected,
it could very well be a firewall.

You can check port connectivity from the minion with the nc command:

.. code-block:: sh

  # nc -v -z salt.master.ip 4505
  # nc -v -z salt.master.ip 4506

There is also a :doc:`firewall configuration</topics/tutorials/firewall>`
document that might help as well.

If you've enabled the right ports on your operating system or Linux
distribution's firewall and still aren't seeing connections, check that no
additional access control such as SELinux or AppArmor are blocking salt.


Using salt-call
===============

The ``salt-call`` command was originally developed for aiding in the development
of new salt modules. Since then, many applications have arisen for running any
salt module locally on a minion. These range from the original intent of
salt-call, development assistance, to gathering more verbose output from calls
like :doc:`state.highstate</ref/modules/all/salt.modules.state>`.

When developing the state tree it is generally recommended to invoke
state.highstate with salt-call. This displays a great deal more information
about the highstate execution than if it is called remotely. For even more
verbosity, increase the loglevel with the same argument as ``salt-minion``:

.. code-block:: sh

    salt-call -l debug state.highstate


Too many open files
===================

The salt-master needs at least 2 sockets per host that connects to it, one for
the Publisher and one for response port. Thus, large installations may upon
scaling up the number of minions accessing a given master, encounter:

.. code-block:: sh

    12:45:29,289 [salt.master    ][INFO    ] Starting Salt worker process 38
    Too many open files
    sock != -1 (tcp_listener.cpp:335)

The solution to this would be to check the number of files allowed to be
opened by the user running salt-master (root by default):

.. code-block:: sh

    [root@salt-master ~]# ulimit -n
    1024

And modify that value to be at least equal to the number of minions x 2.
This setting can be changed in limits.conf as the nofile value(s),
and activated upon new a login of the specified user.

So, an environment with 1800 minions, would need 1800 x 2 = 3600 as a minimum.


Salt Master Stops Responding
============================

There are known bugs with ZeroMQ less than 2.1.11 which can cause the salt
master to not respond properly. If you're running ZeroMQ greater than or equal
to 2.1.9, you can work around the bug by setting the sysctls
``net.core.rmem_max`` and ``net.core.wmem_max`` to 16777216. Next set the third
field in ``net.ipv4.tcp_rmem`` and ``net.ipv4.tcp_wmem`` to at least 16777216.

You can do it manually with something like:

.. code-block:: sh

    # echo 16777216 > /proc/sys/net/core/rmem_max
    # echo 16777216 > /proc/sys/net/core/wmem_max
    # echo "4096 87380 16777216" > /proc/sys/net/ipv4/tcp_rmem
    # echo "4096 87380 16777216" > /proc/sys/net/ipv4/tcp_wmem

Or with the following salt state:

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

Red Hat Enterprise Linux 5
==========================

Salt requires Python 2.6 or 2.7. RHEL 5 and variants come with python 2.4 by
default, when installing on RHEL 5 from the EPEL repository this is handled
for you. But if running Salt from git, be advised that the deps needs to be
installed from EPEL and salt needs to be run with the ``python26`` executable.

Common YAML Gotchas
===================

An extensive list of
:doc:`yaml idiosyncrasies</topics/troubleshooting/yaml_idiosyncrasies>`
has been compiled.
