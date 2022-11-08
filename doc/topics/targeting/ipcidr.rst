.. _targeting-ipcidr:

==========================
Subnet/IP Address Matching
==========================

Minions can easily be matched based on IP address, or by subnet (using CIDR_
notation).

.. code-block:: bash

    salt -S 192.168.40.20 test.version
    salt -S 2001:db8::/64 test.version

Ipcidr matching can also be used in compound matches

.. code-block:: bash

    salt -C 'S@10.0.0.0/24 and G@os:Debian' test.version

It is also possible to use in both pillar and state-matching

.. code-block:: yaml

  '172.16.0.0/12':
     - match: ipcidr
     - internal

.. _CIDR: https://en.wikipedia.org/wiki/Classless_Inter-Domain_Routing
