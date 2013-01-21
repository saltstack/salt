======
Debian
======

Installation
============

Salt is currently available in in the Debian package tree:

http://packages.debian.org/source/salt

If you're running a Debian release more recent than Wheezy use:

.. code-block:: bash

    apt-get install salt-master
    apt-get install salt-minion

As of this writing salt is only available in Debian unstable.

Squeeze
=======

To build your own salt Debian packages on squeeze use:

.. code-block:: bash

    cat <<EOF | sudo tee /etc/apt/sources.list.d/backports.list
    deb http://backports.debian.org/debian-backports squeeze-backports main
    EOF
    apt-get update
    apt-get install build-essential fakeroot
    apt-get install python-argparse python-zmq
    apt-get -t squeeze-backports install debhelper python-sphinx

After installing the necessary dependencies build the packages with:

.. code-block:: bash

    git clone https://github.com/saltstack/salt.git
    cd salt
    fakeroot debian/rules binary

You will need to install the salt-common package along with the salt-minion or
salt-master packages. For example:

.. code-block:: bash

   dpkg -i salt-common_<version>.deb salt-minion<version>.deb
   apt-get -f install

The last command pulls in the required dependencies for your salt packages.

Wheezy
======

Backports for Wheezy should be available shortly after it's release.

For more information how to use debian-backports see
http://backports-master.debian.org/Instructions/

Post-installation tasks
=======================

Now go to the :doc:`Configuring Salt</topics/configuration>` page.

