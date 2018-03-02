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

    SaltStack does offer commerical support for Solaris which includes packages.
