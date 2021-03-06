=======
OpenBSD
=======

Salt was added to the OpenBSD ports tree on Aug 10th 2013.
It has been tested on OpenBSD 5.5 onwards.

Salt is dependent on the following additional ports. These will be installed as
dependencies of the ``sysutils/salt`` port:

.. code-block:: text

   devel/py3-progressbar
   net/py3-msgpack
   net/py3-zmq
   security/py3-Cryptodome
   security/py3-M2Crypto
   sysutils/py3-distro
   textproc/py3-MarkupSafe
   textproc/py3-yaml
   www/py3-jinja2
   www/py3-requests

Installation
============

To install Salt from the OpenBSD package repo, use the command:

.. code-block:: bash

    pkg_add salt

Post-installation tasks
=======================

**Master**

To have the Master start automatically at boot time:

.. code-block:: bash

    rcctl enable salt_master

To start the Master:

.. code-block:: bash

    rcctl start salt_master

**Minion**

To have the Minion start automatically at boot time:

.. code-block:: bash

    rcctl enable salt_minion

To start the Minion:

.. code-block:: bash

    rcctl start salt_minion

Now go to the :ref:`Configuring Salt<configuring-salt>` page.
