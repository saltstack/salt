==============
Salt Bootstrap
==============

The Salt Bootstrap script allows for a user to install the Salt Minion or
Master on a variety of system distributions and versions. This shell script
known as ``bootstrap-salt.sh`` runs through a series of checks to determine
the operating system type and version. It then installs the Salt binaries
using the appropriate methods. The Salt Bootstrap script installs the
minimum number of packages required to run Salt. This means that in the event
you run the bootstrap to install via package, Git will not be installed.
Installing the minimum number of packages helps ensure the script stays as
lightweight as possible, assuming the user will install any other required
packages after the Salt binaries are present on the system. The script source
is available on GitHub: https://github.com/saltstack/salt-bootstrap

Supported Operating Systems
---------------------------
- Amazon Linux 2012.09
- Arch
- CentOS 5/6
- Debian 6.x/7.x
- Fedora 17/18
- FreeBSD 9.1
- Gentoo
- Linaro
- Linux Mint 13/14
- OpenSUSE 12.x
- Red Hat 5/6
- Red Hat Enterprise 5/6
- SmartOS
- SuSE 11 SP1/11 SP2
- Ubuntu 10.x/11.x/12.x/13.04

.. note::

    In the event you do not see your distribution or version available please
    review the develop branch on Github as it main contain updates that are
    not present in the stable release: 
    https://github.com/saltstack/salt-bootstrap/tree/develop

Example Usage
-------------

The Salt Bootstrap script has a wide variety of options that can be passed as
well as several ways of obtaining the bootstrap script itself.

For example, using ``curl`` to install latest git:

.. code-block:: bash

    curl -L http://bootstrap.saltstack.org | sudo sh -s -- git develop


If you have certificate issues using ``curl``, try the following:

.. code-block:: bash 

    curl --insecure -L http://bootstrap.saltstack.org | sudo sh -s -- git develop


Using ``wget`` to install your distribution's stable packages:

.. code-block:: bash

    wget -O - http://bootstrap.saltstack.org | sudo sh


If you have certificate issues using ``wget`` try the following:

.. code-block:: bash

    wget --no-check-certificate -O - http://bootstrap.saltstack.org | sudo sh


Install a specific version from git using ``wget``:

.. code-block:: bash

    wget -O - http://bootstrap.saltstack.org | sh -s -- -P git v0.16.4


If you already have python installed, ``python 2.6``, then it's as easy as:

.. code-block:: bash

    python -m urllib "http://bootstrap.saltstack.org" | sudo sh -s -- git develop


All python versions should support the following one liner:

.. code-block:: bash

    python -c 'import urllib; print urllib.urlopen("http://bootstrap.saltstack.org").read()' | \
    sudo  sh -s -- git develop


On a FreeBSD base system you usually don't have either of the above binaries available. You **do** 
have ``fetch`` available though:

.. code-block:: bash

    fetch -o - http://bootstrap.saltstack.org | sudo sh


If all you want is to install a ``salt-master`` using latest git:

.. code-block:: bash

    curl -L http://bootstrap.saltstack.org | sudo sh -s -- -M -N git develop


If you want to install a specific release version (based on the git tags):

.. code-block:: bash

    curl -L http://bootstrap.saltstack.org | sudo sh -s -- git v0.16.4


Downloading the develop branch (from here standard command line options may be
passed):

.. code-block:: bash

    wget https://raw.github.com/saltstack/salt-bootstrap/develop/bootstrap-salt.sh

Command Line Options
--------------------

**-h** Display the help message and command line options.

**-v** Display script version.

**-n** No colours.

**-D** Show debug output.

**-c** Temporary configuration directory.

**-k** Temporary directory holding the minion keys which will pre-seed the master.

**-M** Also install salt-master.

**-S** Also install salt-syndic.

**-N** Do not install salt-minion.

**-X** Do not start daemons after installation.

**-C** Only run the configuration function. This option automatically bypasses
any installation.

**-P** Allow pip based installations. On some distributions the required salt
packages or its dependencies are not available as a package for that
distribution. Using this flag allows the script to use pip as a last
resort method. 

.. note::

    This works for functions which actually implement
    pip based installations.

**-F** Allow copied files to overwrite existing(config, init.d, etc).

**-U** If set, fully upgrade the system prior to bootstrapping salt.

**-K** If set, keep the temporary files in the temporary directories specified
with -c and -k.
