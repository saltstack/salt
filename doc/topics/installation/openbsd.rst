=======
OpenBSD
=======

Salt was added to the OpenBSD ports tree on Aug 10th 2013.
It has been tested on OpenBSD 5.5 onwards.

Salt is dependent on the following additional ports. These will be installed as
dependencies of the ``sysutils/salt`` port:

.. code-block:: text

   devel/py-futures
   devel/py-progressbar
   net/py-msgpack
   net/py-zmq
   security/py-crypto
   security/py-M2Crypto
   textproc/py-MarkupSafe
   textproc/py-yaml
   www/py-jinja2
   www/py-requests
   www/py-tornado

Installation
============

To install Salt from the OpenBSD pkg repo, use the command:

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

Now go to the :doc:`Configuring Salt</ref/configuration/index>` page.
