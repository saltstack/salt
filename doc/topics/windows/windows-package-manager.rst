.. _windows-package-manager:

#######################
Windows Package Manager
#######################

Introduction
************

Salt provides a Windows package management tool for installing, updating,
removing, and managing software packages on remote Windows systems. This tool
provides a software repository and a package manager similar to what is provided
by ``yum`` and ``apt`` on Linux. The repository contains a collection of package
definition files.

What are package definition files?
==================================

A package definition file is a YAML/JINJA2 file with a ``.sls`` file extension
that contains all the information needed to install software using Salt. It
defines:

- Full name of the software package
- The version of the software package
- Download location of the software package
- Command-line switches for silent install and uninstall
- Whether or not to use the Windows task scheduler to install the package

Package definition files can be hosted in one or more Git repositories. The
``.sls`` files used to install Windows packages are not distributed by default
with Salt. You have to initialize and clone the default repository
`salt-winrepo-ng <https://github.com/saltstack/salt-winrepo-ng>`_
which is hosted on GitHub by SaltStack. The repository contains package
definition files for many common Windows packages and is maintained by SaltStack
and the Salt community. Anyone can submit a pull request to this repo to add
new package definitions.

You can manage the package definition file through either Salt or Git. You can
download software packages from either a git repository or from HTTP(S) or FTP
URLs. You can store the installer defined in the package definition file
anywhere as long as it is accessible from the host running Salt.

You can use the Salt Windows package manager like ``yum`` on Linux. You do not
have to know the underlying command to install the software.

- Use ``pkg.install`` to install a package using a package manager based on
  the OS the system runs on.
- Use ``pkg.installed`` to check if a particular package is installed in the
  minion.

.. note::
    The Salt Windows package manager does not automatically resolve dependencies
    while installing, updating, or removing packages. You have to manage the
    dependencies between packages manually.

.. _quickstart:

Quickstart
==========

This quickstart guides you through using the Windows Salt package manager
(winrepo) to install software packages in four steps:

1. (Optional) :ref:`Install libraries <install-libraries>`
2. :ref:`Populate the local Git repository<populate-git-repo>`
3. :ref:`Update minion database<refresh-db>`
4. :ref:`Install software packages<pkg-install>`

.. _install-libraries:

Install libraries
*****************

(Optional) If you are using the Salt Windows package manager with package
definition files hosted on a Salt Git repo, install the libraries ``GitPython``
or ``pygit2``\.

.. _populate-git-repo:

Populate the local Git repository
**********************************

The SLS files used to install Windows packages are not distributed by default
with Salt. Assuming no changes to the default configuration (``file_roots``),
initialize and clone `salt-winrepo-ng <https://github.com/saltstack/salt-winrepo-ng>`_
repository.

.. code-block:: bash

    salt-run winrepo.update_git_repos

On successful execution of :mod:`winrepo.update_git_repos <salt.runners.winrepo.update_git_repos>`,
the winrepo repository is cloned on the master in the location specified in
``winrepo_dir_ng`` and all package definition files are pulled down from the Git
repository.

On a masterless minion, use ``salt-call`` to initialize and clone the
`salt-winrepo-ng <https://github.com/saltstack/salt-winrepo-ng>`_

.. code-block:: bash

    salt-call --local winrepo.update_git_repos

On successful execution of the runner, the winrepo repository is cloned on the
minion in the location specified in ``winrepo_dir_ng``  and all package
definition files are pulled down from the Git repository.

.. _refresh-db:

Update minion database
**********************

Run :mod:`pkg.refresh_db <salt.modules.win_pkg.refresh_db>` on all Windows
minions to create a database entry for every package definition file and build
the package database.

.. code-block:: bash

    # From the master
    salt -G 'os:windows' pkg.refresh_db

    # From the minion in masterless mode
    salt-call --local pkg.refresh_db

The :mod:`pkg.refresh_db <salt.modules.win_pkg.refresh_db>` command parses the
YAML/JINJA package definition files and generates the database. The above
command returns the following summary denoting the number of packages that
succeeded or failed to compile:

.. code-block:: bash

    local:
        ----------
        failed:
            0
        success:
            301
        total:
            301

.. note::
    This command can take a few minutes to complete as all the package
    definition files are copied to the minion and the database is generated.

.. note::
    You can use ``pkg.refresh_db`` when writing new Windows package definitions
    to check for errors in the definitions against one or more Windows minions.

.. _pkg-install:

Install software package
************************

You can now install a software package using
:mod:`pkg.install <salt.modules.win_pkg.install>`:

.. code-block:: bash

    # From the master
    salt * pkg.install 'firefox_x64'

    # From the minion in masterless mode
    salt-call --local pkg.install "firefox_x64"

The above command installs the latest version of Firefox on the minions.

.. _configuration:

Configuration
*************

The Github repository (winrepo) is synced to the ``file_roots`` in a location
specified by the ``winrepo_dir_ng`` setting in the config. The default value of
``winrepo_dir_ng`` is as follows:

- Linux master: ``/srv/salt/win/repo-ng`` (``salt://win/repo-ng``)
- Masterless minion: ``C:\salt\srv\salt\win\repo-ng`` (``salt://win/repo-ng``)

.. _master-config:

Master Configuration
====================

The following settings are available for configuring the winrepo on the
master:

- :conf_master:`winrepo_dir`
- :conf_master:`winrepo_dir_ng`
- :conf_master:`winrepo_remotes`
- :conf_master:`winrepo_remotes_ng`
- :conf_master:`winrepo_branch`
- :conf_master:`winrepo_provider`
- :conf_master:`winrepo_ssl_verify`

See :ref:`here <winrepo-master-config-opts>` for detailed information on all
master config options for winrepo.

winrepo_dir
-----------

:conf_master:`winrepo_dir` (str)

This setting is maintained for backwards compatibility with legacy minions. It
points to the location in the ``file_roots`` where the winrepo files are kept.
The default is: ``/srv/salt/win/repo``

winrepo_dir_ng
--------------

:conf_master:`winrepo_dir_ng` (str)

The location in the ``file_roots`` where the winrepo files are kept. The default
is ``/srv/salt/win/repo-ng``\.

.. warning::
    You can change the location of the winrepo directory. However, it must
    always be set to a path that is inside the ``file_roots``\.  Otherwise, the
    software definition files will be unreachable by the minion.

.. important::
    A common mistake is to change the ``file_roots`` setting and fail to update
    the ``winrepo_dir_ng`` and ``winrepo_dir`` settings so that they are inside
    the ``file_roots``

winrepo_remotes
---------------

:conf_master:`winrepo_remotes` (list)

This setting is maintained for backwards compatibility with legacy minions. It
points to the legacy git repo. The default is a list containing a single URL:

`https://github.com/saltstack/salt-winrepo <https://github.com/saltstack/salt-winrepo>`_

The legacy repo can be disabled by setting it to an empty list in the master
config.

.. code-block:: bash

    winrepo_remotes: []

winrepo_remotes_ng
------------------

:conf_master:`winrepo_remotes_ng` (list)

This setting tells the ``winrepo.update_git_repos`` command where the next
generation winrepo is hosted. This a list of URLs to multiple git repos. The
default is a list containing a single URL:

`https://github.com/saltstack/salt-winrepo-ng
<https://github.com/saltstack/salt-winrepo-ng>`_

winrepo_refspecs
----------------

:conf_master:`winrepo_refspecs` (list)

Specify what references to fetch from remote repositories. The default is
``['+refs/heads/*:refs/remotes/origin/*', '+refs/tags/*:refs/tags/*']``

winrepo_branch
--------------

:conf_master:`winrepo_branch` (str)

The branch of the git repo to checkout. The default is ``master``

winrepo_provider
----------------

:conf_master:`winrepo_provider` (str)

The provider to be used for winrepo. Default is ``pygit2``\. Falls back to
``gitpython`` when ``pygit2`` is not available

winrepo_ssl_verify
------------------

:conf_master:`winrepo_ssl_verify` (bool)

Ignore SSL certificate errors when contacting remote repository. Default is
``False``

.. _master-config-pygit2:

Master Configuration (pygit2)
=============================

The following configuration options only apply when the
:conf_master:`winrepo_provider` option is set to ``pygit2``\.

- :conf_master:`winrepo_insecure_auth`
- :conf_master:`winrepo_passphrase`
- :conf_master:`winrepo_password`
- :conf_master:`winrepo_privkey`
- :conf_master:`winrepo_pubkey`
- :conf_master:`winrepo_user`

winrepo_insecure_auth
---------------------

:conf_master:`winrepo_insecure_auth` (bool)

Used only with ``pygit2`` provider. Whether or not to allow insecure auth.
Default is ``False``

winrepo_passphrase
------------------

:conf_master:`winrepo_passphrase` (str)

Used only with ``pygit2`` provider. Used when the SSH key being used to
authenticate is protected by a passphrase. Default is ``''``

winrepo_privkey
---------------

:conf_master:`winrepo_privkey` (str)

Used only with ``pygit2`` provider. Used with :conf_master:`winrepo_pubkey` to
authenticate to SSH remotes. Default is ``''``

winrepo_pubkey
--------------

:conf_master:`winrepo_pubkey` (str)

Used only with ``pygit2`` provider. Used with :conf_master:`winrepo_privkey` to
authenticate to SSH remotes. Default is ``''``

winrepo_user
------------

:conf_master:`winrepo_user` (str)

Used only with ``pygit2`` provider. Used with :conf_master:`winrepo_password` to
authenticate to HTTPS remotes. Default is ``''``

winrepo_password
----------------

:conf_master:`winrepo_password` (str)

Used only with ``pygit2`` provider. Used with :conf_master:`winrepo_user` to
authenticate to HTTPS remotes. Default is ``''``

.. _minion-config:

Minion Configuration
====================

Refreshing the package definitions can take some time, these options were
introduced to allow more control of when it occurs. These settings apply to all
minions whether in masterless mode or not.

- :conf_minion:`winrepo_cache_expire_max`
- :conf_minion:`winrepo_cache_expire_min`
- :conf_minion:`winrepo_cachefile`
- :conf_minion:`winrepo_source_dir`

winrepo_cache_expire_max
------------------------

:conf_minion:`winrepo_cache_expire_max` (int)

Sets the maximum age in seconds of the winrepo metadata file to avoid it
becoming stale. If the metadata file is older than this setting, it will trigger
a ``pkg.refresh_db`` on the next run of any ``pkg`` module function that
requires the metadata file. Default is 604800 (1 week).

Software package definitions are automatically refreshed if stale after
:conf_minion:`winrepo_cache_expire_max`. Running a highstate forces the refresh
of the package definitions and regenerates the metadata, unless the metadata is
younger than :conf_minion:`winrepo_cache_expire_max`.

winrepo_cache_expire_min
------------------------

:conf_minion:`winrepo_cache_expire_min` (int)

Sets the minimum age in seconds of the winrepo metadata file to avoid refreshing
too often. If the metadata file is older than this setting, the metadata will be
refreshed unless you pass ``refresh: False`` in the state. Default is 1800
(30 min).

winrepo_cachefile
-----------------

:conf_minion:`winrepo_cachefile` (str)

The file name of the winrepo cache file. The file is placed at the root of
``winrepo_dir_ng``\. Default is ``winrepo.p``\.

winrepo_source_dir
------------------

:conf_minion:`winrepo_source_dir` (str)

The location of the .sls files on the Salt file server. Default is
``salt://win/repo-ng/``.

.. warning::
    If the default for ``winrepo_dir_ng`` is changed, then this setting will
    also need to be changed on each minion. The default setting for
    ``winrepo_dir_ng`` is ``/srv/salt/win/repo-ng``. If that were changed to
    ``/srv/salt/new/repo-ng`` then the ``winrepo_source_dir`` would need to be
    changed to ``salt://new/repo-ng``


.. _masterless-minion-config:

Masterless Minion Configuration
===============================

The following settings are available for configuring the winrepo on a masterless
minion:

- :conf_minion:`winrepo_dir`
- :conf_minion:`winrepo_dir_ng`
- :conf_minion:`winrepo_remotes`
- :conf_minion:`winrepo_remotes_ng`

See :ref:`here <winrepo-minion-config-opts>` for detailed information on all
minion config options for winrepo.

winrepo_dir
-----------

:conf_minion:`winrepo_dir` (str)

This setting is maintained for backwards compatibility with legacy minions. It
points to the location in the ``file_roots`` where the winrepo files are kept.
The default is: ``C:\ProgramData\Salt Project\Salt\srv\salt\win\repo``

winrepo_dir_ng
--------------

:conf_minion:`winrepo_dir_ng` (str)

The location in the ``file_roots`` where the winrepo files are kept. The default
is ``C:\ProgramData\Salt Project\Salt\srv\salt\win\repo-ng``.

.. warning::
    You can change the location of the winrepo directory. However, it must
    always be set to a path that is inside the ``file_roots``\.  Otherwise, the
    software definition files will be unreachable by the minion.

.. important::
    A common mistake is to change the ``file_roots`` setting and fail to update
    the ``winrepo_dir_ng`` and ``winrepo_dir`` settings so that they are inside
    the ``file_roots``\. You might also want to verify ``winrepo_source_dir`` on
    the minion as well.

winrepo_remotes
---------------

:conf_minion:`winrepo_remotes` (list)

This setting is maintained for backwards compatibility with legacy minions. It
points to the legacy git repo. The default is a list containing a single URL:

`https://github.com/saltstack/salt-winrepo
<https://github.com/saltstack/salt-winrepo>`_

The legacy repo can be disabled by setting it to an empty list in the minion
config.

.. code-block:: bash

    winrepo_remotes: []

winrepo_remotes_ng
------------------

:conf_minion:`winrepo_remotes_ng` (list)

This setting tells the ``winrepo.update_git_repos`` command where the next
generation winrepo is hosted. This a list of URLs to multiple git repos. The
default is a list containing a single URL:

`https://github.com/saltstack/salt-winrepo-ng
<https://github.com/saltstack/salt-winrepo-ng>`_

.. _usage:


Sample Configurations
*********************

Masterless
==========

The configs in this section are for working with winrepo on a Windows minion
using ``salt-call --local``.

Default Configuration
---------------------

This is the default configuration if nothing is configured in the minion config.
The config is shown here for clarity. These are the defaults:

.. code-block:: yaml

    file_roots:
      base:
        - C:\ProgramData\Salt Project\Salt\srv\salt
    winrepo_source_dir: 'salt://win/repo-ng'
    winrepo_dir_ng: C:\ProgramData\Salt Project\Salt\srv\salt\win\repo-ng

The :mod:`winrepo.update_git_repos <salt.modules.winrepo.update_git_repos>`
command will clone the repository to ``win\repo-ng`` on the file_roots.

Multiple Salt Environments
--------------------------

This starts to get a little tricky. The winrepo repository doesn't
get cloned to each environment when you run
:mod:`winrepo.update_git_repos <salt.runners.winrepo.update_git_repos>`, so to
make this work, all environments share the same winrepo. Applying states using
the ``saltenv`` option will find the state files in the appropriate environment,
but the package definition files will always be pulled from the same location.
Therefore, you have to put the same winrepo location in each saltenv. Here's how
this would look:

.. code-block:: yaml

    file_roots:
      base:
        - C:\ProgramData\Salt Project\Salt\srv\salt\base
        - C:\ProgramData\Salt Project\Salt\srv\salt\winrepo
      test:
        - C:\ProgramData\Salt Project\Salt\srv\salt\test
        - C:\ProgramData\Salt Project\Salt\srv\salt\winrepo
    winrepo_source_dir: 'salt://salt-winrepo-ng'
    winrepo_dir_ng: C:\ProgramData\Salt Project\Salt\srv\salt\winrepo
    winrepo_dir: C:\ProgramData\Salt Project\Salt\srv\salt\winrepo

When you run
:mod:`winrepo.update_git_repos <salt.runners.winrepo.update_git_repos>` the
Git repository will be cloned to the location specified in the
``winrepo_dir_ng`` setting. I specified the ``winrepo_dir`` setting just so
everything gets cloned to the same place. The directory that gets cloned is
named ``salt-winrepo-ng`` so you specify that in the ``winrepo_source_dir``
setting.

The ``winrepo`` directory should only contain the package definition files. You
wouldn't want to place any states in the ``winrepo`` directory as they will be
available to both environments.

Master
======

When working in a Master/Minion environment you have to split up some of the
config settings between the master and the minion. Here are some sample configs
for winrepo in a Master/Minion environment.

Default Configuration
---------------------

This is the default configuration if nothing is configured. The config is shown
here for clarity. These are the defaults on the master:

.. code-block:: yaml

    file_roots:
      base:
        - /srv/salt
    winrepo_dir_ng: /srv/salt/win/repo-ng

This is the default in the minion config:

.. code-block:: yaml

    winrepo_source_dir: 'salt://win/repo-ng'

The :mod:`winrepo.update_git_repos <salt.runners.winrepo.update_git_repos>`
command will clone the repository to ``win\repo-ng`` on the file_roots.

Multiple Salt Environments
--------------------------

To set up multiple saltenvs using a Master/Minion configuration set the
following in the master config:

.. code-block:: yaml

    file_roots:
      base:
        - /srv/salt/base
        - /srv/salt/winrepo
      test:
        - /srv/salt/test
        - /srv/salt/winrepo
    winrepo_dir_ng: /srv/salt/winrepo
    winrepo_dir: /srv/salt/winrepo

Use the winrepo runner to set up the winrepo repository on the master.

.. code-block:: bash

    salt-run winrepo.update_git_repos

The winrepo will be cloned to ``/srv/salt/winrepo`` under a directory named
``salt-winrepo-ng``.

Set the following on the minion config so the minion knows where to find the
package definition files in the file_roots:

.. code-block:: yaml

    winrepo_source_dir: 'salt://salt-winrepo-ng'

The same stipulations apply in a Master/Minion configuration as they do in a
Masterless configuration


Usage
*****

After completing the configuration and initialization, you can use the Salt
package manager commands to manage software on Windows minions.

.. note::
    The following example commands can be run from the master using ``salt`` or
    on a masterless minion using ``salt-call``

.. list-table::
  :widths: 5 50 45
  :align: left
  :header-rows: 1
  :stub-columns: 1

  * -
    - Command
    - Description

  * - 1
    - :ref:`pkg.list_pkgs <list-pkgs>`
    - Displays a list of all packages installed in the system.

  * - 2
    - :ref:`pkg.list_available <list-available>`
    - Displays the versions available of a particular package to be installed.

  * - 3
    - :ref:`pkg.install <install>`
    - Installs a given package.

  * - 4
    - :ref:`pkg.remove <remove>`
    - Uninstalls a given package.

.. _list-pkgs:

List installed packages
=======================

Use :mod:`pkg.list_pkgs <salt.modules.win_pkg.list_pkgs>` to display a list of
packages installed on the system.

.. code-block:: bash

    # From the master
    salt -G 'os:windows' pkg.list_pkgs

    # From the minion in masterless mode
    salt-call --local pkg.list_pkgs

The command displays the software name and the version for every package
installed on the system irrespective of whether it was installed by the Salt
package manager.

.. code-block:: bash

    local:
        ----------
        Frhed 1.6.0:
            1.6.0
        GNU Privacy Guard:
            2.2.16
        Gpg4win (3.1.9):
            3.1.9
        git:
            2.17.1.2
        nsis:
            3.03
        python3_x64:
            3.7.4150.0
        salt-minion-py3:
            2019.2.3

The software name indicates whether the software is managed by Salt or not.

If Salt finds a match in the winrepo database, then the software name is the
short name as defined in the package definition file. It is usually a
single-word, lower-case name.

All other software names are displayed as the full name as shown in
Add/Remove Programs. In the above example, Git (git), Nullsoft Installer (nsis),
Python 3.7 (python3_x64), and Salt (salt-minion-py3) have corresponding package
definition files and are managed by Salt, while Frhed 1.6.0, GNU Privacy guard,
and GPG4win are not.

.. _list-available:

List available versions
=======================

Use :mod:`pkg.list_available <salt.modules.win_pkg.list_available>` to display
a list of versions of a package available for installation. You can pass the
name of the software in the command. You can refer to the software by its
``name`` or its ``full_name`` surrounded by quotes.

.. code-block:: bash

    # From the master
    salt winminion pkg.list_available firefox_x64

    # From the minion in masterless mode
    salt-call --local pkg.list_available firefox_x64

The command lists all versions of Firefox available for installation.

.. code-block:: bash

    winminion:
        - 69.0
        - 69.0.1
        - 69.0.2
        - 69.0.3
        - 70.0
        - 70.0.1
        - 71.0
        - 72.0
        - 72.0.1
        - 72.0.2
        - 73.0
        - 73.0.1
        - 74.0

.. note::
    For a Linux master, you can surround the file name with single quotes.
    However, for the ``cmd`` shell on Windows, use double quotes when wrapping
    strings that may contain spaces. Powershell accepts either single quotes or
    double quotes.

.. _install:

Install a package
=================

Use :mod:`pkg.install <salt.modules.win_pkg.install>`: to install a package.

.. code-block:: bash

    # From the master
    salt winminion pkg.install 'firefox_x64'

    # From the minion in masterless mode
    salt-call --local pkg.install "firefox_x64"

The command installs the latest version of Firefox.

.. code-block:: bash

    # From the master
    salt winminion pkg.install 'firefox_x64' version=74.0

    # From the minion in masterless mode
    salt-call --local pkg.install "firefox_x64" version=74.0

The command installs version 74.0 of Firefox.

If a different version of the package is already installed, then the old version
is replaced with the version in the winrepo (only if the package supports live
updating).

You can also specify the full name of the software while installing:

.. code-block:: bash

    # From the master
    salt winminion pkg.install 'Mozilla Firefox 17.0.1 (x86 en-US)'

    # From the minion in masterless mode
    salt-call --local pkg.install "Mozilla Firefox 17.0.1 (x86 en-US)"

.. _remove:

Remove a package
================

Use :mod:`pkg.remove <salt.modules.win_pkg.remove>` to remove a package.

.. code-block:: bash

    # From the master
    salt winminion pkg.remove firefox_x64

    # From the minion in masterless mode
    salt-call --local pkg.remove firefox_x64

.. _winrepo-structure:

Package definition file directory structure and naming
======================================================

All package definition files are stored in the location configured in the
``winrepo_dir_ng`` setting. All files in this directory with a ``.sls`` file
extension are considered package definition files. These files are evaluated to
create the metadata file on the minion.

You can maintain standalone package definition files that point to software on
other servers or on the internet. In this case the file name is the short name
of the software with the ``.sls`` extension, for example,``firefox.sls``\.

You can also store the binaries for your software together with their software
definition files in their own directory. In this scenario, the directory name
is the short name for the software and the package definition file stored that
directory is named ``init.sls``\.

Look at the following example directory structure on a Linux master assuming
default config settings:

.. code-block:: bash

    srv/
    |---salt/
    |   |---win/
    |   |   |---repo-ng/
    |   |   |   |---custom_defs/
    |   |   |   |   |---ms_office_2013_x64/
    |   |   |   |   |   |---access.en-us/
    |   |   |   |   |   |---excel.en-us/
    |   |   |   |   |   |---outlook.en-us/
    |   |   |   |   |   |---powerpoint.en-us/
    |   |   |   |   |   |---word.en-us/
    |   |   |   |   |   |---init.sls
    |   |   |   |   |   |---setup.dll
    |   |   |   |   |   |---setup.exe
    |   |   |   |   |---openssl.sls
    |   |   |   |   |---zoom.sls
    |   |   |   |---salt-winrepo-ng/
    |   |   |   |   |---auditbeat/
    |   |   |   |   |   |---init.sls
    |   |   |   |   |   |---install.cmd
    |   |   |   |   |   |---install.ps1
    |   |   |   |   |   |---remove.cmd
    |   |   |   |   |---gpg4win/
    |   |   |   |   |   |---init.sls
    |   |   |   |   |   |---silent.ini
    |   |   |   |   |---7zip.sls
    |   |   |   |   |---adobereader.sls
    |   |   |   |   |---audacity.sls
    |   |   |   |   |---ccleaner.sls
    |   |   |   |   |---chrome.sls
    |   |   |   |   |---firefox.sls

In the above directory structure:

- The ``custom_defs`` directory contains the following custom package definition
  files.

  - A folder for MS Office 2013 that contains the installer files for all the
    MS Office software and a package definition file named ``init.sls``\.
  - Two additional standalone package definition files ``openssl.sls`` and
    ``zoom.sls`` to install OpenSSl and Zoom.

- The ``salt-winrepo-ng`` directory contains the clone of the git repo specified
  by the ``winrepo_remotes_ng`` config setting.

.. warning::
    Do not modify the files in the ``salt-winrepo-ng`` directory as it breaks
    future runs of ``winrepo.update_git_repos``\.

.. warning::
    Do not place any custom software definition files in the ``salt-winrepo-ng``
    directory as the ``winrepo.update_git_repos`` command wipes out the contents
    of the ``salt-winrepo-ng`` directory each time it is run and any extra files
    stored in the Salt winrepo are lost.

..

.. _pkg-definition:

Writing package definition files
================================
You can write your own software definition file if you know:

- The full name of the software as shown in Add/Remove Programs
- The exact version number as shown in Add/Remove Programs
- How to install your software silently from the command line

Here is a YAML software definition file for Firefox:

.. code-block:: yaml

    firefox_x64:
      '74.0':
        full_name: Mozilla Firefox 74.0 (x64 en-US)
        installer: 'https://download-installer.cdn.mozilla.net/pub/firefox/releases/74.0/win64/en-US/Firefox%20Setup%2074.0.exe'
        install_flags: '/S'
        uninstaller: '%ProgramFiles(x86)%/Mozilla Firefox/uninstall/helper.exe'
        uninstall_flags: '/S'
      '73.0.1':
        full_name: Mozilla Firefox 73.0.1 (x64 en-US)
        installer: 'https://download-installer.cdn.mozilla.net/pub/firefox/releases/73.0.1/win64/en-US/Firefox%20Setup%2073.0.1.exe'
        install_flags: '/S'
        uninstaller: '%ProgramFiles(x86)%/Mozilla Firefox/uninstall/helper.exe'
        uninstall_flags: '/S'

The package definition file itself is a data structure written in YAML with
three indentation levels:

- The first level item is a short name that Salt uses to reference the software.
  This short name is used to install and remove the software and it must be
  unique across all package definition files in the repo. Also, there must be
  only one short name in the file.
- The second level item is the version number. There can be multiple version
  numbers for a package but they must be unique within the file.

.. note::
    When running ``pkg.list_pkgs``\, the short name and version number are
    displayed when Salt finds a match in the repo. Otherwise, the full package
    name is displayed.

- The third indentation level contains all parameters that Salt needs to install
  the software. The parameters are:

  - ``full_name`` : The full name as displayed in Add/Remove Programs
  - ``installer`` : The location of the installer binary
  - ``install_flags`` : The flags required to install silently
  - ``uninstaller`` : The location of the uninstaller binary
  - ``uninstall_flags`` : The flags required to uninstall silently
  - ``msiexec`` : Use msiexec to install this package
  - ``allusers`` : If this is an MSI, install to all users
  - ``cache_dir`` : Cache the entire directory in the installer URL if it starts
    with ``salt://``
  - ``cache_file`` : Cache a single file in the installer URL if it starts with
    ``salt://``
  - ``use_scheduler`` : Launch the installer using the task scheduler
  - ``source_hash`` : The hash sum for the installer

Example package definition files
================================
This section provides some examples of package definition files for different
use cases such as:

- Writing a :ref:`simple package definition file <example-simple>`
- Writing a :ref:`JINJA templated package definition file <example-jinja>`
- Writing a package definition file to :ref:`install the latest version of the software <example-latest>`
- Writing a package definition file to :ref:`install an MSI patch <example-patch>`

These examples enable you to gain a better understanding of the usage of
different file parameters. To understand the examples, you need a basic
`Understanding Jinja <https://docs.saltproject.io/en/latest/topics/jinja/index.html>`_.
For an exhaustive dive into Jinja, refer to the official
`Jinja Template Designer documentation <https://docs.saltproject.io/en/getstarted/config/jinja.html>`_.

.. _example-simple:

Example: Simple
===============

Here is a pure YAML example of a simple package definition file for Firefox:

.. code-block:: yaml

    firefox_x64:
      '74.0':
        full_name: Mozilla Firefox 74.0 (x64 en-US)
        installer: 'https://download-installer.cdn.mozilla.net/pub/firefox/releases/74.0/win64/en-US/Firefox%20Setup%2074.0.exe'
        install_flags: '/S'
        uninstaller: '%ProgramFiles(x86)%/Mozilla Firefox/uninstall/helper.exe'
        uninstall_flags: '/S'
      '73.0.1':
        full_name: Mozilla Firefox 73.0.1 (x64 en-US)
        installer: 'https://download-installer.cdn.mozilla.net/pub/firefox/releases/73.0.1/win64/en-US/Firefox%20Setup%2073.0.1.exe'
        install_flags: '/S'
        uninstaller: '%ProgramFiles(x86)%/Mozilla Firefox/uninstall/helper.exe'
        uninstall_flags: '/S'

The first line is the short name of the software which is ``firefox_x64``\.

.. important::
    The short name must be unique across all other short names in the software
    repository. The ``full_name`` combined with the version must also be unique.

The second line is the ``software version`` and is indented two spaces.

.. important::
    The version number must be enclosed in quotes or the YAML parser removes the
    trailing zeros. For example, if the version number ``74.0`` is not enclosed
    within quotes, then the version number is rendered as ``74``\.

The lines following the ``version`` are indented two more spaces and contain all
the information needed to install the Firefox package.

.. important::
    You can specify multiple versions of software by specifying multiple version
    numbers at the same indentation level as the first with its software
    definition below it.

.. important::
    The ``full_name`` must match exactly what is shown in Add/Remove Programs
    (``appwiz.cpl``)

.. _example-jinja:

Example: JINJA templated package definition file
================================================

JINJA is the default templating language used in package definition files. You
can use JINJA to add variables and expressions to package definition files that
get replaced with values when the ``.sls`` go through the Salt renderer.

When there are tens or hundreds of versions available for a piece of software,
the definition file can become large and cumbersome to maintain. In this
scenario, JINJA can be used to add logic, variables, and expressions to
automatically create the package definition file for software with multiple
versions.

Here is a an example of a package definition file for Firefox that uses JINJA:

.. code-block:: jinja

    {%- set lang = salt['config.get']('firefox:pkg:lang', 'en-US') %}

    firefox_x64:
      {% for version in ['74.0',
                         '73.0.1', '73.0',
                         '72.0.2', '72.0.1', '72.0',
                         '71.0', '70.0.1', '70.0',
                         '69.0.3', '69.0.2', '69.0.1'] %}
      '{{ version }}':
        full_name: 'Mozilla Firefox {{ version }} (x64 {{ lang }})'
        installer: 'https://download-installer.cdn.mozilla.net/pub/firefox/releases/{{ version }}/win64/{{ lang }}/Firefox%20Setup%20{{ version }}.exe'
        install_flags: '/S'
        uninstaller: '%ProgramFiles%\Mozilla Firefox\uninstall\helper.exe'
        uninstall_flags: '/S'
      {% endfor %}

In this example, JINJA is used to generate a package definition file that
defines how to install 12 versions of Firefox. Jinja is used to create a list of
available versions. The list is iterated through a ``for loop`` where each
version is placed in the ``version`` variable. The version is inserted
everywhere there is a ``{{ version }}`` marker inside the ``for loop``\.

The single variable (``lang``) defined at the top of the package definition
identifies the language of the package. You can access the Salt modules using
the ``salt`` keyword. In this case, the ``config.get`` function is invoked to
retrieve the language setting. If the ``lang`` variable is not defined then the
default value is ``en-US``\.

.. _example-latest:

Example: Package definition file to install the latest version
==============================================================

Some software vendors do not provide access to all versions of their software.
Instead, they provide a single URL to what is always the latest version. In some
cases, the software keeps itself up to date. One example of this is the `Google
Chrome web browser <https://dl.google.com/edgedl/chrome/install/GoogleChromeStandaloneEnterprise.msi>`_.

To handle situations such as these, set the version to `latest`. Here's an
example of a package definition file to install the latest version of Chrome.

.. code-block:: yaml

    chrome:
      latest:
        full_name: 'Google Chrome'
        installer: 'https://dl.google.com/edgedl/chrome/install/GoogleChromeStandaloneEnterprise.msi'
        install_flags: '/qn /norestart'
        uninstaller: 'https://dl.google.com/edgedl/chrome/install/GoogleChromeStandaloneEnterprise.msi'
        uninstall_flags: '/qn /norestart'
        msiexec: True

In the above example:

- ``Version`` is set to ``latest``\. Salt then installs the latest version of
  Chrome at the URL and displays that version.
- ``msiexec`` is set to ``True``\, hence the software is installed using an MSI.

.. _example-patch:

Example: Package definition file to install an MSI patch
========================================================

For MSI installers, when the ``msiexec`` parameter is set to true, the ``/i``
option is used for installation, and the ``/x`` option is used for
uninstallation. However, when installing an MSI patch, the ``/i`` and ``/x``
options cannot be combined.

Here is an example of a package definition file to install an MSI patch:

.. code-block:: yaml

    MyApp:
      '1.0':
        full_name: MyApp
        installer: 'salt://win/repo-ng/MyApp/MyApp.1.0.msi'
        install_flags: '/qn /norestart'
        uninstaller: '{B5B5868F-23BA-297A-917D-0DF345TF5764}'
        uninstall_flags: '/qn /norestart'
        msiexec: True
      '1.1':
        full_name: MyApp
        installer: 'salt://win/repo-ng/MyApp/MyApp.1.0.msi'
        install_flags: '/qn /norestart /update "%cd%\\MyApp.1.1.msp" '
        uninstaller: '{B5B5868F-23BA-297A-917D-0DF345TF5764}'
        uninstall_flags: '/qn /norestart'
        msiexec: True
        cache_file: salt://win/repo-ng/MyApp/MyApp.1.1.msp

In the above example:

- Version ``1.0`` of the software installs the application using the ``1.0``
  MSI defined in the ``installer`` parameter.
- There is no file to be cached and the ``install_flags`` parameter does not
  include any special values.

Version ``1.1`` of the software uses the same installer file as Version
``1.0``\. Now, to apply a patch to Version 1.0, make the following changes in
the package definition file:

- Place the patch file (MSP file) in the same directory as the installer file
  (MSI file) on the ``file_roots``
- In the ``cache_file`` parameter, specify the path to the single patch file.
- In the ``install_flags`` parameter, add the ``/update`` flag and include the
  path to the MSP file using the ``%cd%`` environment variable. ``%cd%``
  resolves to the current working directory, which is the location in the minion
  cache where the installer file is cached.

For more information, see issue `#32780 <https://github.com/saltstack/salt/issues/32780>`_.

The same approach could be used for applying MST files for MSIs and answer files
for other types of .exe-based installers.

.. _parameters:

Parameters
==========

This section describes the parameters placed under the ``version`` in the
package definition file. Examples can be found on the `Salt winrepo repository
<https://github.com/saltstack/salt-winrepo-ng>`_.

full_name (str)
---------------

The full name of the software as shown in "Add/Remove Programs". You can also
retrieve the full name of the package by installing the package manually and
then running ``pkg.list_pkgs``\. Here's an example of the output from
``pkg.list_pkgs``:

.. code-block:: bash

    salt 'test-2008' pkg.list_pkgs
    test-2008
        ----------
        7-Zip 9.20 (x64 edition):
            9.20.00.0
        Mozilla Firefox 74.0 (x64 en-US)
            74.0
        Mozilla Maintenance Service:
            74.0
        salt-minion-py3:
            3001

Notice the full Name for Firefox: ``Mozilla Firefox 74.0 (x64 en-US)``\. The
``full_name`` parameter in the package definition file must match this name.

The example below shows the ``pkg.list_pkgs`` for a machine that has Mozilla
Firefox 74.0 installed with a package definition file for that version of
Firefox.

.. code-block:: bash

    test-2008:
        ----------
        7zip:
            9.20.00.0
        Mozilla Maintenance Service:
            74.0
        firefox_x64:
            74.0
        salt-minion-py3:
            3001

On running ``pkg.list_pkgs``\, if any of the software installed on the machine
matches the full name defined in any one of the software definition files in the
repository, then the package name is displayed in the output.

.. important::
    The version number and ``full_name`` must match the output of
    ``pkg.list_pkgs`` so that the installation status can be verified by the
    state system.

.. note::
    You can successfully install packages using ``pkg.install``\, even if the
    ``full_name`` or the version number doesn't match. The module will complete
    successfully, but continue to display the full name in ``pkg.list_pkgs``\.
    If this is happening, verify that the ``full_name`` and the ``version``
    match exactly what is displayed in Add/Remove Programs.

.. tip::
    To force Salt to display the full name when there's already an existing
    package definition file on the system, you can pass a bogus ``saltenv``
    parameter to the command like so: ``pkg.list_pkgs saltenv=NotARealEnv``

.. tip::
    It's important use :mod:`pkg.refresh_db <salt.modules.win_pkg.refresh_db>`
    to check for errors and ensure the latest package definition is on any
    minion you're testing new definitions on.

installer (str)
---------------

The path to the binary (``.exe``\, ``.msi``) that installs the package.

This can be a local path or a URL. If it is a URL or a Salt path (``salt://``),
then the package is cached locally and then executed. If it is a path to a file
on disk or a file share, then it is executed directly.

.. note::
    When storing software in the same location as the winrepo:

    - Create a sub folder named after the package.
    - Store the package definition file named ``init.sls`` and the binary
      installer in the same sub folder if you are hosting those files on the
      ``file_roots``\.

.. note::
    The ``pkg.refresh_db`` command processes all ``.sls`` files in all sub
    directories in the ``winrepo_dir_ng`` directory.

install_flags (str)
-------------------

The flags passed to the installer for silent installation.

You may be able to find these flags by adding ``/?`` or ``/h`` when running the
installer from the command line. See `WPKG project wiki <https://wpkg.org/Category:Silent_Installers>`_ for information on silent install flags.

.. warning::
    Always ensure that the installer has the ability to install silently,
    otherwise Salt appears to hang while the installer waits for user input.

uninstaller (str)
-----------------

The path to the program to uninstall the software.

This can be the path to the same ``.exe`` or ``.msi`` used to install the
software. If you use a ``.msi`` to install the software, then you can either
use the GUID of the software or the same ``.msi`` to uninstall the software.

You can find the uninstall information in the registry:

- Software\\Microsoft\\Windows\\CurrentVersion\\Uninstall
- Software\\WOW6432Node\\Microsoft\\Windows\\CurrentVersion\\Uninstall

Here's an example that uses the GUID to uninstall software:

.. code-block:: yaml

    7zip:
      '9.20.00.0':
        full_name: 7-Zip 9.20 (x64 edition)
        installer: salt://win/repo-ng/7zip/7z920-x64.msi
        install_flags: '/qn /norestart'
        uninstaller: '{23170F69-40C1-2702-0920-000001000000}'
        uninstall_flags: '/qn /norestart'
        msiexec: True

Here's an example that uses the MSI installer to uninstall software:

.. code-block:: yaml

    7zip:
      '9.20.00.0':
        full_name: 7-Zip 9.20 (x64 edition)
        installer: salt://win/repo-ng/7zip/7z920-x64.msi
        install_flags: '/qn /norestart'
        uninstaller: salt://win/repo-ng/7zip/7z920-x64.msi
        uninstall_flags: '/qn /norestart'
        msiexec: True

uninstall_flags (str)
---------------------

The flags passed to the uninstaller for silent uninstallation.

You may be able to find these flags by adding ``/?`` or ``/h`` when running the
uninstaller from the command-line. See `WPKG project wiki <https://wpkg.org/Category:Silent_Installers>`_ for information on silent uninstall flags.

.. warning::
    Always ensure that the installer has the ability to uninstall silently,
    otherwise Salt appears to hang while the uninstaller waits for user input.

msiexec (bool, str)
-------------------

This setting informs Salt to use ``msiexec /i`` to install the package and ``msiexec /x``
to uninstall. This setting only applies to ``.msi`` installations.

Possible options are:

- True
- False (default)
- the path to ``msiexec.exe`` on your system

.. code-block:: yaml

    7zip:
      '9.20.00.0':
        full_name: 7-Zip 9.20 (x64 edition)
        installer: salt://win/repo/7zip/7z920-x64.msi
        install_flags: '/qn /norestart'
        uninstaller: salt://win/repo/7zip/7z920-x64.msi
        uninstall_flags: '/qn /norestart'
        msiexec: 'C:\Windows\System32\msiexec.exe'

allusers (bool)
---------------

This parameter is specific to ``.msi`` installations. It tells ``msiexec`` to
install the software for all users. The default is ``True``\.

cache_dir (bool)
----------------

This setting requires the software to be stored on the ``file_roots`` and only
applies to URLs that begin with ``salt://``\. If set to ``True``\, then the
entire directory where the installer resides is recursively cached. This is
useful for installers that depend on other files in the same directory for
installation.

.. warning::
    If set to ``True``\, then all files and directories in the same location as
    the installer file are copied down to the minion. For example, if you place
    your package definition file with ``cache_dir: True`` in the root of winrepo
    (``/srv/salt/win/repo-ng``) then the entire contents of winrepo is cached to
    the minion. Therefore, it is best practice to place your package definition
    file along with its installer files in a subdirectory if they are stored in
    winrepo.

Here's an example using cache_dir:

.. code-block:: yaml

    sqlexpress:
      '12.0.2000.8':
        full_name: Microsoft SQL Server 2014 Setup (English)
        installer: 'salt://win/repo/sqlexpress/setup.exe'
        install_flags: '/ACTION=install /IACCEPTSQLSERVERLICENSETERMS /Q'
        cache_dir: True

cache_file (str)
----------------

This setting requires the file to be stored on the ``file_roots`` and only
applies to URLs that begin with ``salt://``\. It indicates that the single file
specified is copied down for use with the installer. It is copied to the same
location as the installer. Use this setting instead of ``cache_dir`` when you
only need to cache a single file.

use_scheduler (bool)
--------------------

If set to ``True``\, Windows uses the task scheduler to run the installation. A
one-time task is created in the task scheduler and launched. The return to the
minion is that the task was launched successfully, not that the software was
installed successfully.

.. note::
    This is used in the package definition for Salt itself. The first thing the
    Salt installer does is kill the Salt service, which then kills all child
    processes. If the Salt installer is launched via Salt, then the installer
    is killed with the salt-minion service, leaving Salt on the machine but not
    running. Using the task scheduler allows an external process to launch the
    Salt installer so its processes aren't killed when the Salt service is
    stopped.

source_hash (str)
-----------------

This setting informs Salt to compare a hash sum of the installer to the provided
hash sum before execution. The value can be formatted as ``<hash_algorithm>=<hash_sum>``\,
or it can be a URI to a file containing the hash sum.

For a list of supported algorithms, see the `hashlib documentation
<https://docs.python.org/3/library/hashlib.html>`_.

Here's an example using ``source_hash``:

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

Not Implemented
---------------
The following parameters are often seen in the software definition files hosted
on the Git repo. However, they are not implemented and do not affect the
installation process.

:param bool reboot: Not implemented

:param str locale: Not implemented

.. _standalone-winrepo:

Managing Windows Software on a Standalone Windows Minion
********************************************************

The Windows Software Repository functions similarly in a standalone environment,
with a few differences in the configuration.

To replace the winrepo runner used on the Salt master, an :mod:`execution module
<salt.modules.win_repo>` exists to provide the same functionality to standalone
minions. The functions for the module share the same names with functions in the
runner and are used in the same way; the only difference is that ``salt-call``
is used instead of ``salt-run`` to run those functions:

.. code-block:: bash

    salt-call winrepo.update_git_repos
    salt-call pkg.refresh_db

After executing the previous commands, the repository on the standalone system
is ready for use.

.. _winrepo-troubleshooting:

Troubleshooting
***************

My software installs correctly but ``pkg.installed`` says it failed
===================================================================

If you have a package that seems to install properly but Salt reports a failure
then it is likely you have a ``version`` or ``full_name`` mismatch.

- Check the ``full_name`` and ``version`` of the package as shown in Add/Remove
  Programs (``appwiz.cpl``).
- Use ``pkg.list_pkgs`` to check that the ``full_name`` and ``version`` exactly
  match what is installed.
- Verify that the ``full_name`` and ``version`` in the package definition file
  match the full name and version in Add/Remove programs.
- Ensure that the ``version`` is wrapped in single quotes in the package
  definition file.

Changes to package definition files not being picked up
=======================================================

Make sure you refresh the database on the minion (``pkg.refresh_db``) after
updating package definition files in the repo.

.. code-block:: bash

    salt winminion pkg.refresh_db

Winrepo upgrade issues
======================

To minimize potential issues, it is a good idea to remove any winrepo git
repositories that were checked out by the legacy (pre-2015.8.0) winrepo code
when upgrading the master to 2015.8.0 or later. Run :mod:`winrepo.update_git_repos
<salt.runners.winrepo.update_git_repos>` to clone them anew after the master is
started.

pygit2 / GitPython Support for Maintaining Git Repos
****************************************************

pygit2 and GitPython are the supported python interfaces to Git. The runner
:mod:`winrepo.update_git_repos <salt.runners.winrepo.update_git_repos>` uses the
same underlying code as :ref:`Git Fileserver Backend <tutorial-gitfs>` and
:mod:`Git External Pillar <salt.pillar.git_pillar>` to maintain and update its
local clones of git repositories.

.. note::
    If compatible versions of both pygit2 and GitPython are installed, then
    Salt will prefer pygit2. To override this behavior use the
    :conf_master:`winrepo_provider` configuration parameter, ie:
    ``winrepo_provider: gitpython``

.. _authenticated-pygit2:

Accessing authenticated Git repos (pygit2)
******************************************

pygit2 enables you to access authenticated git repositories and set per-remote
config settings. An example of this is:

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
    The per-remote configuration settings work in the same manner as they do in
    gitfs, with global parameters being overridden by their per-remote
    counterparts. For instance, setting :conf_master:`winrepo_passphrase`
    sets a global passphrase for winrepo that applies to all SSH-based
    remotes, unless overridden by a ``passphrase`` per-remote parameter.

    See :ref:`here <gitfs-per-remote-config>` for a detailed
    explanation of how per-remote configuration works in gitfs. The same
    principles apply to winrepo.

.. _maintaining-repo:

Maintaining Git repos
*********************

A ``clean`` argument is added to the
:mod:`winrepo.update_git_repos <salt.runners.winrepo.update_git_repos>`
runner to maintain the Git repos. When ``clean=True`` the runner removes
directories under the :conf_master:`winrepo_dir_ng`/:conf_minion:`winrepo_dir_ng`
that are not explicitly configured. This eliminates the need to manually remove
these directories when a repo is removed from the config file.

.. code-block:: bash

    salt-run winrepo.update_git_repos clean=True

If a mix of git and non-git Windows Repo definition files are used, then
do not pass ``clean=True``\, as it removes the directories containing non-git
definitions.

.. _name-collisions:

Name collisions between repos
*****************************

Salt detects collisions between repository names. The
:mod:`winrepo.update_git_repos <salt.runners.winrepo.update_git_repos>`
runner does not execute successfully if any collisions between repository names
are detected. Consider the following configuration:

.. code-block:: yaml

    winrepo_remotes:
      - https://foo.com/bar/baz.git
      - https://mydomain.tld/baz.git
      - https://github.com/foobar/baz.git

With the above configuration, the :mod:`winrepo.update_git_repos <salt.runners.winrepo.update_git_repos>`
runner fails to execute as all three repos would be checked out to the same
directory. To resolve this conflict, use the per-remote parameter called
``name``\.

.. code-block:: yaml

    winrepo_remotes:
      - https://foo.com/bar/baz.git
      - https://mydomain.tld/baz.git:
        - name: baz_junior
      - https://github.com/foobar/baz.git:
        - name: baz_the_third

Now on running the :mod:`winrepo.update_git_repos <salt.runners.winrepo.update_git_repos>`:

- https://foo.com/bar/baz.git repo is initialized and cloned under the ``win_repo_dir_ng`` directory.
- https://mydomain.tld/baz.git repo is initialized and cloned under the ``win_repo_dir_ng\baz_junior`` directory.
- https://github.com/foobar/baz.git repo is initialized and cloned under the ``win_repo_dir_ng\baz_the_third`` directory.
