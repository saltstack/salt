.. _windows-package-manager:

===========================
Windows Software Repository
===========================

.. note::
    In 2015.8.0 and later, the Windows Software Repository cache is compiled on
    the Salt Minion, which enables pillar, grains and other things to be
    available during compilation time. To support this new functionality,
    a next-generation (ng) package repository was created. See See the
    :ref:`Changes in Version 2015.8.0 <2015-8-0-winrepo-changes>` for details.

The SaltStack Windows Software Repository provides a package manager and software
repository similar to what is provided by yum and apt on Linux. This repository
enables the installation of software using the installers on remote Windows
systems.

In many senses, the operation is similar to that of
the other package managers salt is aware of:

- the ``pkg.installed`` and similar states work on Windows.
- the ``pkg.install`` and similar module functions work on Windows.

High level differences to yum and apt are:

- The repository metadata (SLS files) is hosted through either salt or
  git.
- Packages can be downloaded from within the salt repository, a git
  repository or from http(s) or ftp urls.
- No dependencies are managed. Dependencies between packages needs to
  be managed manually.

Requirements:

- GitPython 0.3 or later, or pygit2 0.20.3 with libgit 0.20.0 or later installed
  on your Salt master. The Windows package definitions are downloaded
  and updated using Git.


Configuration
=============

Populate the Repository
-----------------------

The SLS files used to install Windows packages are not distributed by default with
Salt. Run the following command to initialize the repository on your Salt
master:

.. code-block:: bash

    salt-run winrepo.update_git_repos

Sync Repo to Windows Minions
----------------------------

Run ``pkg.refresh_db`` on each of your Windows minions to synchronize
the package repository.

.. code-block:: bash

    salt -G 'os:windows' pkg.refresh_db

Install Windows Software
========================

After completing the configuration steps, you are ready to manage software on your
Windows minions.

Show Installed Packages
-----------------------

.. code-block:: bash

    salt -G 'os:windows' pkg.list_pkgs

Install a Package
-----------------

You can query the available version of a package using the Salt pkg module.

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

.. note::
    ``pkg.purge`` just executes ``pkg.remove`` on Windows. At some point in the
    future ``pkg.purge`` may direct the installer to remove all configs and
    settings for software packages that support that option.


Repository Location
===================

Salt maintains a repository of SLS files to install a large number of Windows
packages:

- 2015.8.0 and later minions: https://github.com/saltstack/salt-winrepo-ng
- Earlier releases: https://github.com/saltstack/salt-winrepo

By default, these repositories are mirrored to ``/srv/salt/win/repo_ng``
and ``/srv/salt/win/repo``.

This location can be changed in the master config file by setting the
:conf_master:`winrepo_dir_ng` and :conf_master:`winrepo_dir` options.


Maintaining Windows Repo Definitions in Git Repositories
========================================================

Windows software package definitions can be hosted in one or more Git
repositories. The default repositories are hosted on GitHub by SaltStack. These
include software definition files for various open source software projects.
These software definition files are ``.sls`` files. There are two default
repositories: ``salt-winrepo`` and ``salt-winrepo-ng``. ``salt-winrepo``
contains software definition files for older minions (older than 2015.8.0).
``salt-winrepo-ng`` is for newer minions (2015.8.0 and newer).

Each software definition file contains all the information salt needs to install
that software on a minion including the HTTP or FTP locations of the installer
files, required command-line switches for silent install, etc. Anyone is welcome
to send a pull request to this repo to add new package definitions. The repos
can be browsed here:
`salt-winrepo`_
`salt-winrepo-ng`_

.. _salt-winrepo: https://github.com/saltstack/salt-winrepo.git
.. _salt-winrepo-ng: https://github.com/saltstack/salt-winrepo-ng.git

.. note::
    The newer software definition files are run through the salt's parser which
    allows for the use of jinja.

Configure which git repositories the master can search for package definitions
by modifying or extending the :conf_master:`winrepo_remotes` and
:conf_master:`winrepo_remotes_ng` options.

.. important::
    ``winrepo_remotes`` was called ``win_gitrepos`` in Salt versions earlier
    than 2015.8.0

Package definitions are pulled down from the online repository by running the
:mod:`winrepo.update_git_repos <salt.runners.winrepo.update_git_repos>` runner.
This command is run on the master:

.. code-block:: bash

    salt-run winrepo.update_git_repos

This will pull down the software definition files for older minions
(``salt-winrepo``) and new minions (``salt-winrepo-ng``). They are stored in the
``file_roots`` under ``win/repo/salt-winrepo`` and
``win/repo-ng/salt-winrepo-ng`` respectively.

.. important::
    If you have customized software definition files that aren't maintained in a
    repository, those should be stored under ``win/repo`` for older minions and
    ``win/repo-ng`` for newer minions. The reason for this is that the contents
    of ``win/repo/salt-winrepo`` and ``win/repo-ng/salt-winrepo-ng`` are wiped
    out every time you run a ``winrepo.update_git_repos``.

    Additionally, when you run ``winrepo.genrepo`` and ``pkg.refresh_db`` the
    entire contents under ``win/repo`` and ``win/repo-ng``, to include all
    subdirectories, are used to create the msgpack file.

The next step (if you have older minions) is to create the msgpack file for the
repo (``winrepo.p``). This is done by running the
:mod:`winrepo.genrepo <salt.runners.winrepo.genrepo>` runner. This is also run
on the master:

.. code-block:: bash

    salt-run winrepo.genrepo

.. note::
    If you have only 2015.8.0 and newer minions, you no longer need to run
    ``salt-run winrepo.genrepo`` on the master.

Finally, you need to refresh the minion database by running the
:py:func:`pkg.refresh_db <salt.modules.win_pkg.refresh_db>` command. This is run
on the master as well:

.. code-block:: bash

    salt '*' pkg.refresh_db

On older minions (older than 2015.8.0) this will copy the winrepo.p file down to
the minion. On newer minions (2015.8.0 and newer) this will copy all the
software definition files (.sls) down to the minion and then create the msgpack
file (``winrepo.p``) locally. The reason this is done locally is because the
jinja needs to be parsed using the minion's grains.

.. important::
    Every time you modify the software definition files on the master, either by
    running ``salt-run winrepo.update_git_repos``, modifying existing files, or
    by creating your own, you need to refresh the database on your minions. For
    older minions, that means running ``salt-run winrepo.genrepo`` and then
    ``salt '*' pkg.refresh_db``. For newer minions (2015.8.0 and newer) it is
    just ``salt '*' pkg.refresh_db``.

.. note::
    If the ``winrepo.genrepo`` or the ``pkg.refresh_db`` fails, it is likely a
    problem with the jinja in one of the software definition files. This will
    cause the operations to stop. You'll need to fix the syntax in order for the
    msgpack file to be created successfully.

To disable one of the repos, set it to an empty list ``[]`` in the master
config. For example, to disable :conf_master:`winrepo_remotes` set the following
in the master config file:

.. code-block:: bash

    winrepo_remotes: []


Creating a Package Definition SLS File
======================================

The package definition file is a yaml file that contains all the information
needed to install a piece of software using salt. It defines information about
the package to include version, full name, flags required for the installer and
uninstaller, whether or not to use the windows task scheduler to install the
package, where to find the installation package, etc.

Take a look at this example for Firefox:

.. code-block:: yaml

    firefox:
      '17.0.1':
        installer: 'salt://win/repo/firefox/English/Firefox Setup 17.0.1.exe'
        full_name: Mozilla Firefox 17.0.1 (x86 en-US)
        locale: en_US
        reboot: False
        install_flags: '-ms'
        uninstaller: '%ProgramFiles(x86)%/Mozilla Firefox/uninstall/helper.exe'
        uninstall_flags: '/S'
      '16.0.2':
        installer: 'salt://win/repo/firefox/English/Firefox Setup 16.0.2.exe'
        full_name: Mozilla Firefox 16.0.2 (x86 en-US)
        locale: en_US
        reboot: False
        install_flags: '-ms'
        uninstaller: '%ProgramFiles(x86)%/Mozilla Firefox/uninstall/helper.exe'
        uninstall_flags: '/S'
      '15.0.1':
        installer: 'salt://win/repo/firefox/English/Firefox Setup 15.0.1.exe'
        full_name: Mozilla Firefox 15.0.1 (x86 en-US)
        locale: en_US
        reboot: False
        install_flags: '-ms'
        uninstaller: '%ProgramFiles(x86)%/Mozilla Firefox/uninstall/helper.exe'
        uninstall_flags: '/S'

Each software definition file begins with a package name for the software. As in
the example above ``firefox``. The next line is indented two spaces and contains
the version to be defined. As in the example above, a software definition file
can define multiple versions for the same piece of software. The lines following
the version are indented two more spaces and contain all the information needed
to install that package.

.. warning:: The package name and the ``full_name`` must be unique to all
    other packages in the software repository.

The version line is the version for the package to be installed. It is used when
you need to install a specific version of a piece of software.

.. warning:: The version must be enclosed in quotes, otherwise the yaml parser
    will remove trailing zeros.

.. note:: There are unique situations where previous versions are unavailable.
    Take Google Chrome for example. There is only one url provided for a
    standalone installation of Google Chrome.
    (https://dl.google.com/edgedl/chrome/install/GoogleChromeStandaloneEnterprise.msi)
    When a new version is released, the url just points to the new version. To
    handle situations such as these, set the version to `latest`. Salt will
    install the version of Chrome at the URL and report that version. Here's an
    example:

.. code-block:: bash

    chrome:
      latest:
        full_name: 'Google Chrome'
        installer: 'https://dl.google.com/edgedl/chrome/install/GoogleChromeStandaloneEnterprise.msi'
        install_flags: '/qn /norestart'
        uninstaller: 'https://dl.google.com/edgedl/chrome/install/GoogleChromeStandaloneEnterprise.msi'
        uninstall_flags: '/qn /norestart'
        msiexec: True
        locale: en_US
        reboot: False

Available parameters are as follows:

:param str full_name: The Full Name for the software as shown in "Programs and
    Features" in the control panel. You can also get this information by
    installing the package manually and then running ``pkg.list_pkgs``. Here's
    an example of the output from ``pkg.list_pkgs``:

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

Notice the Full Name for Firefox: Mozilla Firefox 17.0.0 (x86 en-US). That's
exactly what's in the ``full_name`` parameter in the software definition file.

If any of the software insalled on the machine matches one of the software
definition files in the repository the full_name will be automatically renamed
to the package name. The example below shows the ``pkg.list_pkgs`` for a
machine that already has Mozilla Firefox 17.0.1 installed.

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

.. important:: The version number and ``full_name`` need to match the output
    from ``pkg.list_pkgs`` so that the status can be verified when running
    highstate.

.. note:: It is still possible to successfully install packages using
    ``pkg.install`` even if they don't match. This can make troubleshooting
    difficult so be careful.

:param str installer: The path to the ``.exe`` or ``.msi`` to use to install the
    package. This can be a path or a URL. If it is a URL or a salt path
    (salt://), the package will be cached locally and then executed. If it is a
    path to a file on disk or a file share, it will be executed directly.

:param str install_flags: Any flags that need to be passed to the installer to
    make it perform a silent install. These can often be found by adding ``/?``
    or ``/h`` when running the installer from the command-line. A great resource
    for finding these silent install flags can be found on the WPKG project's wiki_:

Salt will not return if the installer is waiting for user input so these are
important.

:param str uninstaller: The path to the program used to uninstall this software.
    This can be the path to the same `exe` or `msi` used to install the
    software. It can also be a GUID. You can find this value in the registry
    under the following keys:

    - Software\\Microsoft\\Windows\\CurrentVersion\\Uninstall
    - Software\\Wow6432None\\Microsoft\\Windows\\CurrentVersion\\Uninstall

:param str uninstall_flags: Any flags that need to be passed to the uninstaller
    to make it perform a silent uninstall. These can often be found by adding
    ``/?`` or ``/h`` when running the uninstaller from the command-line. A great
    resource for finding these silent install flags can be found on the WPKG
    project's wiki_:

Salt will not return if the uninstaller is waiting for user input so these are
important.

Here are some examples of installer and uninstaller settings:

.. code-block:: yaml

    7zip:
      '9.20.00.0':
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
      '9.20.00.0':
        installer: salt://win/repo/7zip/7z920-x64.msi
        full_name: 7-Zip 9.20 (x64 edition)
        reboot: False
        install_flags: '/qn /norestart'
        msiexec: True
        uninstaller: salt://win/repo/7zip/7z920-x64.msi
        uninstall_flags: '/qn /norestart'

:param bool msiexec: This tells salt to use ``msiexec /i`` to install the
    package and ``msiexec /x`` to uninstall. This is for `.msi` installations.

:param bool allusers: This parameter is specific to `.msi` installations. It
    tells `msiexec` to install the software for all users. The default is True.

:param bool cache_dir: If true, the entire directory where the installer resides
    will be recursively cached. This is useful for installers that depend on
    other files in the same directory for installation.

.. note:: Only applies to salt: installer URLs.

Here's an example for a software package that has dependent files:

.. code-block:: yaml

    sqlexpress:
      '12.0.2000.8':
        installer: 'salt://win/repo/sqlexpress/setup.exe'
        full_name: Microsoft SQL Server 2014 Setup (English)
        reboot: False
        install_flags: '/ACTION=install /IACCEPTSQLSERVERLICENSETERMS /Q'
        cache_dir: True

:param bool use_scheduler: If true, windows will use the task scheduler to run
    the installation. This is useful for running the salt installation itself as
    the installation process kills any currently running instances of salt.

:param str source_hash: This tells salt to compare a hash sum of the installer
to the provided hash sum before execution. The value can be formatted as
``hash_algorithm=hash_sum``, or it can be a URI to a file containing the hash
sum.
For a list of supported algorithms, see the `hashlib documentation
<https://docs.python.org/2/library/hashlib.html>`_.

Here's an example of source_hash usage:

.. code-block:: yaml

    messageanalyzer:
      '4.0.7551.0':
        full_name: 'Microsoft Message Analyzer'
        installer: 'salt://win/repo/messageanalyzer/MessageAnalyzer64.msi'
        install_flags: '/quiet /norestart'
        uninstaller: '{1CC02C23-8FCD-487E-860C-311EC0A0C933}'
        uninstall_flags: '/quiet /norestart'
        msiexec: True
        source_hash: 'sha1=62875ff451f13b10a8ff988f2943e76a4735d3d4'

:param bool reboot: Not implemented

:param str local: Not implemented

Examples can be found at https://github.com/saltstack/salt-winrepo-ng


.. _standalone-winrepo:

Managing Windows Software on a Standalone Windows Minion
========================================================

The Windows Package Repository functions similar in a standalone environment,
with a few differences in the configuration.

To replace the winrepo runner that is used on the Salt master, an :mod:`execution module
<salt.modules.win_repo>` exists to provide the same functionality to standalone
minions. The functions are named the same as the ones in the runner, and are
used in the same way; the only difference is that ``salt-call`` is used instead
of ``salt-run``:

.. code-block:: bash

    salt-call winrepo.update_git_repos
    salt-call winrepo.genrepo
    salt-call pkg.refresh_db

After executing the previous commands the repository on the standalone system
is ready to use.

Custom Location for Repository SLS Files
----------------------------------------

If :conf_minion:`file_roots` has not been modified in the minion
configuration, then no additional configuration needs to be added to the
minion configuration. The :py:func:`winrepo.genrepo
<salt.modules.win_repo.genrepo>` function from the :mod:`winrepo
<salt.modules.win_repo>` execution module will by default look for the
filename specified by :conf_minion:`winrepo_cachefile` within
``C:\salt\srv\salt\win\repo``.

If the :conf_minion:`file_roots` parameter has been modified, then
:conf_minion:`winrepo_dir` must be modified to fall within that path, at the
proper relative path. For example, if the ``base`` environment in
:conf_minion:`file_roots` points to ``D:\foo``, and
:conf_minion:`winrepo_source_dir` is ``salt://win/repo``, then
:conf_minion:`winrepo_dir` must be set to ``D:\foo\win\repo`` to ensure that
:py:func:`winrepo.genrepo <salt.modules.win_repo.genrepo>` puts the cachefile
into right location.


Config Options for Minions 2015.8.0 and Later
=============================================

The :conf_minion:`winrepo_source_dir` config parameter (default:
``salt://win/repo``) controls where :mod:`pkg.refresh_db
<salt.modules.win_pkg.refresh_db>` looks for the cachefile (default:
``winrepo.p``). This means that the default location for the winrepo cachefile
would be ``salt://win/repo/winrepo.p``. Both :conf_minion:`winrepo_source_dir`
and :conf_minion:`winrepo_cachefile` can be adjusted to match the actual
location of this file on the Salt fileserver.


Config Options for Minions Before 2015.8.0
==========================================

If connected to a master, the minion will by default look for the winrepo
cachefile (the file generated by the :mod:`winrepo.genrepo runner
<salt.runners.winrepo.genrepo>`) at ``salt://win/repo/winrepo.p``. If the
cachefile is in a different path on the salt fileserver, then
:conf_minion:`win_repo_cachefile` will need to be updated to reflect the proper
location.


.. _2015-8-0-winrepo-changes:

Changes in Version 2015.8.0
===========================

Git repository management for the Windows Software Repository has changed
in version 2015.8.0, and several master/minion config parameters have been
renamed to make their naming more consistent with each other.

For a list of the winrepo config options, see :ref:`here
<winrepo-master-config-opts>` for master config options, and :ref:`here
<winrepo-minion-config-opts>` for configuration options for masterless Windows
minions.

On the master, the :mod:`winrepo.update_git_repos
<salt.runners.winrepo.update_git_repos>` runner has been updated to use either
pygit2_ or GitPython_ to checkout the git repositories containing repo data. If
pygit2_ or GitPython_ is installed, existing winrepo git checkouts should be
removed after upgrading to 2015.8.0, to allow them to be checked out again by
running :py:func:`winrepo.update_git_repos
<salt.runners.winrepo.update_git_repos>`.

If neither GitPython_ nor pygit2_ are installed, then Salt will fall back to
the pre-existing behavior for :mod:`winrepo.update_git_repos
<salt.runners.winrepo.update_git_repos>`, and a warning will be logged in the
master log.

.. note::
    Standalone Windows minions do not support the new GitPython_/pygit2_
    functionality, and will instead use the :py:func:`git.latest
    <salt.states.git.latest>` state to keep repositories up-to-date. More
    information on how to use the Windows Software Repo on a standalone minion
    can be found :ref:`here <standalone-winrepo>`.


Config Parameters Renamed
-------------------------

Many of the legacy winrepo configuration parameters have changed in version 2015.8.0
to make the naming more consistent. The old parameter names will still work,
but a warning will be logged indicating that the old name is deprecated.

Below are the parameters which have changed for version 2015.8.0:

Master Config
*************

======================== ================================
Old Name                 New Name
======================== ================================
win_repo                 :conf_master:`winrepo_dir`
win_repo_mastercachefile :conf_master:`winrepo_cachefile`
win_gitrepos             :conf_master:`winrepo_remotes`
======================== ================================

.. note::
    ``winrepo_cachefile`` is no longer used by 2015.8.0 and later minions, and
    the ``winrepo_dir`` setting is replaced by ``winrepo_dir_ng`` for 2015.8.0
    and later minions.

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
and the :py:func:`winrepo.update_git_repos
<salt.runners.winrepo.update_git_repos>` runner will not proceed if any are
detected. Consider the following configuration:

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

Ensure you have (re)generated the repository cache file (for older minions) and
then updated the repository cache on the relevant minions:

.. code-block:: bash

    salt-run winrepo.genrepo
    salt winminion pkg.refresh_db


Packages management under Windows 2003
--------------------------------------

On Windows server 2003, you need to install optional Windows component "wmi
windows installer provider" to have full list of installed packages. If you
don't have this, salt-minion can't report some installed software.


How Success and Failure are Reported
------------------------------------

The install state/module function of the Windows package manager works roughly
as follows:

1. Execute ``pkg.list_pkgs`` and store the result
2. Check if any action needs to be taken. (i.e. compare required package
   and version against ``pkg.list_pkgs`` results)
3. If so, run the installer command.
4. Execute ``pkg.list_pkgs`` and compare to the result stored from
   before installation.
5. Success/Failure/Changes will be reported based on the differences
   between the original and final ``pkg.list_pkgs`` results.

If there are any problems in using the package manager it is likely due to the
data in your sls files not matching the difference between the pre and post
``pkg.list_pkgs`` results.
