.. _windows-package-manager:
===========================
Windows Software Repository
===========================

.. note::
    Git repository management for the Windows Software Repository has changed
    in version 2015.8.0, and several master/minion config parameters have been
    renamed to make their naming more consistent with each other. Please see
    :ref:`below <2015-8-0-winrepo-changes>` for important details if upgrading
    from an earlier Salt release.

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
(``C:\salt\srv\salt\win\repo`` on standalone minions). This can be changed in
the master config file by setting the :conf_master:`winrepo_dir` option
(**NOTE:** this option was called ``win_repo`` in Salt versions prior to
2015.8.0). However, this path must reside somewhere inside the master's
:conf_master:`file_roots`. Each piece of software should have its own directory
which contains the installers and a package definition file. This package
definition file is a YAML file named ``init.sls``.

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

Add ``cache_dir: True`` when the installer requires multiple source files. The
directory containing the installer file will be recursively cached on the minion.
Only applies to salt: installer URLs.

.. code-block:: yaml

    sqlexpress:
      12.0.2000.8:
        installer: 'salt://win/repo/sqlexpress/setup.exe'
        full_name: Microsoft SQL Server 2014 Setup (English)
        reboot: False
        install_flags: '/ACTION=install /IACCEPTSQLSERVERLICENSETERMS /Q'
        cache_dir: True

Generate Repo Cache File
========================

Once the sls file has been created, generate the repository cache file with the
winrepo runner:

.. code-block:: bash

    salt-run winrepo.genrepo

Beginning with the 2015.8.0 Salt release the repository cache is compiled on
the Salt Minion. This allows for easy templating on the minion which allows for
pillar, grains and other things to be available during compilation time. From
2015.8.0 forward the above `salt-run winrepo.genrepo` is only required for
older minions. New minions should execute `salt \* pkg.refresh_db` to update
from the latest from the master's repo.

Then update the repository cache file on your minions, exactly how it's done
for the Linux package managers:

.. code-block:: bash

    salt winminion pkg.refresh_db


Install Windows Software
========================

Now you can query the available version of Firefox using the Salt pkg module.

.. code-block:: bash

    salt winminion pkg.available_version firefox

    {'firefox': {'15.0.1': 'Mozilla Firefox 15.0.1 (x86 en-US)',
                 '16.0.2': 'Mozilla Firefox 16.0.2 (x86 en-US)',
                 '17.0.1': 'Mozilla Firefox 17.0.1 (x86 en-US)'}}

As you can see, there are three versions of Firefox available for installation.
You can refer a software package by its ``name`` or its ``full_name`` surround
by single quotes.

.. code-block:: bash

    salt winminion pkg.install 'firefox'

The above line will install the latest version of Firefox.

.. code-block:: bash

    salt winminion pkg.install 'firefox' version=16.0.2

The above line will install version 16.0.2 of Firefox.

If a different version of the package is already installed it will be replaced
with the version in the winrepo (only if the package itself supports live
updating).

You can also specify the full name:

.. code-block:: bash

    salt winminion pkg.install 'Mozilla Firefox 17.0.1 (x86 en-US)'


Uninstall Windows Software
==========================

Uninstall software using the pkg module:

.. code-block:: bash

    salt winminion pkg.remove firefox
    salt winminion pkg.purge firefox

``pkg.purge`` just executes ``pkg.remove`` on Windows. At some point in the
future ``pkg.purge`` may direct the installer to remove all configs and
settings for software packages that support that option.

.. _standalone-winrepo:

Managing Windows Software on a Standalone Windows Minion
========================================================

The examples above for managing the winrepo using the :mod:`winrepo runner
<salt.runners.winrepo>` apply to the master, but some use cases call for
running a standalone (a.k.a. masterless) minion on a Windows server. For these
cases, the runner functions are not available, so an :mod:`execution module
<salt.modules.win_repo>` exists to provide the same functionality to standalone
minions. The functions are named the same as the ones in the runner, and are
used in the same way; the only difference is that ``salt-call`` is used instead
of ``salt-run``:

.. code-block:: bash

    salt-call winrepo.genrepo
    salt-call pkg.refresh_db

Package definition SLS files need to be in the correct location for
:py:func:`winrepo.genrepo <salt.modules.win_repo.genrepo>` to find them. This
location is governed by minion config parameters. With much of Salt's Windows
Repo code having been rewritten for version 2015.8.0, the parameter names will
differ depending on which version the minion is running. The following two
sections include information on additional configuration required when running
a standalone minion.

Minion Config Options for Releases Older Than 2015.8.0
======================================================

If connected to a master, the minion will by default look for the winrepo
cachefile (the file generated by the :py:func`winrepo.genrepo runner
<salt.runners.winrepo.genrepo>`) at ``salt://win/repo/winrepo.p``. If the
cachefile is in a different path on the salt fileserver, then
:conf_minion:`win_repo_cachefile` will need to be updated to reflect the proper
location.

.. note:: Additional Info for Standalone Minions

    Additional configuration needs to be added to the minion config:

    .. code-block:: yaml

        win_repo: 'C:\path\to\win\repo'

    This path still needs to be within the minion's :conf_minion:`file_roots`,
    just as when managing the Windows Repo on the master.

Minion Config Options for Releases 2015.8.0 and Newer
=====================================================

The :conf_minion:`winrepo_source_dir` config parameter (default:
``salt://win/repo``) controls where :py:func:`pkg.refresh_db
<salt.modules.win_pkg.refresh_db>` looks for the cachefile (default:
``winrepo.p``). This means that the default location for the winrepo cachefile
would be ``salt://win/repo/winrepo.p``. Both :conf_minion:`winrepo_source_dir`
and :conf_minion:`winrepo_cachefile` can be adjusted to match the actual
location of this file on the Salt fileserver.

.. note:: Additional Info for Standalone Minions

    The above still holds true regarding :conf_minion:`winrepo_source_dir`, the
    differences are that the minion's :conf_minion:`file_roots` is where that
    ``salt://`` URL will resolve, and the :mod:`winrepo
    <salt.modules.win_repo>` execution module must be used to generate this
    cachefile.

    If :conf_minion:`file_roots` has not been modified in the minion
    configuration, then no additional configuration needs to be added to the
    minion configuration. The :py:func:`winrepo.genrepo
    <salt.modules.win_repo.genrepo>` function from the :mod:`winrepo
    <salt.modules.win_repo>` execution module will by default look for the
    filename specified by :conf_minion:`winrepo_cachefile` within
    ``C:\salt\srv\salt\win\repo``. If the :conf_minion:`file_roots` parameter
    has been modified, then :conf_minion:`winrepo_dir` must be modified to fall
    within that path, at the proper relative path. For example, if the
    ``base`` environment in :conf_minion:`file_roots` points to ``D:\foo``, and
    :conf_minion:`winrepo_source_dir` is ``salt://win/repo``, then
    :conf_minion:`winrepo_dir` must be set to ``D:\foo\win\repo`` to ensure
    that :py:func:`winrepo.genrepo <salt.modules.win_repo.genrepo>` puts the
    cachefile into right location.

Maintaining Windows Repo Definitions in Git Repositories
========================================================

Windows software package definitions can also be hosted in one or more git
repositories. The default repository configured is hosted on GitHub.com by
SaltStack, Inc. It includes package definitions for various open source
software projects.

This repo points to the HTTP or ftp locations of the installer files. Anyone is
welcome to send a pull request to this repo to add new package definitions.
Browse the repo here: `https://github.com/saltstack/salt-winrepo.git
<https://github.com/saltstack/salt-winrepo.git>`_ .

Configure which git repositories the master can search for package definitions
by modifying or extending the :conf_master:`winrepo_remotes` option (**NOTE:**
this option was called ``win_gitrepos`` in Salt versions prior to 2015.8.0).

Use the :py:func:`winrepo.update_git_repos
<salt.runners.winrepo.update_git_repos>` runner to clone/update the configured
repos, then use :py:func:`winrepo.genrepo <salt.runners.winrepo.genrepo>`
runner to compile the repository cache. Finally, use :py:func:`pkg.refresh_db
<salt.modules.win_pkg.refresh_db>` on each minion to have them update their
copy of the repository cache. Command examples are as follows:

.. code-block:: bash

    salt-run winrepo.update_git_repos
    salt-run winrepo.genrepo
    salt winminion pkg.refresh_db

For standalone minions, the usage would be slightly different:

.. code-block:: bash

    salt-call winrepo.update_git_repos
    salt-call winrepo.genrepo
    salt-call pkg.refresh_db

.. _2015-8-0-winrepo-changes:

Changes in Version 2015.8.0
===========================

Config Parameters Renamed
-------------------------

Many of the winrepo configuration parameters have changed in version 2015.8.0
to make the naming more consistent. The old parameter names will still work,
but a warning will be logged indicating that the old name is deprecated. Below
are the parameters which have changed for version 2015.8.0:

Master Config
*************

======================== ================================
Old Name                 New Name
======================== ================================
win_repo                 :conf_master:`winrepo_dir`
win_repo_mastercachefile :conf_master:`winrepo_cachefile`
win_gitrepos             :conf_master:`winrepo_remotes`
======================== ================================

See :ref:`here <winrepo-master-config-opts>` for detailed information on all
master config options for the Windows Repo.

Minion Config
*************

======================== ================================
Old Name                 New Name
======================== ================================
win_repo                 :conf_minion:`winrepo_dir`
win_repo_cachefile       :conf_minion:`winrepo_cachefile`
win_gitrepos             :conf_minion:`winrepo_remotes`
======================== ================================

See :ref:`here <winrepo-minion-config-opts>` for detailed information on all
minion config options for the Windows Repo.

pygit2_/GitPython_ Support for Maintaining Git Repos
----------------------------------------------------

The :py:func:`winrepo.update_git_repos <salt.runners.winrepo.update_git_repos>`
runner (and the corresponding :py:func:`remote execution function
<salt.modules.win_repo.update_git_repos>` for standalone minions) now makes use
of the same underlying code used by the :ref:`Git Fileserver Backend
<tutorial-gitfs>` and :mod:`Git External Pillar <salt.pillar.git_pillar>` to
maintain and update its local clones of git repositories. If a compatible
version of either pygit2_ (0.20.3 and later) or GitPython_ (0.3.0 or later) is
installed, then Salt will use it instead of the old method (which invokes the
:py:func:`git.latest <salt.states.git.latest>` state).

.. note::
    If compatible versions of both pygit2_ and GitPython_ are installed, then
    Salt will prefer pygit2_, to override this behavior use the
    :conf_master:`winrepo_provider` configuration parameter:

    .. code-block:: yaml

        winrepo_provider: gitpython

    The :mod:`winrepo execution module <salt.modules.win_repo>` (discussed
    above in the :ref:`Managing Windows Software on a Standalone Windows Minion
    <standalone-winrepo>` section) does not yet officially support the new
    pygit2_/GitPython_ functionality, but if either pygit2_ or GitPython_ is
    installed into Salt's bundled Python then it *should* work. However, it
    should be considered experimental at this time.

.. _pygit2: https://github.com/libgit2/pygit2
.. _GitPython: https://github.com/gitpython-developers/GitPython

To minimize potential issues, it is a good idea to remove any winrepo git
repositories that were checked out by the old (pre-2015.8.0) winrepo code when
upgrading the master to 2015.8.0 or later, and run
:py:func:`winrepo.update_git_repos <salt.runners.winrepo.update_git_repos>` to
clone them anew after the master is started.

Additional added features include the ability to access authenticated git
repositories (**NOTE:** pygit2_ only), and to set per-remote config settings.
An example of this would be the following:

.. code-block:: yaml

    winrepo_remotes:
      - https://github.com/saltstack/salt-winrepo.git
      - git@github.com:myuser/myrepo.git:
        - pubkey: /path/to/key.pub
        - privkey: /path/to/key
        - passphrase: myaw3s0m3pa$$phr4$3
      - https://github.com/myuser/privaterepo.git:
        - user: mygithubuser
        - password: CorrectHorseBatteryStaple

.. note::
    Per-remote configuration settings work in the same fashion as they do in
    gitfs, with global parameters being overridden by their per-remote
    counterparts (for instance, setting :conf_master:`winrepo_passphrase` would
    set a global passphrase for winrepo that would apply to all SSH-based
    remotes, unless overridden by a ``passphrase`` per-remote parameter).

    See :ref:`here <gitfs-per-remote-config>` for more a more in-depth
    explanation of how per-remote configuration works in gitfs, the same
    principles apply to winrepo.

There are a couple other changes in how Salt manages git repos using
pygit2_/GitPython_. First of all, a ``clean`` argument has been added to the
:py:func:`winrepo.update_git_repos <salt.runners.winrepo.update_git_repos>`
runner, which (if set to ``True``) will tell the runner to dispose of
directories under the :conf_master:`winrepo_dir` which are not explicitly
configured. This prevents the need to manually remove these directories when a
repo is removed from the config file. To clean these old directories, just pass
``clean=True``, like so:

.. code-block:: bash

    salt-run winrepo.update_git_repos clean=True

However, if a mix of git and non-git Windows Repo definition files are being
used, then this should *not* be used, as it will remove the directories
containing non-git definitions.

The other major change is that collisions between repo names are now detected,
and the winrepo runner will not proceed if any are detected. Consider the
following configuration:

.. code-block:: yaml

    winrepo_remotes:
      - https://foo.com/bar/baz.git
      - https://mydomain.tld/baz.git
      - https://github.com/foobar/baz

The :py:func:`winrepo.update_git_repos <salt.runners.winrepo.update_git_repos>`
runner will refuse to update repos here, as all three of these repos would be
checked out to the same directory. To work around this, a per-remote parameter
called ``name`` can be used to resolve these conflicts:

.. code-block:: yaml

    winrepo_remotes:
      - https://foo.com/bar/baz.git
      - https://mydomain.tld/baz.git:
        - name: baz_junior
      - https://github.com/foobar/baz:
        - name: baz_the_third

.. _wiki: http://wpkg.org/Category:Silent_Installers

Troubleshooting
===============

Incorrect name/version
----------------------

If the package seems to install properly, but salt reports a failure then it is
likely you have a version or ``full_name`` mismatch.

Check the exact ``full_name`` and version used by the package. Use
``pkg.list_pkgs`` to check that the names and version exactly match what is
installed.

Changes to sls files not being picked up
----------------------------------------

Ensure you have (re)generated the repository cache file and then
updated the repository cache on the relevant minions:

.. code-block:: bash

    salt-run winrepo.genrepo
    salt winminion pkg.refresh_db


Packages management under Windows 2003
----------------------------------------

On windows server 2003, you need to install optional windows component
"wmi windows installer provider" to have full list of installed packages.
If you don't have this, salt-minion can't report some installed software.
