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

.. note::

    In the event you do not see your distribution or version available please
    review the develop branch on GitHub as it main contain updates that are
    not present in the stable release:
    https://github.com/saltstack/salt-bootstrap/tree/develop


Debian and derivatives
~~~~~~~~~~~~~~~~~~~~~~

- Debian GNU/Linux 7/8
- Linux Mint Debian Edition 1 (based on Debian 8)
- Kali Linux 1.0 (based on Debian 7)


Red Hat family
~~~~~~~~~~~~~~

- Amazon Linux 2012.09/2013.03/2013.09/2014.03/2014.09
- CentOS 5/6/7
- Fedora 17/18/20/21/22
- Oracle Linux 5/6/7
- Red Hat Enterprise Linux 5/6/7
- Scientific Linux 5/6/7


SUSE family
~~~~~~~~~~~

- openSUSE 12/13
- openSUSE Leap 42
- openSUSE Tumbleweed 2015
- SUSE Linux Enterprise Server 11 SP1/11 SP2/11 SP3/12


Ubuntu and derivatives
~~~~~~~~~~~~~~~~~~~~~~

- Elementary OS 0.2 (based on Ubuntu 12.04)
- Linaro 12.04
- Linux Mint 13/14/16/17
- Trisquel GNU/Linux 6 (based on Ubuntu 12.04)
- Ubuntu 10.x/11.x/12.x/13.x/14.x/15.04


Other Linux distro
~~~~~~~~~~~~~~~~~~

- Arch Linux
- Gentoo


UNIX systems
~~~~~~~~~~~~

**BSD**:

- OpenBSD (``pip`` installation)
- FreeBSD 9/10/11

**SunOS**:

- SmartOS


Example Usage
-------------

If you're looking for the *one-liner* to install Salt, please scroll to the
bottom and use the instructions for `Installing via an Insecure One-Liner`_

.. note::

    In every two-step example, you would be well-served to examine the downloaded file and examine
    it to ensure that it does what you expect.


The Salt Bootstrap script has a wide variety of options that can be passed as
well as several ways of obtaining the bootstrap script itself.

.. note::

    These examples below show how to bootstrap Salt directly from GitHub or other Git repository.
    Run the script without any parameters to get latest stable Salt packages for your system from
    `SaltStack corporate repository`_. See first example in the `Install using wget`_ section.

.. _`SaltStack corporate repository`: https://repo.saltstack.com/


Install using curl
~~~~~~~~~~~~~~~~~~

Using ``curl`` to install latest development version from GitHub:

.. code:: console

    curl -o bootstrap_salt.sh -L https://bootstrap.saltstack.com
    sudo sh bootstrap_salt.sh git develop

If you want to install a specific release version (based on the Git tags):

.. code:: console

    curl -o bootstrap_salt.sh -L https://bootstrap.saltstack.com
    sudo sh bootstrap_salt.sh git v2015.8.8

To install a specific branch from a Git fork:

.. code:: console

    curl -o bootstrap_salt.sh -L https://bootstrap.saltstack.com
    sudo sh bootstrap_salt.sh -g https://github.com/myuser/salt.git git mybranch

If all you want is to install a ``salt-master`` using latest Git:

.. code:: console

    curl -o bootstrap_salt.sh -L https://bootstrap.saltstack.com
    sudo sh bootstrap_salt.sh -M -N git develop

If your host has Internet access only via HTTP proxy:

.. code:: console

    PROXY='http://user:password@myproxy.example.com:3128'
    curl -o bootstrap_salt.sh -L -x "$PROXY" https://bootstrap.saltstack.com
    sudo sh bootstrap_salt.sh -G -H "$PROXY" git


Install using wget
~~~~~~~~~~~~~~~~~~

Using ``wget`` to install your distribution's stable packages:

.. code:: console

    wget -O bootstrap_salt.sh https://bootstrap.saltstack.com
    sudo sh bootstrap_salt.sh

Downloading the script from develop branch:

.. code-block:: bash

    wget https://bootstrap.saltstack.com/develop
    sudo sh bootstrap_salt.sh

Installing a specific version from git using ``wget``:

.. code:: console

    wget -O bootstrap_salt.sh https://bootstrap.saltstack.com
    sudo sh bootstrap_salt.sh -P git v2015.8.8

.. note::

    On the above example we added `-P` which will allow PIP packages to be installed if required but
    it's not a necessary flag for Git based bootstraps.


Install using Python
~~~~~~~~~~~~~~~~~~~~

If you already have Python installed, ``python 2.6``, then it's as easy as:

.. code:: console

    python -m urllib "https://bootstrap.saltstack.com" > bootstrap_salt.sh
    sudo sh bootstrap_salt.sh git develop

All Python versions should support the following in-line code:

.. code:: console

    python -c 'import urllib; print urllib.urlopen("https://bootstrap.saltstack.com").read()' > bootstrap_salt.sh
    sudo sh bootstrap_salt.sh git develop


Install using fetch
~~~~~~~~~~~~~~~~~~~

On a FreeBSD base system you usually don't have either of the above binaries available. You **do**
have ``fetch`` available though:

.. code:: console

  fetch -o bootstrap_salt.sh https://bootstrap.saltstack.com
  sudo sh bootstrap_salt.sh

If you have any SSL issues install ``ca_root_nssp``:

.. code:: console

   pkg install ca_root_nssp

And either copy the certificates to the place where fetch can find them:

.. code:: console

   cp /usr/local/share/certs/ca-root-nss.crt /etc/ssl/cert.pem

Or link them to the right place:

.. code:: console

   ln -s /usr/local/share/certs/ca-root-nss.crt /etc/ssl/cert.pem


Installing via an Insecure One-Liner
------------------------------------

The following examples illustrate how to install Salt via a one-liner.

.. note::

    Warning! These methods do not involve a verification step and assume that
    the delivered file is trustworthy.


Any of the example above which use two-lines can be made to run in a single-line
configuration with minor modifications.

For example, using ``curl`` to install your distribution's stable packages:

.. code-block:: bash

    curl -L https://bootstrap.saltstack.com | sudo sh


Using ``wget`` to install your distribution's stable packages:

.. code-block:: bash

    wget -O - https://bootstrap.saltstack.com | sudo sh


Installing the latest develop branch of Salt:

.. code-block:: bash

    curl -L https://bootstrap.saltstack.com | sudo sh -s -- git develop


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
          ${BS_SALT_ETC_DIR}/minion.d/99-master-address.conf
      -i  Pass the salt-minion id. This will be stored under
          ${BS_SALT_ETC_DIR}/minion_id
      -L  Install the Apache Libcloud package if possible(required for salt-cloud)
      -p  Extra-package to install while installing salt dependencies. One package
          per -p flag. You're responsible for providing the proper package name.
      -d  Disable check_service functions. Setting this flag disables the
          'install_<distro>_check_services' checks. You can also do this by
          touching /tmp/disable_salt_checks on the target host. Defaults ${BS_FALSE}
      -H  Use the specified http proxy for the installation
      -Z  Enable external software source for newer ZeroMQ(Only available for RHEL/CentOS/Fedora/Ubuntu based distributions)
      -b  Assume that dependencies are already installed and software sources are set up.
          If git is selected, git tree is still checked out as dependency step.
