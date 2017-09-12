.. _installation-debian:

===========================
Debian GNU/Linux / Raspbian
===========================

Debian GNU/Linux distribution and some derivatives such as Raspbian already
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

Instructions are at https://repo.saltstack.com/#debian.

.. note::
    Regular security support for Debian 7 ended on April 25th 2016. As a result,
    2016.3.1 and 2015.8.10 will be the last Salt releases for which Debian
    7 packages are created.

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
       apt-get install python-zmq python-systemd/jessie-backports python-tornado/jessie-backports salt-common/stretch

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

Now, go to the :ref:`Configuring Salt <configuring-salt>` page.
