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

https://github.com/downloads/thatch45/salt/salt-0.8.9.tar.gz

Salt should run on any Unix like platform so long as the dependencies are met.

Salt for Red Hat
----------------

Salt rpms have been prepared for Red Hat Enterprise Linux 6 and Fedora 15.
While Fedora 15 only requires the Salt rpm Red Hat Enterprise Linux 6 requires
that a newer version of ZeroMQ be installed than what is available in the EPEL
repositories.

Fedora rpms
```````````

Salt noarch rpm for Fedora 15:

https://github.com/downloads/thatch45/salt/salt-0.8.9-1.fc15.noarch.rpm

Red Hat Enterprise Linux 6 rpms
```````````````````````````````

The EPEL repository is required for Salt as well as updated ZeroMQ packages.

The Salt rpm can be downloaded here:

https://github.com/downloads/thatch45/salt/salt-0.8.9-1.el6.noarch.rpm

ZeroMQ backport:

https://github.com/downloads/thatch45/salt/zeromq-2.1.7-1.el6.x86_64.rpm

PyZMQ Binding backport:

https://github.com/downloads/thatch45/salt/python-zmq-2.1.7-1.el6.src.rpm

Package to set up EPEL repository (provided by the EPEL project):

http://download.fedoraproject.org/pub/epel/6/i386/epel-release-6-5.noarch.rpm

Salt for Arch Linux
```````````````````

Salt can be easily installed on Arch Linux, install the package from the Arch
Linux AUR:

https://aur.archlinux.org/packages.php?ID=47512

Or install directly from git on Arch Linux:

https://aur.archlinux.org/packages.php?ID=47513
