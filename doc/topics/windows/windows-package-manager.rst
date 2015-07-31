===========================
Windows Software Repository
===========================

The Salt Windows Software Repository provides a package manager and software
repository similar to what is provided by yum and apt on Linux.

It permits the installation of software using the installers on remote
windows machines. In many senses, the operation is similar to that of
the other package managers salt is aware of:

- the ``pkg.installed`` and similar states work on Windows.
- the ``pkg.install`` and similar module functions work on Windows.
- each windows machine needs to have ``pkg.refresh_db`` executed
  against it to pick up the latest version of the package database.

High level differences to yum and apt are:

- The repository metadata (sls files) is hosted through either salt or
  git.
- Packages can be downloaded from within the salt repository, a git
  repository or from http(s) or ftp urls.
- No dependencies are managed. Dependencies between packages needs to
  be managed manually.


Operation
=========

The install state/module function of the windows package manager works
roughly as follows:

1. Execute ``pkg.list_pkgs`` and store the result
2. Check if any action needs to be taken. (i.e. compare required package
   and version against ``pkg.list_pkgs`` results)
3. If so, run the installer command.
4. Execute ``pkg.list_pkgs`` and compare to the result stored from
   before installation.
5. Success/Failure/Changes will be reported based on the differences
   between the original and final ``pkg.list_pkgs`` results.

If there are any problems in using the package manager it is likely to
be due to the data in your sls files not matching the difference
between the pre and post ``pkg.list_pkgs`` results.



Usage
=====

By default, the Windows software repository is found at ``/srv/salt/win/repo``
This can be changed in the master config file (default location is
``/etc/salt/master``) by modifying the  ``win_repo`` variable.  Each piece of
software should have its own directory which contains the installers and a
package definition file. This package definition file is a YAML file named
``init.sls``.

The package definition file should look similar to this example for Firefox:
``/srv/salt/win/repo/firefox/init.sls``

.. code-block:: yaml

    Firefox:
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
so that the status can be verified when running highstate.
Note: It is still possible to successfully install packages using ``pkg.install``
even if they don't match which can make this hard to troubleshoot.

.. code-block:: bash

    salt 'test-2008' pkg.list_pkgs
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
        install_flags: '/qn /norestart'
        msiexec: True
        uninstaller: '{23170F69-40C1-2702-0920-000001000000}'
        uninstall_flags: '/qn /norestart'

Alternatively the ``uninstaller`` can also simply repeat the URL of the msi file. 

.. code-block:: yaml

    7zip:
      9.20.00.0:
        installer: salt://win/repo/7zip/7z920-x64.msi
        full_name: 7-Zip 9.20 (x64 edition)
        reboot: False
        install_flags: '/qn /norestart'
        msiexec: True
        uninstaller: salt://win/repo/7zip/7z920-x64.msi
        uninstall_flags: '/qn /norestart'


Generate Repo Cache File
========================

Once the sls file has been created, generate the repository cache file with the winrepo runner:

.. code-block:: bash

    salt-run winrepo.genrepo

Then update the repository cache file on your minions, exactly how it's done for the Linux package managers:

.. code-block:: bash

    salt '*' pkg.refresh_db


Install Windows Software
========================

Now you can query the available version of Firefox using the Salt pkg module.

.. code-block:: bash

    salt '*' pkg.available_version Firefox

    {'Firefox': {'15.0.1': 'Mozilla Firefox 15.0.1 (x86 en-US)',
                     '16.0.2': 'Mozilla Firefox 16.0.2 (x86 en-US)',
                     '17.0.1': 'Mozilla Firefox 17.0.1 (x86 en-US)'}}

As you can see, there are three versions of Firefox available for installation.
You can refer a software package by its ``name`` or its ``full_name`` surround
by single quotes.

.. code-block:: bash

    salt '*' pkg.install 'Firefox'

The above line will install the latest version of Firefox.

.. code-block:: bash

    salt '*' pkg.install 'Firefox' version=16.0.2

The above line will install version 16.0.2 of Firefox.

If a different version of the package is already installed it will
be replaced with the version in winrepo (only if the package itself supports
live updating).

You can also specify the full name:

.. code-block:: bash

    salt '*' pkg.install 'Mozilla Firefox 17.0.1 (x86 en-US)'


Uninstall Windows Software
==========================

Uninstall software using the pkg module:

.. code-block:: bash

    salt '*' pkg.remove 'Firefox'

    salt '*' pkg.purge 'Firefox'

``pkg.purge`` just executes ``pkg.remove`` on Windows. At some point in the
future ``pkg.purge`` may direct the installer to remove all configs and
settings for software packages that support that option.



Standalone Minion Salt Windows Repo Module
==========================================

In order to facilitate managing a Salt Windows software repo with Salt on a
Standalone Minion on Windows, a new module named winrepo has been added to
Salt. winrepo matches what is available in the salt runner and allows you to
manage the Windows software repo contents. Example: ``salt '*'
winrepo.genrepo``

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

    salt-run winrepo.update_git_repos
    salt-run winrepo.genrepo
    salt '*' pkg.refresh_db

.. _wiki: http://wpkg.org/Category:Silent_Installers



Troubleshooting
===============


Incorrect name/version
----------------------

If the package seems to install properly, but salt reports a failure
then it is likely you have a version or ``full_name`` mismatch.

Check the exact ``full_name`` and version used by the package. Use
``pkg.list_pkgs`` to check that the names and version exactly match
what is installed.

Changes to sls files not being picked up
----------------------------------------

Ensure you have (re)generated the repository cache file and then
updated the repository cache on the relevant minions:

.. code-block:: bash

    salt-run winrepo.genrepo
    salt 'MINION' pkg.refresh_db


Packages management under Windows 2003
----------------------------------------

On windows server 2003, you need to install optional windows component
"wmi windows installer provider" to have full list of installed packages.
If you don't have this, salt-minion can't report some installed software.
