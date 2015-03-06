===================
Debian Installation
===================

Currently the latest packages for Debian Old Stable, Stable, and
Unstable (Squeeze, Wheezy, and Sid) are published in our
(saltstack.com) Debian repository.

Configure Apt
-------------


Squeeze (Old Stable)
--------------------

For squeeze, you will need to enable the Debian backports repository
as well as the debian.saltstack.com repository. To do so, add the
following to ``/etc/apt/sources.list`` or a file in
``/etc/apt/sources.list.d``:

.. code-block:: bash

    deb http://debian.saltstack.com/debian squeeze-saltstack main
    deb http://backports.debian.org/debian-backports squeeze-backports main contrib non-free



Wheezy (Stable)
---------------

For wheezy, the following line is needed in either
``/etc/apt/sources.list`` or a file in ``/etc/apt/sources.list.d``:

.. code-block:: bash

    deb http://debian.saltstack.com/debian wheezy-saltstack main

Jessie (Testing)
----------------

For jessie, the following line is needed in either
``/etc/apt/sources.list`` or a file in ``/etc/apt/sources.list.d``:

.. code-block:: bash

    deb http://debian.saltstack.com/debian jessie-saltstack main

Sid (Unstable)
--------------

For sid, the following line is needed in either
``/etc/apt/sources.list`` or a file in ``/etc/apt/sources.list.d``:

.. code-block:: bash

    deb http://debian.saltstack.com/debian unstable main


Import the repository key.
--------------------------

You will need to import the key used for signing.

.. code-block:: bash

    wget -q -O- "http://debian.saltstack.com/debian-salt-team-joehealy.gpg.key" | apt-key add -

.. note::

    You can optionally verify the key integrity with ``sha512sum`` using the
    public key signature shown here. E.g:

    .. code-block:: bash

        echo "b702969447140d5553e31e9701be13ca11cc0a7ed5fe2b30acb8491567560ee62f834772b5095d735dfcecb2384a5c1a20045f52861c417f50b68dd5ff4660e6  debian-salt-team-joehealy.gpg.key" | sha512sum -c

Update the package database
---------------------------

.. code-block:: bash

    apt-get update


Install packages
----------------

Install the Salt master, minion, or syndic from the repository with the apt-get
command. These examples each install one daemon, but more than one package name
may be given at a time:

.. code-block:: bash

    apt-get install salt-master

.. code-block:: bash

    apt-get install salt-minion

.. code-block:: bash

    apt-get install salt-syndic

.. _Debian-config:

Post-installation tasks
-----------------------

Now, go to the :doc:`Configuring Salt </ref/configuration/index>` page.


Notes
-----

1. These packages will be backported from the packages intended to be
uploaded into Debian unstable. This means that the packages will be
built for unstable first and then backported over the next day or so.

2. These packages will be tracking the released versions of salt
rather than maintaining a stable fixed feature set. If a fixed version
is what you desire, then either pinning or manual installation may be
more appropriate for you.

3. The version numbering and backporting process should provide clean
upgrade paths between Debian versions.

If you have any questions regarding these, please email the mailing
list or look for joehh on IRC.
