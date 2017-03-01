======
Fedora
======

Beginning with version 0.9.4, Salt has been available in the primary Fedora
repositories and `EPEL`_. It is installable using ``yum`` or ``dnf``, depending
on your version of Fedora.

.. note::

    Released versions of Salt starting with ``2015.5.2`` through ``2016.3.2``
    do not have Fedora packages available though `EPEL`_. To install a version
    of Salt within this release array, please use SaltStack's `Bootstrap Script`_
    and use the git method of installing Salt using the version's associated
    release tag.

    Release ``2016.3.3`` and onward will have packaged versions available via
    `EPEL`_.

**WARNING**: Fedora 19 comes with systemd 204.  Systemd has known bugs fixed in
later revisions that prevent the salt-master from starting reliably or opening
the network connections that it needs to.  It's not likely that a salt-master
will start or run reliably on any distribution that uses systemd version 204 or
earlier.  Running salt-minions should be OK.

Installation
============

Salt can be installed using ``yum`` and is available in the standard Fedora
repositories.

Stable Release
--------------

Salt is packaged separately for the minion and the master. It is necessary only to
install the appropriate package for the role the machine will play. Typically, there
will be one master and multiple minions.

.. code-block:: bash

    yum install salt-master
    yum install salt-minion

Installing from ``updates-testing``
-----------------------------------

When a new Salt release is packaged, it is first admitted into the
``updates-testing`` repository, before being moved to the stable repo.

To install from ``updates-testing``, use the ``enablerepo`` argument for yum:

.. code-block:: bash

    yum --enablerepo=updates-testing install salt-master
    yum --enablerepo=updates-testing install salt-minion

Installation Using pip
======================

Since Salt is on `PyPI`_, it can be installed using pip, though most users
prefer to install using a package manager.

Installing from pip has a few additional requirements:

* Install the group 'Development Tools', ``dnf groupinstall 'Development Tools'``
* Install the 'zeromq-devel' package if it fails on linking against that
  afterwards as well.

A pip install does not make the init scripts or the /etc/salt directory, and you
will need to provide your own systemd service unit.

Installation from pip:

.. code-block:: bash

    pip install salt

.. warning::

    If installing from pip (or from source using ``setup.py install``), be
    advised that the ``yum-utils`` package is needed for Salt to manage
    packages. Also, if the Python dependencies are not already installed, then
    you will need additional libraries/tools installed to build some of them.
    More information on this can be found :ref:`here
    <installing-for-development>`.


Post-installation tasks
=======================

**Master**

To have the Master start automatically at boot time:

.. code-block:: bash

    systemctl enable salt-master.service

To start the Master:

.. code-block:: bash

    systemctl start salt-master.service

**Minion**

To have the Minion start automatically at boot time:

.. code-block:: bash

    systemctl enable salt-minion.service

To start the Minion:

.. code-block:: bash

    systemctl start salt-minion.service

Now go to the :ref:`Configuring Salt<configuring-salt>` page.

.. _`Bootstrap Script`: https://github.com/saltstack/salt-bootstrap
.. _`EPEL`: http://fedoraproject.org/wiki/EPEL
.. _`PyPI`: https://pypi.python.org/pypi/salt
