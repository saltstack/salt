=======
Solaris
=======

Salt is known to work on Solaris but community packages are unmaintained.

It is possible to install Salt on Solaris by using `setuptools`.

For example, to install the develop version of salt:

.. code-block:: bash

    git clone https://github.com/saltstack/salt
    cd salt
    sudo python setup.py install --force


.. note::

    SaltStack does offer commercial support for Solaris which includes packages.
    Packages can be found on the
    `Downloads page of the Enterprise Installation Guide
    <https://enterprise.saltstack.com/docs/downloads.html#aix-solaris-minions>`_
    and are downloadable with a *SaltStack Enterprise* account.