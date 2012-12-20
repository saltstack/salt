======
Debian
======

Installation
============
Salt is currently available in in the Debian package tree:

http://packages.debian.org/source/salt

To install Salt on Wheezy or later use:

.. code-block:: bash

    apt-get install salt-master
    apt-get install salt-minion

Squeeze
=======

Salt is available for squeeze in the Debian backports repository, and may be
installed as follows:

.. code-block:: bash

    cat <<EOF | sudo tee /etc/apt/sources.list.d/backports.list
    deb http://backports.debian.org/debian-backports squeeze-backports main
    EOF
    apt-get update
    apt-get -t squeeze-backports install salt-master
    apt-get -t squeeze-backports install salt-minion

For more information how to use debian-backports see
http://backports-master.debian.org/Instructions/

Post-installation tasks
=======================

Now go to the :doc:`Configuring Salt</topics/configuration>` page.

