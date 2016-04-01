.. _installation:

============
Installation
============
.. seealso::

    :doc:`Installing Salt for development </topics/development/hacking>` and
    contributing to the project.

Quick Install
-------------

On most distributions, you can set up a **Salt Minion** with the
`Salt Bootstrap`_.

.. _`Salt Bootstrap`: https://github.com/saltstack/salt-bootstrap


Platform-specific Installation Instructions
-------------------------------------------

These guides go into detail how to install Salt on a given platform.

.. toctree::
    :maxdepth: 1

    arch
    debian
    fedora
    freebsd
    gentoo
    openbsd
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
* `msgpack-python`_ - High-performance message interchange format
* `YAML`_ - Python YAML bindings
* `Jinja2`_ - parsing Salt States (configurable in the master settings)
* `MarkupSafe`_ - Implements a XML/HTML/XHTML Markup safe string for Python
* `apache-libcloud`_ - Python lib for interacting with many of the popular
  cloud service providers using a unified API
* `Requests`_ - HTTP library

Depending on the chosen Salt transport, `ZeroMQ`_ or `RAET`_, dependencies
vary:

* ZeroMQ:

  * `ZeroMQ`_ >= 3.2.0
  * `pyzmq`_ >= 2.2.0 - ZeroMQ Python bindings
  * `PyCrypto`_ - The Python cryptography toolkit

* RAET:

  * `libnacl`_ - Python bindings to `libsodium`_
  * `ioflo`_ - The flo programming interface raet and salt-raet is built on
  * `RAET`_ - The worlds most awesome UDP protocol

Salt defaults to the `ZeroMQ`_ transport, and the choice can be made at install
time, for example:

.. code-block:: bash

    python setup.py --salt-transport=raet install

This way, only the required dependencies are pulled by the setup script if need
be.

If installing using pip, the ``--salt-transport`` install option can be
provided like:

.. code-block:: bash

  pip install --install-option="--salt-transport=raet" salt

.. note::
    Salt does not bundle dependencies that are typically distributed as part of
    the base OS. If you have unmet dependencies and are using a custom or
    minimal installation, you might need to install some additional packages
    from your OS vendor.

Optional Dependencies
---------------------

* `mako`_ - an optional parser for Salt States (configurable in the master
  settings)
* gcc - dynamic `Cython`_ module compiling

.. _`Python 2.6`: http://python.org/download/
.. _`ZeroMQ`: http://zeromq.org/
.. _`pyzmq`: https://github.com/zeromq/pyzmq
.. _`msgpack-python`:  https://pypi.python.org/pypi/msgpack-python/
.. _`PyCrypto`: https://www.dlitz.net/software/pycrypto/
.. _`YAML`: http://pyyaml.org/
.. _`Jinja2`: http://jinja.pocoo.org/
.. _`MarkupSafe`: https://pypi.python.org/pypi/MarkupSafe
.. _`mako`: http://www.makotemplates.org/
.. _`Cython`: http://cython.org/
.. _`apache-libcloud`: http://libcloud.apache.org
.. _`Requests`: http://docs.python-requests.org/en/latest
.. _`libnacl`: https://github.com/saltstack/libnacl
.. _`ioflo`: https://github.com/ioflo/ioflo
.. _`RAET`: https://github.com/saltstack/raet
.. _`libsodium`: https://github.com/jedisct1/libsodium


Upgrading Salt
--------------

When upgrading Salt, the master(s) should always be upgraded first.  Backward
compatibility for minions running newer versions of salt than their masters is
not guaranteed.

Whenever possible, backward compatibility between new masters and old minions
will be preserved.  Generally, the only exception to this policy is in case of
a security vulnerability.
