============
Installation
============

The Salt system setup is amazingly simple, as this is one of the central design
goals of Salt.

Dependencies
------------

Salt should run on any Unix-like platform so long as the dependencies are met.

* `Python 2.6`_ >= 2.6 <3.0
* `ZeroMQ`_ >= 2.1.9
* `pyzmq`_ >= 2.1.9 - ZeroMQ Python bindings
* `PyCrypto`_ - The Python cryptography toolkit
* `msgpack-python`_ - High-performance message interchange format
* `YAML`_ - Python YAML bindings

Optional Dependencies
---------------------

* `Jinja2`_ - parsing Salt States (configurable in the master settings)
* gcc - dynamic `Cython`_ module compiling

.. _`Python 2.6`: http://python.org/download/
.. _`ZeroMQ`: http://www.zeromq.org/
.. _`pyzmq`: https://github.com/zeromq/pyzmq
.. _`msgpack-python`:  http://pypi.python.org/pypi/msgpack-python/0.1.12
.. _`YAML`: http://pyyaml.org/
.. _`PyCrypto`: http://www.dlitz.net/software/pycrypto/
.. _`Cython`: http://cython.org/
.. _`Jinja2`: http://jinja.pocoo.org/

Platform-specific installation instructions
-------------------------------------------

.. toctree::
    :maxdepth: 1

    arch
    debian
    ubuntu
    fedora
    freebsd
    gentoo
    windows
