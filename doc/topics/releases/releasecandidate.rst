===========================================
Installing/Testing a Salt Release Candidate
===========================================

It's time for a new feature release of Salt!  Follow the instructions below to
install the latest release candidate of Salt, and try :doc:`all the shiny new
features </topics/releases/2015.8.0>`!  Be sure to report any bugs you find on
`Github <http://www.github.com/saltstack/salt>`_

Installing Using Bootstrap
==========================

The easiest way to install a release candidate of Salt is using
`Salt Bootstrap`_:

.. code-block:: bash

    curl -o install_salt.sh -L https://bootstrap.saltstack.com
    sudo sh install_salt.sh git v2015.8.0rc2

If you want to also install a master using `Salt Bootstrap`_, use the ``-M``
flag:

.. code-block:: bash

    curl -o install_salt.sh -L https://bootstrap.saltstack.com
    sudo sh install_salt.sh -M git v2015.8.0rc2

If you want to install only a master and not a minion using `Salt Bootstrap`_,
use the ``-M`` and ``-N`` flags:

.. code-block:: bash

    curl -o install_salt.sh -L https://bootstrap.saltstack.com
    sudo sh install_salt.sh -M -N git v2015.8.0rc2


Installation from Source Tarball
================================

Installing from the source tarball on PyPI is also fairly straightforward.
First, install all the dependencies for Salt as documented :ref:`in the
installation docs <_installation>`.  Then install salt using the following:

.. code-block:: bash

    curl -O https://pypi.python.org/packages/source/s/salt/salt-2015.8.0rc2.tar.gz
    tar -xzvf salt-2015.8.0rc2.tar.gz
    cd salt-2015.8.0rc2
    sudo python setup.py install


.. _`saltstack/salt`: https://github.com/saltstack/salt
.. _`Salt Bootstrap`: https://github.com/saltstack/salt-bootstrap
