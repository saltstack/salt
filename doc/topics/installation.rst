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

Fedora
------

Salt is currently being built for Fedora. The latest koji build pages can be
found here:

* `Fedora 14 <https://koji.fedoraproject.org/koji/taskinfo?taskID=3358221>`_
* `Fedora 15 <https://koji.fedoraproject.org/koji/taskinfo?taskID=3358223>`_
* `Fedora Rawhide <https://koji.fedoraproject.org/koji/taskinfo?taskID=3358219>`_

Red Hat Enterprise Linux 6
--------------------------

Salt is being built for EPEL6. `Browse the latest builds.
<https://koji.fedoraproject.org/koji/taskinfo?taskID=3358215>`_

The ZeroMQ packages in EPEL6 have been tested with this package, but if you
still have issues these backports may help:

* :download:`ZeroMQ backport <zeromq-2.1.7-1.el6.x86_64.rpm>`
* :download:`pyzmq bindings backport <python-zmq-2.1.7-1.el6.src.rpm>`
* `Package to set up EPEL repository
  <http://download.fedoraproject.org/pub/epel/6/i386/epel-release-6-5.noarch.rpm>`_
  (provided by the EPEL project)
  
Red Hat Enterprise Linux 5
--------------------------

Salt is being built for RHEL5, updates will be available soon!

Red Hat Enterprise Linux 5 requires more backports and the use of the Python
2.6 stack provided in the EPEL repository. All of the listed packages need to
be installed and the EPEL repository enabled to bring in the needed
dependencies:

* :download:`Salt rpm <salt-0.8.9-1.el5.noarch.rpm>`
* :download:`YAML bindings for Python 2.6 <python26-PyYAML-3.08-4.el5.x86_64.rpm>`
* :download:`ZeroMQ backport <zeromq-2.1.7-1.el5.x86_64.rpm>`
* :download:`pyzmq bindings backport <python26-zmq-2.1.7-1.el5.x86_64.rpm>`

Arch Linux
==========

Salt can be easily installed from the Arch Linux AUR in one of two flavors:

* `Install a Salt release <https://aur.archlinux.org/packages.php?ID=47512>`_
* `Install the latest Salt from Git <https://aur.archlinux.org/packages.php?ID=47513>`_

Debian / Ubuntu
===============

Ubuntu
------

A PPA is available until we can get packages into apt::

    aptitude -y install python-software-properties
    add-apt-repository ppa:saltstack/salt
    aptitude update
    aptitude install salt

.. admonition:: Installing ZeroMQ on Ubuntu Lucid (10.04 LTS)

    The ZeroMQ package is available starting with Maverick but there are `PPA
    packages available for Lucid`_ for both ZeroMQ and pyzmq. You will need to
    also enable the following PPAs before running the commands above::

        add-apt-repository ppa:chris-lea/libpgm
        add-apt-repository ppa:chris-lea/zeromq

.. _`PPA packages available for Lucid`: https://launchpad.net/~chris-lea/+archive/zeromq

Debian
------

`A deb package is currently in testing`__. Until that is accepted you can
install Salt via :command:`easy_install` or :command:`pip`::

    pip install salt

.. __: http://mentors.debian.net/package/salt

.. admonition:: Installing ZeroMQ on Squeeze (Debian 6)

    ZeroMQ packages are available in squeeze-backports.

    1.  Add the following line to your :file:`/etc/apt/sources.list`::

            deb http://backports.debian.org/debian-backports squeeze-backports main

    2.  Run::

            aptitude update
            aptitude install libzmq1 python-zmq

Installing from source
======================

1.  Download the latest source tarball from the GitHub downloads directory for
    the Salt project: |latest|

2.  Untar the tarball and run the :file:`setup.py` as root:

.. parsed-literal::

    tar xvf salt-|version|.tar.gz
    cd salt-|version|
    python2 setup.py install
