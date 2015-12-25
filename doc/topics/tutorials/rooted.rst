====================================
running salt as normal user tutorial
====================================

.. include:: /_incl/requisite_incl.rst

Running Salt functions as non root user
=======================================

If you don't want to run salt cloud as root or even install it you can
configure it to have a virtual root in your working directory.

The salt system uses the ``salt.syspath`` module to find the variables

If you run the salt-build, it will generated in:

.. code-block:: bash

   ./build/lib.linux-x86_64-2.7/salt/_syspaths.py

To generate it, run the command:

.. code-block:: bash

    python setup.py build

Copy the generated module into your salt directory

.. code-block:: bash

    cp ./build/lib.linux-x86_64-2.7/salt/_syspaths.py salt/_syspaths.py

Edit it to include needed variables and your new paths

.. code-block:: python

   # you need to edit this
   ROOT_DIR = *your current dir* + '/salt/root'

   # you need to edit this
   INSTALL_DIR = *location of source code*

   CONFIG_DIR =  ROOT_DIR + '/etc/salt'
   CACHE_DIR = ROOT_DIR + '/var/cache/salt'
   SOCK_DIR = ROOT_DIR + '/var/run/salt'
   SRV_ROOT_DIR= ROOT_DIR + '/srv'
   BASE_FILE_ROOTS_DIR = ROOT_DIR + '/srv/salt'
   BASE_PILLAR_ROOTS_DIR = ROOT_DIR + '/srv/pillar'
   BASE_MASTER_ROOTS_DIR = ROOT_DIR + '/srv/salt-master'
   LOGS_DIR = ROOT_DIR + '/var/log/salt'
   PIDFILE_DIR = ROOT_DIR + '/var/run'
   CLOUD_DIR = INSTALL_DIR + '/cloud'
   BOOTSTRAP = CLOUD_DIR + '/deploy/bootstrap-salt.sh'


Create the directory structure

.. code-block:: bash

    mkdir -p root/etc/salt root/var/cache/run root/run/salt root/srv
    root/srv/salt root/srv/pillar root/srv/salt-master root/var/log/salt root/var/run


Populate the configuration files:

.. code-block:: bash

    cp -r conf/* root/etc/salt/

Edit your ``root/etc/salt/master`` configuration that is used by salt-cloud:

.. code-block:: yaml

    user: *your user name*

Run like this:

.. code-block:: bash

    PYTHONPATH=`pwd` scripts/salt-cloud
