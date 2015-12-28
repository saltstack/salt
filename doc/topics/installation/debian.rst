.. _installation-debian:

===================
Debian Installation
===================

.. _installation-debian-repo:

Installation from the SaltStack Repository
==========================================

2015.5 and later packages for Debian 8 (Jessie) are available in the
SaltStack repository.

.. important::
  The repository folder structure changed in the 2015.8.3 release, though the
  previous repository structure that was documented in 2015.8.1 can continue to
  be used.

To install using the SaltStack repository:

#. Run the following command to import the SaltStack repository key:

   .. code-block:: bash

       wget -O - https://repo.saltstack.com/apt/debian/8/amd64/latest/SALTSTACK-GPG-KEY.pub | sudo apt-key add -

#. Add the following line to ``/etc/apt/sources.list``:

   .. code-block:: bash

       deb http://repo.saltstack.com/apt/debian/8/amd64/latest jessie main

#. Run ``sudo apt-get update``.

#. Install the salt-minion, salt-master, or other Salt components:

   - ``apt-get install salt-master``
   - ``apt-get install salt-minion``
   - ``apt-get install salt-ssh``
   - ``apt-get install salt-syndic``
   - ``apt-get install salt-cloud``

Post-installation tasks
-----------------------

Now, go to the :doc:`Configuring Salt </ref/configuration/index>` page.

Installation from the Community Repository
==========================================

The SaltStack community maintains a Debian repository at debian.saltstack.com.
Packages for Debian Old Stable, Stable, and Unstable (Wheezy, Jessie, and Sid)
for Salt 0.16 and later are published in this repository.

.. note::
   Packages in this repository are community built, and it can
   take a little while until the latest SaltStack release is available
   in this repository.

Jessie (Stable)
---------------

For Jessie, the following line is needed in either
``/etc/apt/sources.list`` or a file in ``/etc/apt/sources.list.d``:

.. code-block:: bash

    deb http://debian.saltstack.com/debian jessie-saltstack main

Wheezy (Old Stable)
-------------------

For wheezy, the following line is needed in either
``/etc/apt/sources.list`` or a file in ``/etc/apt/sources.list.d``:

.. code-block:: bash

    deb http://debian.saltstack.com/debian wheezy-saltstack main

Squeeze (Old Old Stable)
------------------------

For squeeze, you will need to enable the Debian backports repository
as well as the debian.saltstack.com repository. To do so, add the
following to ``/etc/apt/sources.list`` or a file in
``/etc/apt/sources.list.d``:

.. code-block:: bash

    deb http://debian.saltstack.com/debian squeeze-saltstack main
    deb http://backports.debian.org/debian-backports squeeze-backports main

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

   - ``apt-get install salt-master``
   - ``apt-get install salt-minion``
   - ``apt-get install salt-ssh``
   - ``apt-get install salt-syndic``

.. _Debian-config:

Post-installation tasks
-----------------------

Now, go to the :doc:`Configuring Salt </ref/configuration/index>` page.

