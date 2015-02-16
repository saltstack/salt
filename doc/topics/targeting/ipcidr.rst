.. _targeting-ipcidr:

==========================
Subnet/IP Address Matching
==========================

Minions can easily be matched based on IP address, or by subnet (using CIDR_
notation).

.. code-block:: bash

    salt -S 192.168.40.20 test.ping
    salt -S 10.0.0.0/24 test.ping

.. code-block:: yaml

  '172.16.0.0/12':
     - match: ipcidr
     - internal
.. _CIDR: http://en.wikipedia.org/wiki/Classless_Inter-Domain_Routing

.. note::

    Only IPv4 matching is supported at this time.
