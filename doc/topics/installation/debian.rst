===================
Debian Installation
===================

Currently the latest packages for Debian are published in Martin F. Krafft's
personal debian.org repository. 

Configure Apt
-------------

Setup apt to install Salt from the repository and use Debian's stable (squeeze)
backports for dependencies:

.. code-block:: bash

    for i in salt-{common,master,minion,syndic,doc} sysvinit-utils; do
    echo "Package: $i"
    echo "Pin: release a=squeeze-backports"
    echo "Pin-Priority: 600"
    echo
    done > /etc/apt/preferences.d/local-salt-backport.pref 

Add repository
--------------

Add the repository to the list of sources:

.. code-block:: bash

    cat <<_eof > /etc/apt/sources.list.d/local-madduck-backports.list
        deb http://debian.madduck.net/repo squeeze-backports main
        deb-src http://debian.madduck.net/repo squeeze-backports main
    _eof 

Import the repository key.

.. code-block:: bash

    wget -q -O- "http://debian.madduck.net/repo/gpg/archive.key" | apt-key add -

.. note:: 
 
    You can optionally verify the key integrity with ``sha512sum`` using the 
    public key signature shown here. E.g::

        echo "8b1983fc2d2c55c83e2bbc15d93c3fc090c8e0e92c04ece555a6b6d8ff26de8b4fc2ccbe1bbd16a6357ff86b8b69fd261e90d61350e07a518d50fc9f5f0a1eb3 archive.key" | sha512sum -c 

Update the package database:

.. code-block:: bash

    apt-get update


Install packages
----------------

Install the Salt master, minion, or syndic from the repository with the apt-get 
command. These examples each install one daemon, but more than one package name 
may be given at a time:

.. code-block:: bash

    apt-get install salt-master 

.. code-block:: bash

    apt-get install salt-minion

.. code-block:: bash

    apt-get install salt-syndic

.. _Debian-config:

Post-installation tasks
=======================

Now go to the :doc:`Configuring Salt</topics/configuration>` page.


Packages from Source
====================

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

For more information how to use debian-backports see
http://backports-master.debian.org/Instructions/

