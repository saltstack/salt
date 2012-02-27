======
Gentoo
======

Salt can be easily installed on Gentoo::

    emerge pyyaml m2crypto pycrypto jinja pyzmq

Then download and install from source:

1.  Download the latest source tarball from the GitHub downloads directory for
    the Salt project:

2.  Untar the tarball and run the ``setup.py`` as root::

        tar xvf salt-<version>.tar.gz
        cd salt-<version>
        python2 setup.py install
