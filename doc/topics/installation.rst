===============
Installing Salt
===============

The Salt system setup is amazingly simple, as this is one of the central design
goals of Salt. Setting up Salt only requires that the Salt :term:`master` be
running and the Salt :term:`minions <minion>` point to the master.

.. admonition:: Salt dependencies

    Salt should run on any Unix-like platform so long as the dependencies are
    met.

    * `Python 2.6`_
    * `ZeroMQ`_ >= 2.1.9
    * `pyzmq`_ >= 2.1.9 — ZeroMQ Python bindings
    * `M2Crypto`_ — Python OpenSSL wrapper
    * `PyCrypto`_ — The Python cryptography toolkit
    * `YAML`_ — Python YAML bindings

    Optional Dependencies:

    * `Jinja2`_ — parsing Salt States (other renderers can be used via the
      :conf_master:`renderer` setting).
    * gcc — dynamic `Cython`_ module compiling

.. _`Python 2.6`: http://python.org/download/
.. _`ZeroMQ`: http://www.zeromq.org/
.. _`pyzmq`: https://github.com/zeromq/pyzmq
.. _`M2Crypto`: http://chandlerproject.org/Projects/MeTooCrypto
.. _`YAML`: http://pyyaml.org/
.. _`PyCrypto`: http://www.dlitz.net/software/pycrypto/
.. _`Cython`: http://cython.org/
.. _`Jinja2`: http://jinja.pocoo.org/

.. contents:: Instructions by operating system
    :depth: 1
    :local:

Red Hat
=======

We are working to get Salt packages into EPEL. In the meantime you can install
Salt via our Fedora People repository. This should work for Red Hat Enterprise
Linux 5 & 6, CentOS 5 & 6, as well as Fedora 14, 15, & 16.

1.  If you are running el5 or el6 `install the EPEL repository`__

2.  Enable our repository on FedoraPeople::

        wget -O /etc/yum.repos.d/epel-salt.repo \
            http://repos.fedorapeople.org/repos/herlo/salt/epel-salt.repo

3.  Install Salt::

        yum install salt-master salt-minion

.. __: http://fedoraproject.org/wiki/EPEL#How_can_I_use_these_extra_packages.3F

Arch Linux
==========

Salt can be easily installed from the Arch Linux AUR in one of two flavors:

* `Install a Salt release <https://aur.archlinux.org/packages.php?ID=47512>`_
* `Install the latest Salt from Git <https://aur.archlinux.org/packages.php?ID=47513>`_

Debian / Ubuntu
===============

Ubuntu
------

We are working to get Salt into apt. In the meantime we have a PPA available
for Lucid::

    aptitude -y install python-software-properties
    add-apt-repository ppa:chris-lea/libpgm
    add-apt-repository ppa:chris-lea/zeromq
    add-apt-repository ppa:saltstack/salt
    aptitude update
    aptitude install salt

Debian
------

`A deb package is currently in testing`__ for inclusion in apt. Until that is
accepted you can install Salt by downloading the latest ``.deb`` in the
`downloads section on GitHub`__ and installing that manually:

.. parsed-literal::

    dpkg -i salt-|version|.deb

.. __: http://mentors.debian.net/package/salt
.. __: https://github.com/saltstack/salt/downloads

.. admonition:: Installing ZeroMQ on Squeeze (Debian 6)

    There is a `python-zmq`__ package available in Debian "wheezy (testing)".
    If you don't have that repo enabled the best way to install Salt and pyzmq
    is by using :command:`pip` (or :command:`easy_install`)::

        pip install pyzmq salt

.. __: http://packages.debian.org/search?keywords=python-zmq

Gentoo
======

Salt can be easily installed on Gentoo::

    emerge pyyaml m2crypto pycrypto jinja pyzmq

Then download and install from source:

1.  Download the latest source tarball from the GitHub downloads directory for
    the Salt project: |latest|

2.  Untar the tarball and run the :file:`setup.py` as root:

.. parsed-literal::

    tar xvf salt-|version|.tar.gz
    cd salt-|version|
    python2 setup.py install

FreeBSD
=======

Salt is available in the FreeBSD ports tree::

    cd /usr/ports/sysutils/salt && make install clean

.. seealso:: :doc:`freebsd installation guide </topics/tutorials/freebsd>`

Installing from source
======================

1.  Download the latest source tarball from the GitHub downloads directory for
    the Salt project: |latest|

2.  Untar the tarball and run the :file:`setup.py` as root:

.. parsed-literal::

    tar xvf salt-|version|.tar.gz
    cd salt-|version|
    python2 setup.py install
