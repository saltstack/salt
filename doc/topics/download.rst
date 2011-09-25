=============
Download Salt
=============

Packages and dependencies for Salt can be downloaded here for specific
operating systems. Please follow and specific instructions for your system.

Salt From Source
----------------

The Salt source can be downloaded and installed directly from git:

.. code-block:: bash

    # git clone git://github.com/thatch45/salt.git

The latest source tarball can be downloaded as well:

|latest|

Salt should run on any Unix like platform so long as the dependencies are met.

Salt for Red Hat
----------------

Salt rpms have been prepared for Red Hat Enterprise Linux 6 and Fedora 15.
While Fedora 15 only requires the Salt rpm Red Hat Enterprise Linux 6 requires
that a newer version of ZeroMQ be installed than what is available in the EPEL
repositories.

Fedora rpms
```````````

Salt is currently being built for Fedora, the latest koji build pages can be
found here:

Fedora 14:

https://koji.fedoraproject.org/koji/taskinfo?taskID=3358221

Fedora 15:

https://koji.fedoraproject.org/koji/taskinfo?taskID=3358223

Fedora Rawhide:

https://koji.fedoraproject.org/koji/taskinfo?taskID=3358219


Red Hat Enterprise Linux 6 rpms
```````````````````````````````

Salt is being built for EPEL6, the latest builds can be found here:

https://koji.fedoraproject.org/koji/taskinfo?taskID=3358215

The ZeroMQ packages in EPEL6 have been tested with this package, but if you
still have issues, these backports may help

ZeroMQ backport:

:download:`zeromq-2.1.7-1.el6.x86_64.rpm`

PyZMQ bindings backport:

:download:`python-zmq-2.1.7-1.el6.src.rpm`

Package to set up EPEL repository (provided by the EPEL project):

http://download.fedoraproject.org/pub/epel/6/i386/epel-release-6-5.noarch.rpm

Red Hat Enterprise Linux 5 rpms
```````````````````````````````

Salt is being built for RHEL5, updates will be available soon!

Red Hat Enterprise Linux 5 requires more backports and the use of the
python 2.6 stack provided in the EPEL repository. All of the listed packages
need to be installed and the EPEL repository enabled to bring in the needed
dependencies:

Salt rpm:

:download:`salt-0.8.9-1.el5.noarch.rpm`

YAML bindings for python 2.6:

:download:`python26-PyYAML-3.08-4.el5.x86_64.rpm`

ZeroMQ backport:

:download:`zeromq-2.1.7-1.el5.x86_64.rpm`

PyZMQ bindings backport:

:download:`python26-zmq-2.1.7-1.el5.x86_64.rpm`

Salt for Arch Linux
-------------------

Salt can be easily installed on Arch Linux, install the package from the Arch
Linux AUR:

https://aur.archlinux.org/packages.php?ID=47512

Or install directly from git on Arch Linux:

https://aur.archlinux.org/packages.php?ID=47513
