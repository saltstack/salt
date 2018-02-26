=======
FreeBSD
=======

Installation
============

Salt is available in binary package form from both the FreeBSD pkgng repository
or directly from SaltStack. The instructions below outline installation via
both methods:

FreeBSD repo
============

The FreeBSD pkgng repository is preconfigured on systems 10.x and above. No
configuration is needed to pull from these repositories.

.. code-block:: shell

    pkg install py27-salt

These packages are usually available within a few days of upstream release.

.. _freebsd-upstream:

SaltStack repo
==============

SaltStack also hosts internal binary builds of the Salt package, available from
https://repo.saltstack.com/freebsd/. To make use of this repository, add the
following file to your system:

**/usr/local/etc/pkg/repos/saltstack.conf:**

.. code-block:: json

    saltstack: {
      url: "https://repo.saltstack.com/freebsd/${ABI}/",
      enabled: yes
    }

You should now be able to install Salt from this new repository:

.. code-block:: shell

    pkg install py27-salt

These packages are usually available earlier than upstream FreeBSD. Also
available are release candidates and development releases. Use these pre-release
packages with caution.

Post-installation tasks
=======================

**Master**

Copy the sample configuration file:

.. code-block:: shell

   cp /usr/local/etc/salt/master.sample /usr/local/etc/salt/master

**rc.conf**

Activate the Salt Master in ``/etc/rc.conf``:

.. code-block:: shell

   sysrc salt_master_enable="YES"

**Start the Master**

Start the Salt Master as follows:

.. code-block:: shell

   service salt_master start

**Minion**

Copy the sample configuration file:

.. code-block:: shell

   cp /usr/local/etc/salt/minion.sample /usr/local/etc/salt/minion

**rc.conf**

Activate the Salt Minion in ``/etc/rc.conf``:

.. code-block:: shell

   sysrc salt_minion_enable="YES"

**Start the Minion**

Start the Salt Minion as follows:

.. code-block:: shell

   service salt_minion start

Now go to the :ref:`Configuring Salt<configuring-salt>` page.
