.. _installation:

============
Installation
============

The Salt system setup is amazingly simple, as this is one of the central design
goals of Salt.

.. seealso::

    :doc:`Installing Salt for development </topics/hacking>` and contributing
    to the project.

Quick Install
-------------

Many popular distributions will be able to install the salt minion by executing
the bootstrap script:

.. code-block:: bash

    wget -O - http://bootstrap.saltstack.org | sudo sh

Run the following script to install just the Salt Master:

.. code-block:: bash

    curl -L http://bootstrap.saltstack.org | sudo sh -s -- -M -N

The script should also make it simple to install a salt master, if desired.

Currently the install script has been tested to work on:

* Ubuntu 10.x/11.x/12.x
* Debian 6.x
* CentOS 6.3
* Fedora
* Arch
* FreeBSD 9.0

See `Salt Bootstrap`_ for more information.

.. _`Salt Bootstrap`: https://github.com/saltstack/salt-bootstrap


Platform-specific installation instructions
-------------------------------------------

These guides go into detail how to install salt on a given platform.

.. toctree::
    :maxdepth: 1

    arch
    debian
    fedora
    freebsd
    gentoo
    osx
    rhel
    solaris
    ubuntu
    windows
    suse


Dependencies
------------

Salt should run on any Unix-like platform so long as the dependencies are met.

* `Python 2.6`_ >= 2.6 <3.0
* `ZeroMQ`_ >= 3.2.0
* `pyzmq`_ >= 2.2.0 - ZeroMQ Python bindings
* `PyCrypto`_ - The Python cryptography toolkit
* `msgpack-python`_ - High-performance message interchange format
* `YAML`_ - Python YAML bindings
* `Jinja2`_ - parsing Salt States (configurable in the master settings)

Optional Dependencies
---------------------

* `mako`_ - an optional parser for Salt States (configurable in the master
  settings)
* gcc - dynamic `Cython`_ module compiling

.. _`Python 2.6`: http://python.org/download/
.. _`ZeroMQ`: http://www.zeromq.org/
.. _`pyzmq`: https://github.com/zeromq/pyzmq
.. _`msgpack-python`:  http://pypi.python.org/pypi/msgpack-python/0.1.12
.. _`YAML`: http://pyyaml.org/
.. _`PyCrypto`: http://www.dlitz.net/software/pycrypto/
.. _`M2Crypto`: http://chandlerproject.org/Projects/MeTooCrypto
.. _`Cython`: http://cython.org/
.. _`Jinja2`: http://jinja.pocoo.org/
.. _`mako`: http://www.makotemplates.org/

