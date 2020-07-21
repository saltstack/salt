.. _installation-debian:

===========================
Debian GNU/Linux / Raspbian
===========================

Debian GNU/Linux distribution and some derivatives such as Raspbian already
have included Salt packages to their repositories. However, current stable
Debian release contains old outdated Salt releases. It is
recommended to use SaltStack repository for Debian as described
:ref:`below <installation-debian-repo>`.

Installation from official Debian and Raspbian repositories is described
:ref:`here <installation-debian-raspbian>`.

.. _installation-debian-repo:

Installation from the Official SaltStack Repository
===================================================

Packages for Debian 10 (Buster) and Debian 9 (Stretch) are available in the
Official SaltStack repository.

Instructions are at https://repo.saltstack.com/#debian.

.. note::
    Archived builds from unsupported branches:
    
    - `Archive 1 <https://archive.repo.saltstack.com/py3/debian/>`__
    - `Archive 2 <https://archive.repo.saltstack.com/debian/dists/>`__

    If looking to use archives, the same directions from the `Debian install
    directions <https://repo.saltstack.com/#debian>`__ can be used by replacing
    the URL paths with the appropriate archive location. The
    repository configuration endpoint also needs to be adjusted to point to the
    archives. Here is an example ``sed`` command:

    .. code-block:: bash

        # Salt repo configurations are found in the /etc/apt/sources.list.d/saltstack.list directory
        sed -i 's/repo.saltstack.com/archive.repo.saltstack.com/g' /etc/apt/sources.list.d/saltstack.list


.. warning::
    Regular security support for Debian 8 ended on June 30th 2018. As a result,
    3000.3 and 2019.2.5 will be the last Salt releases for which Debian 8
    packages are created. Debian 8 also reached LTS EOL on June 30 2020.

    Regular security support for Debian 7 ended on April 25th 2016. As a result,
    2016.3.1 and 2015.8.10 will be the last Salt releases for which Debian
    7 packages are created. Debian 7 also reached LTS EOL on May 31 2018.

.. _installation-debian-raspbian:

Installation from the Debian / Raspbian Official Repository
===========================================================

The Debian distributions contain mostly old Salt packages
built by the Debian Salt Team. You can install Salt
components directly from Debian but it is recommended to
use the instructions above for the packages from the official
Salt repository.

On Jessie there is an option to install Salt minion from Stretch with
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

#. Install Salt minion package from Latest Debian Release:

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
