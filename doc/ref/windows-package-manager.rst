===========================
Windows Software Repository
===========================

The Salt Windows Software Repository provides a package manager and software
repository similar to what is provided by yum and apt on Linux.

By default, the Windows software repository is found at ``/srv/salt/win/repo``
This can be changed in the master config file (default location is ``/etc/salt/master``)
by modifying the  ``win_repo`` variable.
Each piece of software should have its own directory which contains the
installers and a package definition file. This package definition file is a
YAML file named ``init.sls``.

The package definition file should look similar to this example for Firefox:
``/srv/salt/win/repo/firefox/init.sls``

.. code-block:: yaml

    firefox:
      17.0.1: 
        installer: 'salt://win/repo/firefox/English/Firefox Setup 17.0.1.exe'
        full_name: Mozilla Firefox 17.0.1 (x86 en-US) 
        locale: en_US
        reboot: False
        install_flags: ' -ms'
        uninstaller: '%ProgramFiles(x86)%/Mozilla Firefox/uninstall/helper.exe'
        uninstall_flags: ' /S' 
      16.0.2: 
        installer: 'salt://win/repo/firefox/English/Firefox Setup 16.0.2.exe'
        full_name: Mozilla Firefox 16.0.2 (x86 en-US) 
        locale: en_US
        reboot: False
        install_flags: ' -ms'
        uninstaller: '%ProgramFiles(x86)%/Mozilla Firefox/uninstall/helper.exe'
        uninstall_flags: ' /S' 
      15.0.1: 
        installer: 'salt://win/repo/firefox/English/Firefox Setup 15.0.1.exe'
        full_name: Mozilla Firefox 15.0.1 (x86 en-US) 
        locale: en_US
        reboot: False
        install_flags: ' -ms'
        uninstaller: '%ProgramFiles(x86)%/Mozilla Firefox/uninstall/helper.exe'
        uninstall_flags: ' /S'        

More examples can be found here: https://github.com/saltstack/salt-winrepo

The version number and ``full_name`` need to match the output from ``pkg.list_pkgs``
so that the status can be verfied when running highstate.
Note: It is still possible to succesfully install packages using ``pkg.install``
even if they don't match which can make this hard to troubleshoot.

.. code-block:: bash

    $ salt 'test-2008' pkg.list_pkgs
    test-2008
        ----------
        7-Zip 9.20 (x64 edition):
            9.20.00.0
        Microsoft .NET Framework 4 Client Profile:
            4.0.30319,4.0.30319
        Microsoft .NET Framework 4 Extended:
            4.0.30319,4.0.30319
        Microsoft Visual C++ 2008 Redistributable - x64 9.0.21022:
            9.0.21022
        Mozilla Firefox 17.0.1 (x86 en-US):
            17.0.1
        Mozilla Maintenance Service:
            17.0.1
        NSClient++ (x64):
            0.3.8.76
        Notepad++:
            6.4.2
        Salt Minion 0.16.0:
            0.16.0

If any of these preinstalled packages already exist in winrepo the full_name
will be automatically renamed to their package name during the next update
(running highstate or installing another package).

.. code-block:: bash

    test-2008:
        ----------
        7zip:
            9.20.00.0
        Microsoft .NET Framework 4 Client Profile:
            4.0.30319,4.0.30319
        Microsoft .NET Framework 4 Extended:
            4.0.30319,4.0.30319
        Microsoft Visual C++ 2008 Redistributable - x64 9.0.21022:
            9.0.21022
        Mozilla Maintenance Service:
            17.0.1
        Notepad++:
            6.4.2
        Salt Minion 0.16.0:
            0.16.0
        firefox:
            17.0.1
        nsclient:
            0.3.9.328

Add ``msiexec: True`` if using an MSI installer requiring the use of ``msiexec
/i`` to install and ``msiexec /x`` to uninstall.
``/srv/salt/win/repo/7zip/init.sls``

The ``install_flags`` and ``uninstall_flags`` are flags passed to the software
installer to cause it to perform a silent install. These can often be found by
adding ``/?`` or ``/h`` when running the installer from the command line. A
great resource for finding these silent install flags can be found on the WPKG
project's wiki_:

.. code-block:: yaml

    7zip:
      9.20.00.0:
        installer: salt://win/repo/7zip/7z920-x64.msi
        full_name: 7-Zip 9.20 (x64 edition)
        reboot: False
        install_flags: ' /q '  
        msiexec: True
        uninstaller: salt://win/repo/7zip/7z920-x64.msi
        uninstall_flags: ' /qn'
 
 

Generate Repo Cache File
========================

Once the sls file has been created, generate the repository cache file with the winrepo runner:

.. code-block:: bash

    $ salt-run winrepo.genrepo

Then update the repository cache file on your minions, exactly how it's done for the Linux package managers:

.. code-block:: bash

    $ salt '*' pkg.refresh_db


Install Windows Software
========================

Now you can query the available version of Firefox using the Salt pkg module.

.. code-block:: bash

    $ salt \* pkg.available_version firefox

    {'davewindows': {'15.0.1': 'Mozilla Firefox 15.0.1 (x86 en-US)',
                     '16.0.2': 'Mozilla Firefox 16.0.2 (x86 en-US)',
                     '17.0.1': 'Mozilla Firefox 17.0.1 (x86 en-US)'}}

As you can see, there are three versions of Firefox available for installation.

.. code-block:: bash

    $ salt \* pkg.install firefox

The above line will install the latest version of Firefox.

.. code-block:: bash

    $ salt \* pkg.install firefox version=16.0.2

The above line will install version 16.0.2 of Firefox.

If a different version of the package is already installed it will
be replaced with the version in winrepo (only if the package itself supports
live updating)


Uninstall Windows Software
==========================

Uninstall software using the pkg module:

.. code-block:: bash

    $ salt \* pkg.remove firefox

    $ salt \* pkg.purge firefox

``pkg.purge`` just executes ``pkg.remove`` on Windows. At some point in the
future ``pkg.purge`` may direct the installer to remove all configs and
settings for software packages that support that option.


Git Hosted Repo
===============

Windows software package definitions can also be hosted in one or more git
repositories. The default repo is one hosted on Github.com by SaltStack,Inc., which
includes package definitions for open source software. This repo points to the
HTTP or ftp locations of the installer files. Anyone is welcome to send a pull
request to this repo to add new package definitions. Browse the repo
here: `https://github.com/saltstack/salt-winrepo
<https://github.com/saltstack/salt-winrepo>`_ . 

Configure which git repos the master can search for package definitions by
modifying or extending the ``win_gitrepos`` configuration option list in the
master config.

Checkout each git repo in ``win_gitrepos``, compile your package repository
cache and then refresh each minion's package cache:

.. code-block:: bash

    $ salt-run winrepo.update_git_repos
    $ salt-run winrepo.genrepo
    $ salt \* pkg.refresh_db


.. _wiki: http://wpkg.org/Category:Silent_Installers
