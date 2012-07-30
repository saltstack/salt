======
Debian
======

Installation
============
Salt is currently available in in the Debian package tree:

http://packages.debian.org/source/salt

To install Salt on Wheezy or later use:

.. code-block:: bash

    sudo apt-get install salt-master
    sudo apt-get install salt-minion


Squeeze
=======

Salt is available for squeeze in the Debian backports repository. For more
information how to use debian-backports see
http://backports-master.debian.org/Instructions/

.. code-block:: bash

    cat <<EOF | sudo tee /etc/apt/sources.list.d/backports.list
    deb http://backports.debian.org/debian-backports squeeze-backports main
    EOF
    sudo apt-get update
    sudo apt-get -t squeeze-backports install salt-master
    sudo apt-get -t squeeze-backports install salt-minion


Configuration
=============

For more configuration have a look at the Ubuntu section :ref:`ubuntu-config`
