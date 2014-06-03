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
* `M2Crypto`_ - "Me Too Crypto" - Python OpenSSL wrapper
* `msgpack-python`_ - High-performance message interchange format
* `YAML`_ - Python YAML bindings
* `Jinja2`_ - parsing Salt States (configurable in the master settings)
* `MarkupSafe`_ - Implements a XML/HTML/XHTML Markup safe string for Python
* `apache-libcloud`_ - Python lib for interacting with many of the popular
  cloud service providers using a unified API

The upcoming feature release will include a new dependency:

* `Requests`_ - HTTP library

Optional Dependencies
---------------------

* `mako`_ - an optional parser for Salt States (configurable in the master
  settings)
* gcc - dynamic `Cython`_ module compiling

.. _`Python 2.6`: http://python.org/download/
.. _`ZeroMQ`: http://zeromq.org/
.. _`pyzmq`: https://github.com/zeromq/pyzmq
.. _`msgpack-python`:  https://pypi.python.org/pypi/msgpack-python/0.1.12
.. _`PyCrypto`: https://www.dlitz.net/software/pycrypto/
.. _`M2Crypto`: http://chandlerproject.org/Projects/MeTooCrypto
.. _`YAML`: http://pyyaml.org/
.. _`Jinja2`: http://jinja.pocoo.org/
.. _`MarkupSafe`: https://pypi.python.org/pypi/MarkupSafe
.. _`mako`: http://www.makotemplates.org/
.. _`Cython`: http://cython.org/
.. _`apache-libcloud`: http://libcloud.apache.org
.. _`Requests`: http://docs.python-requests.org/en/latest


Upgrading Salt
--------------

When upgrading Salt, the master(s) should always be upgraded first.  Backward
compatibility for minions running newer versions of salt than their masters is
not guaranteed.

Whenever possible, backward compatibility between new masters and old minions
will be preserved.  Generally, the only exception to this policy is in case of
a security vulnerability.
