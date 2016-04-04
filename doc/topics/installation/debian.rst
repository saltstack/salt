.. _installation-debian:

===========================
Debian GNU/Linux / Raspbian
===========================

Debian GNU/Linux distribution and some devariatives such as Raspbian already
have included Salt packages to their repositories. However, current stable
release codenamed "Jessie" contains old outdated Salt release. It is
recommended to use SaltStack repository for Debian as described
:ref:`below <installation-debian-repo>`.

Installation from official Debian and Raspbian repositories is described
:ref:`here <installation-debian-raspbian>`.

.. _installation-debian-repo:

Installation from the Official SaltStack Repository
===================================================

Packages for Debian 8 (Jessie) and Debian 7 (Wheezy) are available in the
Official SaltStack repository.

Instructions are at http://repo.saltstack.com/#debian.

Installation from the Community-Maintained Repository
=====================================================

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

For Wheezy, the following line is needed in either
``/etc/apt/sources.list`` or a file in ``/etc/apt/sources.list.d``:

.. code-block:: bash

    deb http://debian.saltstack.com/debian wheezy-saltstack main

Squeeze (Old Old Stable)
------------------------

For Squeeze, you will need to enable the Debian backports repository
as well as the debian.saltstack.com repository. To do so, add the
following to ``/etc/apt/sources.list`` or a file in
``/etc/apt/sources.list.d``:

.. code-block:: bash

    deb http://debian.saltstack.com/debian squeeze-saltstack main
    deb http://backports.debian.org/debian-backports squeeze-backports main

Stretch (Testing)
-----------------

For Stretch, the following line is needed in either
``/etc/apt/sources.list`` or a file in ``/etc/apt/sources.list.d``:

.. code-block:: bash

    deb http://debian.saltstack.com/debian stretch-saltstack main

Sid (Unstable)
--------------

For Sid, the following line is needed in either
``/etc/apt/sources.list`` or a file in ``/etc/apt/sources.list.d``:

.. code-block:: bash

    deb http://debian.saltstack.com/debian unstable main

Import the repository key
-------------------------

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

.. _installation-debian-raspbian:

Installation from the Debian / Raspbian Official Repository
===========================================================

Stretch (Testing) and Sid (Unstable) distributions are already contain mostly
up-to-date Salt packages built by Debian Salt Team. You can install Salt
components directly from Debian.

On Jessie (Stable) there is an option to install Salt minion from Stretch with
`python-tornado` dependency from `jessie-backports` repositories.

To install fresh release of Salt minion on Jessie:

#. Add `jessie-backports` and `stretch` repositories:

   **Debian**:

   .. code-block:: bash

       echo 'deb http://httpredir.debian.org/debian jessie-backports main' >> /etc/apt/sources.list
       echo 'deb http://httpredir.debian.org/debian stretch main' >> /etc/apt/sources.list

   **Raspbian**:

   .. code-block:: bash

       echo 'deb http://archive.raspbian.org/raspbian/ stretch main' >> /etc/apt/sources.list

#. Make Jessie a default release:

   .. code-block:: bash

       echo 'APT::Default-Release "jessie";' > /etc/apt/apt.conf.d/10apt

#. Install Salt dependencies:

   **Debian**:

   .. code-block:: bash

       apt-get update
       apt-get install python-zmq python-tornado/jessie-backports salt-common/stretch

   **Raspbian**:

   .. code-block:: bash

       apt-get update
       apt-get install python-zmq python-tornado/stretch salt-common/stretch

#. Install Salt minion package from Stretch:

   .. code-block:: bash

       apt-get install salt-minion/stretch

.. _debian-install-pkgs:

Install Packages
================

Install the Salt master, minion or other packages from the repository with
the `apt-get` command. These examples each install one of Salt components, but
more than one package name may be given at a time:

- ``apt-get install salt-api``
- ``apt-get install salt-cloud``
- ``apt-get install salt-master``
- ``apt-get install salt-minion``
- ``apt-get install salt-ssh``
- ``apt-get install salt-syndic``

.. _debian-config:

Post-installation tasks
=======================

Now, go to the :doc:`Configuring Salt </ref/configuration/index>` page.
