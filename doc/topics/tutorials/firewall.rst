================================
Opening the Firewall up for Salt
================================

The Salt master communicates with the minions using an AES-encrypted ZeroMQ
connection. These communications are done over TCP ports **4505** and **4506**,
which need to be accessible on the master only. This document outlines suggested
firewall rules for allowing these incoming connections to the master.

.. note::

    No firewall configuration needs to be done on Salt minions. These changes
    refer to the master only.

Fedora 18 and beyond / RHEL 7 / CentOS 7
========================================

Starting with Fedora 18 `FirewallD`_ is the tool that is used to dynamically
manage the firewall rules on a host. It has support for IPv4/6 settings and
the separation of runtime and permanent configurations. To interact with
FirewallD use the command line client ``firewall-cmd``.

**firewall-cmd example**:

.. code-block:: bash

    firewall-cmd --permanent --zone=<zone> --add-port=4505-4506/tcp

Please choose the desired zone according to your setup. Don't forget to reload
after you made your changes.

.. code-block:: bash

    firewall-cmd --reload

.. _`FirewallD`: https://fedoraproject.org/wiki/FirewallD

RHEL 6 / CentOS 6
=================

The ``lokkit`` command packaged with some Linux distributions makes opening
iptables firewall ports very simple via the command line. Just be careful
to not lock out access to the server by neglecting to open the ssh port.

**lokkit example**:

.. code-block:: bash

   lokkit -p 22:tcp -p 4505:tcp -p 4506:tcp

The ``system-config-firewall-tui`` command provides a text-based interface to
modifying the firewall.

**system-config-firewall-tui**:

.. code-block:: bash

   system-config-firewall-tui


openSUSE
========

Salt installs firewall rules in :blob:`/etc/sysconfig/SuSEfirewall2.d/services/salt <pkg/suse/salt.SuSEfirewall2>`.
Enable with:

.. code-block:: bash

    SuSEfirewall2 open
    SuSEfirewall2 start

If you have an older package of Salt where the above configuration file is
not included, the ``SuSEfirewall2`` command makes opening iptables firewall
ports very simple via the command line.

**SuSEfirewall example**:

.. code-block:: bash

   SuSEfirewall2 open EXT TCP 4505
   SuSEfirewall2 open EXT TCP 4506

The firewall module in YaST2 provides a text-based interface to modifying the
firewall.

**YaST2**:

.. code-block:: bash

   yast2 firewall

.. _linux-iptables:

iptables
========

Different Linux distributions store their `iptables` (also known as
`netfilter`_) rules in different places, which makes it difficult to
standardize firewall documentation. Included are some of the more
common locations, but your mileage may vary.

.. _`netfilter`: http://www.netfilter.org/

**Fedora / RHEL / CentOS**:

.. code-block:: bash

    /etc/sysconfig/iptables

**Arch Linux**:

.. code-block:: bash

    /etc/iptables/iptables.rules

**Debian**

Follow these instructions: https://wiki.debian.org/iptables

Once you've found your firewall rules, you'll need to add the two lines below
to allow traffic on ``tcp/4505`` and ``tcp/4506``:

.. code-block:: bash

    -A INPUT -m state --state new -m tcp -p tcp --dport 4505 -j ACCEPT
    -A INPUT -m state --state new -m tcp -p tcp --dport 4506 -j ACCEPT

**Ubuntu**

Salt installs firewall rules in :blob:`/etc/ufw/applications.d/salt.ufw
<pkg/salt.ufw>`. Enable with:

.. code-block:: bash

    ufw allow salt

pf.conf
=======

The BSD-family of operating systems uses `packet filter (pf)`_. The following
example describes the additions to ``pf.conf`` needed to access the Salt
master.

.. code-block:: bash

    pass in on $int_if proto tcp from any to $int_if port 4505
    pass in on $int_if proto tcp from any to $int_if port 4506

Once these additions have been made to the ``pf.conf`` the rules will need to
be reloaded. This can be done using the ``pfctl`` command.

.. code-block:: bash

    pfctl -vf /etc/pf.conf

.. _`packet filter (pf)`: http://openbsd.org/faq/pf/

=================================
Whitelist communication to Master
=================================

There are situations where you want to selectively allow Minion traffic
from specific hosts or networks into your Salt Master. The first
scenario which comes to mind is to prevent unwanted traffic to your
Master out of security concerns, but another scenario is to handle
Minion upgrades when there are backwards incompatible changes between
the installed Salt versions in your environment.

Here is an example :ref:`Linux iptables <linux-iptables>` ruleset to
be set on the Master:

.. code-block:: bash

    # Allow Minions from these networks
    -I INPUT -s 10.1.2.0/24 -p tcp -m multiport --dports 4505,4506 -j ACCEPT
    -I INPUT -s 10.1.3.0/24 -p tcp -m multiport --dports 4505,4506 -j ACCEPT
    # Allow Salt to communicate with Master on the loopback interface
    -A INPUT -i lo -p tcp -m multiport --dports 4505,4506 -j ACCEPT
    # Reject everything else
    -A INPUT -p tcp -m multiport --dports 4505,4506 -j REJECT

.. note::

    The important thing to note here is that the ``salt`` command
    needs to communicate with the listening network socket of
    ``salt-master`` on the *loopback* interface. Without this you will
    see no outgoing Salt traffic from the master, even for a simple
    ``salt '*' test.ping``, because the ``salt`` client never reached
    the ``salt-master`` to tell it to carry out the execution.