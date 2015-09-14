.. _installation-debian:

===================
Debian Installation
===================

.. _installation-debian-repo:

Installation from the SaltStack Repository
==========================================

Debian 8 packages are available in the SaltStack Debian repository.

To install using the SaltStack Debian repository:

#. Run the following command to import the SaltStack repository key:

   .. code-block:: bash

       wget -O - https://repo.saltstack.com/apt/debian/SALTSTACK-GPG-KEY.pub | apt-key add -

#. Add the following line to ``/etc/apt/sources.list``:

   .. code-block:: bash

       deb http://repo.saltstack.com/apt/debian jessie contrib

#. Run ``sudo apt-get update``

#. Install the salt-minion, salt-master, or other Salt components:

   - ``apt-get install salt-master``
   - ``apt-get install salt-minion``
   - ``apt-get install salt-ssh``
   - ``apt-get install salt-syndic``
   - ``apt-get install salt-cloud``

Configure Apt
-------------

Currently the latest packages for Debian Old Stable, Stable, and
Unstable (Squeeze, Wheezy, and Sid) are published in our
(saltstack.com) Debian repository.

Squeeze (Old Old Stable)
------------------------

For squeeze, you will need to enable the Debian backports repository
as well as the debian.saltstack.com repository. To do so, add the
following to ``/etc/apt/sources.list`` or a file in
``/etc/apt/sources.list.d``:

.. code-block:: bash

    deb http://debian.saltstack.com/debian squeeze-saltstack main
    deb http://backports.debian.org/debian-backports squeeze-backports main



Wheezy (Old Stable)
-------------------

For wheezy, the following line is needed in either
``/etc/apt/sources.list`` or a file in ``/etc/apt/sources.list.d``:

.. code-block:: bash

    deb http://debian.saltstack.com/debian wheezy-saltstack main

Jessie (Stable)
---------------

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


