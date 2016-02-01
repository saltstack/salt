.. _salt-bootstrap:

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
- Debian 6.x/7.x/8(git installations only)
- Fedora 17/18
- FreeBSD 9.1/9.2/10
- Gentoo
- Linaro
- Linux Mint 13/14
- OpenSUSE 12.x
- Oracle Linux 5/5
- Red Hat 5/6
- Red Hat Enterprise 5/6
- Scientific Linux 5/6
- SmartOS
- SuSE 11 SP1/11 SP2
- Ubuntu 10.x/11.x/12.x/13.04/13.10
- Elementary OS 0.2


.. note::

    In the event you do not see your distribution or version available please
    review the develop branch on GitHub as it main contain updates that are
    not present in the stable release:
    https://github.com/saltstack/salt-bootstrap/tree/develop



Example Usage
~~~~~~~~~~~~~

If you're looking for the *one-liner* to install salt, please scroll to the
bottom and use the instructions for `Installing via an Insecure One-Liner`_

.. note::
    In every two-step example, you would be well-served to examine the downloaded file and examine
    it to ensure that it does what you expect.


Using ``curl`` to install latest git:

.. code-block:: bash

  curl -L https://bootstrap.saltstack.com -o install_salt.sh
  sudo sh install_salt.sh git develop


Using ``wget`` to install your distribution's stable packages:

.. code-block:: bash

  wget -O install_salt.sh https://bootstrap.saltstack.com
  sudo sh install_salt.sh


Install a specific version from git using ``wget``:

.. code-block:: bash

  wget -O install_salt.sh https://bootstrap.saltstack.com
  sudo sh install_salt.sh -P git v0.16.4

If you already have python installed, ``python 2.6``, then it's as easy as:

.. code-block:: bash

  python -m urllib "https://bootstrap.saltstack.com" > install_salt.sh
  sudo sh install_salt.sh git develop


All python versions should support the following one liner:

.. code-block:: bash

  python -c 'import urllib; print urllib.urlopen("https://bootstrap.saltstack.com").read()' > install_salt.sh
  sudo sh install_salt.sh git develop


On a FreeBSD base system you usually don't have either of the above binaries available. You **do**
have ``fetch`` available though:

.. code-block:: bash

  fetch -o install_salt.sh https://bootstrap.saltstack.com
  sudo sh install_salt.sh


If all you want is to install a ``salt-master`` using latest git:

.. code-block:: bash

  curl -o install_salt.sh -L https://bootstrap.saltstack.com
  sudo sh install_salt.sh -M -N git develop

If you want to install a specific release version (based on the git tags):

.. code-block:: bash

  curl -o install_salt.sh -L https://bootstrap.saltstack.com
  sudo sh install_salt.sh git v0.16.4

To install a specific branch from a git fork:

.. code-block:: bash

  curl -o install_salt.sh -L https://bootstrap.saltstack.com
  sudo sh install_salt.sh -g https://github.com/myuser/salt.git git mybranch


Installing via an Insecure One-Liner
------------------------------------

The following examples illustrate how to install Salt via a one-liner.

.. note::

    Warning! These methods do not involve a verification step and assume that
    the delivered file is trustworthy.


Examples
~~~~~~~~

Installing the latest develop branch of Salt:

.. code-block:: bash

  curl -L https://bootstrap.saltstack.com | sudo sh -s -- git develop

Any of the example above which use two-lines can be made to run in a single-line
configuration with minor modifications.


Example Usage
-------------

The Salt Bootstrap script has a wide variety of options that can be passed as
well as several ways of obtaining the bootstrap script itself.

For example, using ``curl`` to install your distribution's stable packages:

.. code-block:: bash

    curl -L https://bootstrap.saltstack.com | sudo sh


Using ``wget`` to install your distribution's stable packages:

.. code-block:: bash

    wget -O - https://bootstrap.saltstack.com | sudo sh


Installing the latest version available from git with ``curl``:

.. code-block:: bash

    curl -L https://bootstrap.saltstack.com | sudo sh -s -- git develop


Install a specific version from git using ``wget``:

.. code-block:: bash

    wget -O - https://bootstrap.saltstack.com | sh -s -- -P git v0.16.4


If you already have python installed, ``python 2.6``, then it's as easy as:

.. code-block:: bash

    python -m urllib "https://bootstrap.saltstack.com" | sudo sh -s -- git develop


All python versions should support the following one liner:

.. code-block:: bash

    python -c 'import urllib; print urllib.urlopen("https://bootstrap.saltstack.com").read()' | \
    sudo  sh -s -- git develop


On a FreeBSD base system you usually don't have either of the above binaries
available. You **do** have ``fetch`` available though:

.. code-block:: bash

    fetch -o - https://bootstrap.saltstack.com | sudo sh


If all you want is to install a ``salt-master`` using latest git:

.. code-block:: bash

    curl -L https://bootstrap.saltstack.com | sudo sh -s -- -M -N git develop


If you want to install a specific release version (based on the git tags):

.. code-block:: bash

    curl -L https://bootstrap.saltstack.com | sudo sh -s -- git v0.16.4


Downloading the develop branch (from here standard command line options may be
passed):

.. code-block:: bash

    wget https://bootstrap.saltstack.com/develop

Command Line Options
--------------------

Here's a summary of the command line options:

.. code-block:: bash

    $ sh bootstrap-salt.sh -h

      Usage :  bootstrap-salt.sh [options] <install-type> <install-type-args>

      Installation types:
        - stable (default)
        - stable [version] (ubuntu specific)
        - daily  (ubuntu specific)
        - testing (redhat specific)
        - git

      Examples:
        - bootstrap-salt.sh
        - bootstrap-salt.sh stable
        - bootstrap-salt.sh stable 2014.7
        - bootstrap-salt.sh daily
        - bootstrap-salt.sh testing
        - bootstrap-salt.sh git
        - bootstrap-salt.sh git develop
        - bootstrap-salt.sh git v0.17.0
        - bootstrap-salt.sh git 8c3fadf15ec183e5ce8c63739850d543617e4357

      Options:
      -h  Display this message
      -v  Display script version
      -n  No colours.
      -D  Show debug output.
      -c  Temporary configuration directory
      -g  Salt repository URL. (default: git://github.com/saltstack/salt.git)
      -G  Instead of cloning from git://github.com/saltstack/salt.git, clone from https://github.com/saltstack/salt.git (Usually necessary on systems which have the regular git protocol port blocked, where https usually is not)
      -k  Temporary directory holding the minion keys which will pre-seed
          the master.
      -s  Sleep time used when waiting for daemons to start, restart and when checking
          for the services running. Default: 3
      -M  Also install salt-master
      -S  Also install salt-syndic
      -N  Do not install salt-minion
      -X  Do not start daemons after installation
      -C  Only run the configuration function. This option automatically
          bypasses any installation.
      -P  Allow pip based installations. On some distributions the required salt
          packages or its dependencies are not available as a package for that
          distribution. Using this flag allows the script to use pip as a last
          resort method. NOTE: This only works for functions which actually
          implement pip based installations.
      -F  Allow copied files to overwrite existing(config, init.d, etc)
      -U  If set, fully upgrade the system prior to bootstrapping salt
      -K  If set, keep the temporary files in the temporary directories specified
          with -c and -k.
      -I  If set, allow insecure connections while downloading any files. For
          example, pass '--no-check-certificate' to 'wget' or '--insecure' to 'curl'
      -A  Pass the salt-master DNS name or IP. This will be stored under
          ${_SALT_ETC_DIR}/minion.d/99-master-address.conf
      -i  Pass the salt-minion id. This will be stored under
          ${_SALT_ETC_DIR}/minion_id
      -L  Install the Apache Libcloud package if possible(required for salt-cloud)
      -p  Extra-package to install while installing salt dependencies. One package
          per -p flag. You're responsible for providing the proper package name.
      -d  Disable check_service functions. Setting this flag disables the
          'install_<distro>_check_services' checks. You can also do this by
          touching /tmp/disable_salt_checks on the target host. Defaults ${BS_FALSE}
      -H  Use the specified http proxy for the installation
      -Z  Enable external software source for newer ZeroMQ(Only available for RHEL/CentOS/Fedora/Ubuntu based distributions)
