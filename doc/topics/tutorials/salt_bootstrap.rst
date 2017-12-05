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
    review the develop branch on GitHub as it may contain updates that are
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
- Ubuntu 10.x/11.x/12.x/13.x/14.x/15.x/16.x


Other Linux distro
~~~~~~~~~~~~~~~~~~

- Arch Linux
- Gentoo


UNIX systems
~~~~~~~~~~~~

**BSD**:

- OpenBSD
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

.. code-block:: bash

    curl -o bootstrap-salt.sh -L https://bootstrap.saltstack.com
    sudo sh bootstrap-salt.sh git develop

If you want to install a specific release version (based on the Git tags):

.. code-block:: bash

    curl -o bootstrap-salt.sh -L https://bootstrap.saltstack.com
    sudo sh bootstrap-salt.sh git v2015.8.8

To install a specific branch from a Git fork:

.. code-block:: bash

    curl -o bootstrap-salt.sh -L https://bootstrap.saltstack.com
    sudo sh bootstrap-salt.sh -g https://github.com/myuser/salt.git git mybranch

If all you want is to install a ``salt-master`` using latest Git:

.. code-block:: bash

    curl -o bootstrap-salt.sh -L https://bootstrap.saltstack.com
    sudo sh bootstrap-salt.sh -M -N git develop

If your host has Internet access only via HTTP proxy:

.. code-block:: bash

    PROXY='http://user:password@myproxy.example.com:3128'
    curl -o bootstrap-salt.sh -L -x "$PROXY" https://bootstrap.saltstack.com
    sudo sh bootstrap-salt.sh -G -H "$PROXY" git


Install using wget
~~~~~~~~~~~~~~~~~~

Using ``wget`` to install your distribution's stable packages:

.. code-block:: bash

    wget -O bootstrap-salt.sh https://bootstrap.saltstack.com
    sudo sh bootstrap-salt.sh

Downloading the script from develop branch:

.. code-block:: bash

    wget -O bootstrap-salt.sh https://bootstrap.saltstack.com/develop
    sudo sh bootstrap-salt.sh

Installing a specific version from git using ``wget``:

.. code-block:: bash

    wget -O bootstrap-salt.sh https://bootstrap.saltstack.com
    sudo sh bootstrap-salt.sh -P git v2015.8.8

.. note::

    On the above example we added `-P` which will allow PIP packages to be installed if required but
    it's not a necessary flag for Git based bootstraps.


Install using Python
~~~~~~~~~~~~~~~~~~~~

If you already have Python installed, ``python 2.6``, then it's as easy as:

.. code-block:: bash

    python -m urllib "https://bootstrap.saltstack.com" > bootstrap-salt.sh
    sudo sh bootstrap-salt.sh git develop

All Python versions should support the following in-line code:

.. code-block:: bash

    python -c 'import urllib; print urllib.urlopen("https://bootstrap.saltstack.com").read()' > bootstrap-salt.sh
    sudo sh bootstrap-salt.sh git develop


Install using fetch
~~~~~~~~~~~~~~~~~~~

On a FreeBSD base system you usually don't have either of the above binaries available. You **do**
have ``fetch`` available though:

.. code-block:: bash

  fetch -o bootstrap-salt.sh https://bootstrap.saltstack.com
  sudo sh bootstrap-salt.sh

If you have any SSL issues install ``ca_root_nssp``:

.. code-block:: bash

   pkg install ca_root_nssp

And either copy the certificates to the place where fetch can find them:

.. code-block:: bash

   cp /usr/local/share/certs/ca-root-nss.crt /etc/ssl/cert.pem

Or link them to the right place:

.. code-block:: bash

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

      Installation types:
        - stable              Install latest stable release. This is the default
                              install type
        - stable [branch]     Install latest version on a branch. Only supported
                              for packages available at repo.saltstack.com
        - stable [version]    Install a specific version. Only supported for
                              packages available at repo.saltstack.com
        - daily               Ubuntu specific: configure SaltStack Daily PPA
        - testing             RHEL-family specific: configure EPEL testing repo
        - git                 Install from the head of the develop branch
        - git [ref]           Install from any git ref (such as a branch, tag, or
                              commit)

      Examples:
        - bootstrap-salt.sh
        - bootstrap-salt.sh stable
        - bootstrap-salt.sh stable 2017.7
        - bootstrap-salt.sh stable 2017.7.2
        - bootstrap-salt.sh daily
        - bootstrap-salt.sh testing
        - bootstrap-salt.sh git
        - bootstrap-salt.sh git 2017.7
        - bootstrap-salt.sh git v2017.7.2
        - bootstrap-salt.sh git 06f249901a2e2f1ed310d58ea3921a129f214358

      Options:
        -h  Display this message
        -v  Display script version
        -n  No colours
        -D  Show debug output
        -c  Temporary configuration directory
        -g  Salt Git repository URL. Default: https://github.com/saltstack/salt.git
        -w  Install packages from downstream package repository rather than
            upstream, saltstack package repository. This is currently only
            implemented for SUSE.
        -k  Temporary directory holding the minion keys which will pre-seed
            the master.
        -s  Sleep time used when waiting for daemons to start, restart and when
            checking for the services running. Default: 3
        -L  Also install salt-cloud and required python-libcloud package
        -M  Also install salt-master
        -S  Also install salt-syndic
        -N  Do not install salt-minion
        -X  Do not start daemons after installation
        -d  Disables checking if Salt services are enabled to start on system boot.
            You can also do this by touching /tmp/disable_salt_checks on the target
            host. Default: ${BS_FALSE}
        -P  Allow pip based installations. On some distributions the required salt
            packages or its dependencies are not available as a package for that
            distribution. Using this flag allows the script to use pip as a last
            resort method. NOTE: This only works for functions which actually
            implement pip based installations.
        -U  If set, fully upgrade the system prior to bootstrapping Salt
        -I  If set, allow insecure connections while downloading any files. For
            example, pass '--no-check-certificate' to 'wget' or '--insecure' to
            'curl'. On Debian and Ubuntu, using this option with -U allows to obtain
            GnuPG archive keys insecurely if distro has changed release signatures.
        -F  Allow copied files to overwrite existing (config, init.d, etc)
        -K  If set, keep the temporary files in the temporary directories specified
            with -c and -k
        -C  Only run the configuration function. Implies -F (forced overwrite).
            To overwrite Master or Syndic configs, -M or -S, respectively, must
            also be specified. Salt installation will be ommitted, but some of the
            dependencies could be installed to write configuration with -j or -J.
        -A  Pass the salt-master DNS name or IP. This will be stored under
            ${BS_SALT_ETC_DIR}/minion.d/99-master-address.conf
        -i  Pass the salt-minion id. This will be stored under
            ${BS_SALT_ETC_DIR}/minion_id
        -p  Extra-package to install while installing Salt dependencies. One package
            per -p flag. You're responsible for providing the proper package name.
        -H  Use the specified HTTP proxy for all download URLs (including https://).
            For example: http://myproxy.example.com:3128
        -Z  Enable additional package repository for newer ZeroMQ
            (only available for RHEL/CentOS/Fedora/Ubuntu based distributions)
        -b  Assume that dependencies are already installed and software sources are
            set up. If git is selected, git tree is still checked out as dependency
            step.
        -f  Force shallow cloning for git installations.
            This may result in an "n/a" in the version number.
        -l  Disable ssl checks. When passed, switches "https" calls to "http" where
            possible.
        -V  Install Salt into virtualenv
            (only available for Ubuntu based distributions)
        -a  Pip install all Python pkg dependencies for Salt. Requires -V to install
            all pip pkgs into the virtualenv.
            (Only available for Ubuntu based distributions)
        -r  Disable all repository configuration performed by this script. This
            option assumes all necessary repository configuration is already present
            on the system.
        -R  Specify a custom repository URL. Assumes the custom repository URL
            points to a repository that mirrors Salt packages located at
            repo.saltstack.com. The option passed with -R replaces the
            "repo.saltstack.com". If -R is passed, -r is also set. Currently only
            works on CentOS/RHEL and Debian based distributions.
        -J  Replace the Master config file with data passed in as a JSON string. If
            a Master config file is found, a reasonable effort will be made to save
            the file with a ".bak" extension. If used in conjunction with -C or -F,
            no ".bak" file will be created as either of those options will force
            a complete overwrite of the file.
        -j  Replace the Minion config file with data passed in as a JSON string. If
            a Minion config file is found, a reasonable effort will be made to save
            the file with a ".bak" extension. If used in conjunction with -C or -F,
            no ".bak" file will be created as either of those options will force
            a complete overwrite of the file.
        -q  Quiet salt installation from git (setup.py install -q)
        -x  Changes the python version used to install a git version of salt. Currently
            this is considered experimental and has only been tested on Centos 6. This
            only works for git installations.
        -y  Installs a different python version on host. Currently this has only been
            tested with Centos 6 and is considered experimental. This will install the
            ius repo on the box if disable repo is false. This must be used in conjunction
            with -x <pythonversion>.  For example:
                sh bootstrap.sh -P -y -x python2.7 git v2016.11.3
            The above will install python27 and install the git version of salt using the
            python2.7 executable. This only works for git and pip installations.
