.. _installation:

============
Installation
============
This section contains instructions to install Salt. If you are setting up your
environment for the first time, you should install a Salt master on
a dedicated management server or VM, and then install a Salt minion on each
system that you want to manage using Salt. For now you don't need to worry
about your :ref:`architecture <architecture-overview>`, you can easily add
components and modify your configuration later without needing to reinstall
anything.

The general installation process is as follows:

1. Install a Salt master using the instructions for your platform or by running
   the Salt bootstrap script. If you use the bootstrap script, be sure to
   include the ``-M`` option to install the Salt master.

2. Make sure that your Salt minions can :ref:`find the Salt master
   <master-dns>`.

3. Install the Salt minion on each system that you want to manage.

4. Accept the Salt :ref:`minion keys <using-salt-key>` after the Salt minion
   connects.

After this, you should be able to run a simple command and receive returns from
all connected Salt minions.

.. code-block:: bash

    salt '*' test.ping

Quick Install
-------------
On most distributions, you can set up a **Salt Minion** with the
:ref:`Salt bootstrap <salt-bootstrap>`.

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

Initial Configuration
---------------------

.. toctree::
    :maxdepth: 1

    ../../ref/configuration/index


Additional Installation Guides
------------------------------

.. toctree::
    :maxdepth: 1

    ../tutorials/salt_bootstrap
    ../tutorials/firewall
    ../tutorials/preseed_key
    ../tutorials/walkthrough_macosx
    ../tutorials/rooted
    ../tutorials/standalone_minion
    ../tutorials/quickstart

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
* `Tornado`_ - Web framework and asynchronous networking library
* `futures`_ - Backport of the concurrent.futures package from Python 3.2

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
.. _`Tornado`: http://www.tornadoweb.org/en/stable/
.. _`libnacl`: https://github.com/saltstack/libnacl
.. _`ioflo`: https://github.com/ioflo/ioflo
.. _`RAET`: https://github.com/saltstack/raet
.. _`libsodium`: https://github.com/jedisct1/libsodium
.. _`futures`: https://github.com/agronholm/pythonfutures


Upgrading Salt
--------------

When upgrading Salt, the master(s) should always be upgraded first.  Backward
compatibility for minions running newer versions of salt than their masters is
not guaranteed.

Whenever possible, backward compatibility between new masters and old minions
will be preserved.  Generally, the only exception to this policy is in case of
a security vulnerability.

.. seealso::

    :ref:`Installing Salt for development <installing-for-development>` and
    contributing to the project.

Building Packages using Salt Pack
---------------------------------

Salt-pack is an open-source package builder for most commonly used Linux
platforms, for example: Redhat/CentOS and Debian/Ubuntu families, utilizing
SaltStack states and execution modules to build Salt and a specified set of
dependencies, from which a platform specific repository can be built.

https://github.com/saltstack/salt-pack

