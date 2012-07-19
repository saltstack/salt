================================
Opening the Firewall up for Salt
================================

The Salt master communicates with the minions using an AES-encrypted ZeroMQ
connection. These communications are done over ports 4505 and 4506, which need
to be accessible on the master only. This document outlines suggested firewall
rules for allowing these incoming connections to the master.

.. note::

    **No firewall configuration needs to be done on Salt minions. These changes
    refer to the master only.**

RHEL 6 / CENTOS 6
=================

The lokkit command packaged with some linux distributions makes opening
iptables firewall ports very simple via the command line. Just be careful
to not lock out access to the server by neglecting to open the ssh
port.

**lokkit example** ::

   lokkit -p 22:tcp -p 4505:tcp -p 4506:tcp

The system-config-firewall-tui command provides a text-based interface to modifying
the firewall.

**system-config-firewall-tui** ::

   system-config-firewall-tui


iptables
========

Different Linux distributions store their `iptables`_ rules in different places,
which makes it difficult to standardize firewall documentation. Included are
some of the more common locations, but your mileage may vary.

**Fedora / RHEL / CentOS** ::

    /etc/sysconfig/iptables

**Arch Linux** ::

    /etc/iptables/iptables.rules

**Debian**

Follow these instructions: http://wiki.debian.org/iptables

Once you've found your firewall rules, you'll need to add the two lines below
to allow traffic on ``tcp/4505`` and ``tcp/4506``:

.. code-block:: diff

    + -A INPUT -m state --state new -m tcp -p tcp --dport 4505 -j ACCEPT
    + -A INPUT -m state --state new -m tcp -p tcp --dport 4506 -j ACCEPT

**Ubuntu**

Create a file named ``/etc/ufw/applications.d/salt-master`` ::

        [Salt Master]
        title=Salt master
        description=Salt is a remote execution and configuration management tool.
        ports=4505,4506/tcp

.. _`iptables`: http://www.netfilter.org/

pf.conf
=======

The BSD-family of operating systems uses `packet filter (pf)`_. The following
example describes the additions to ``pf.conf`` needed to access the Salt
master.

.. code-block:: diff

    + pass in on $int_if proto tcp from any to $int_if port 4505
    + pass in on $int_if proto tcp from any to $int_if port 4506

Once these additions have been made to the ``pf.conf`` the rules will need to
be reloaded. This can be done using the ``pfctl`` command.

.. code-block:: bash

    pfctl -vf /etc/pf.conf

    
.. _`packet filter (pf)`: http://openbsd.org/faq/pf/
