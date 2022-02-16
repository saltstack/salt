.. _windows-package-manager:

#######################
Windows Package Manager
#######################

Introduction
************

The Windows Package Manager provides a software repository and a package manager
similar to what is provided by ``yum`` and ``apt`` on Linux. This tool enables
the installation of software on remote Windows systems.

The repository contains a collection of software definition files. A software
definition file is a YAML/JINJA file with an ``.sls`` file extension. It
contains all the information Salt needs to install a software package on a
Windows system, including the download location of the installer, required
command-line switches for silent install, etc.

Software definition files can be hosted in one or more Git repositories. The
default repository is hosted on GitHub by SaltStack. It is maintained by
SaltStack and the Salt community and contains software definition files for many
common Windows packages.  Anyone is welcome to submit a pull request to this
repo to add new software definitions. The default github repository is:

- `salt-winrepo-ng <https://github.com/saltstack/salt-winrepo-ng>`_

The Windows Package Manager is used the same way as other package managers Salt
is aware of. For example:

- the ``pkg.installed`` and similar states work on Windows.
- the ``pkg.install`` and similar module functions work on Windows.

High level differences to ``yum`` and ``apt`` are:

- The repository metadata (SLS files) can be managed through either Salt or git
- Packages can be downloaded from within the Salt repository, a git repository
  or from HTTP(S) or FTP URLs
- No dependencies are managed. Dependencies between packages need to be managed
  manually

Requirements
============

If using the a software definition files hosted on a Git repo, the following
libraries are required:

- GitPython 0.3 or later

  or

- pygit2 0.20.3 with libgit 0.20.0 or later

Quick Start
***********

You can get up and running with winrepo pretty quickly just using the defaults.
Assuming no changes to the default configuration (ie, ``file_roots``) run the
following commands on the master:

.. code-block:: bash

    salt-run winrepo.update_git_repos
    salt * pkg.refresh_db
    salt * pkg.install firefox_x64

On a masterless minion run the following:

.. code-block:: bash

    salt-call --local winrepo.update_git_repos
    salt-call --local pkg.refresh_db
    salt-call --local pkg.install firefox_x64

These commands clone the default winrepo from github, update the winrepo
database on the minion, and install the latest version of Firefox.

Configuration
*************

The Github repository (winrepo) is synced to the ``file_roots`` in a location
specified by the ``winrepo_dir_ng`` setting in the config. The default value of
``winrepo_dir_ng`` is as follows:

- Linux master: ``/srv/salt/win/repo-ng`` (``salt://win/repo-ng``)
- Masterless minion: ``C:\salt\srv\salt\win\repo-ng`` (``salt://win/repo-ng``)

Master Configuration
====================

The following are settings are available for configuring the winrepo on the
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
is ``/srv/salt/win/repo-ng``.

.. warning::
    You can change the location of the winrepo directory. However, it must
    always be set to a path that is inside the ``file_roots``.
    Otherwise the software definition files will be unreachable by the minion.

.. important::
    A common mistake is to change the ``file_roots`` setting and fail to update
    the ``winrepo_dir_ng`` and ``winrepo_dir`` settings so that they are inside
    the ``file_roots``

winrepo_remotes
---------------

:conf_master:`winrepo_remotes` (list)

This setting is maintained for backwards compatibility with legacy minions. It
points to the legacy git repo. The default is a list containing a single URL:

`https://github.com/saltstack/salt-winrepo
<https://github.com/saltstack/salt-winrepo>`_

The legacy repo can be disabled by setting it to an empty list in the master
config.

.. code-block:: bash

    winrepo_remotes: []

winrepo_remotes_ng
------------------

:conf_master:`winrepo_remotes_ng` (list)

This setting tells the ``winrepo.upgate_git_repos`` command where the next
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

The provider to be used for winrepo. Default is ``pygit2``. Falls back to
``gitpython`` when ``pygit2`` is not available

winrepo_ssl_verify
------------------

:conf_master:`winrepo_ssl_verify` (bool)

Ignore SSL certificate errors when contacting remote repository. Default is
``False``

Master Configuration (pygit2)
=============================

The following configuration options only apply when the
:conf_master:`winrepo_provider` option is set to ``pygit2``.

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
becoming stale. If the metadata file is older than this setting it will trigger
a ``pkg.refresh_db`` on the next run of any ``pkg`` module function that
requires the metadata file. Default is 604800 (1 week).

Software package definitions are automatically refreshed if stale after
:conf_minion:`winrepo_cache_expire_max`.  Running a highstate normal forces the
refresh of the package definition and generation of the metadata, unless
the metadata is younger than :conf_minion:`winrepo_cache_expire_max`.

winrepo_cache_expire_min
------------------------

:conf_minion:`winrepo_cache_expire_min` (int)

Sets the minimum age in seconds of the winrepo metadata file to avoid refreshing
too often. If the metadata file is older than this setting the metadata will be
refreshed unless you pass ``refresh: False`` in the state. Default is 1800
(30 min).

winrepo_cachefile
-----------------

:conf_minion:`winrepo_cachefile` (str)

The file name of the winrepo cache file. The file is placed at the root of
``winrepo_dir_ng``. Default is ``winrepo.p``.

winrepo_source_dir
------------------

:conf_minion:`winrepo_source_dir` (str)

The location of the .sls files on the Salt file server. This allows for using
different environments. Default is ``salt://win/repo-ng/``.

.. warning::
    If the default for ``winrepo_dir_ng`` is changed, this setting may need to
    changed on each minion. The default setting for ``winrepo_dir_ng`` is
    ``/srv/salt/win/repo-ng``. If that were changed to ``/srv/salt/new/repo-ng``
    then the ``winrepo_source_dir`` would need to be changed to
    ``salt://new/repo-ng``

Masterless Minion Configuration
===============================

The following are settings are available for configuring the winrepo on a
masterless minion:

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
The default is: ``C:\salt\srv\salt\win\repo``

winrepo_dir_ng
--------------

:conf_minion:`winrepo_dir_ng` (str)

The location in the ``file_roots where the winrepo files are kept. The default
is ``C:\salt\srv\salt\win\repo-ng``.

.. warning::
    You can change the location of the winrepo directory. However, it must
    always be set to a path that is inside the ``file_roots``.
    Otherwise the software definition files will be unreachable by the minion.

.. important::
    A common mistake is to change the ``file_roots`` setting and fail to update
    the ``winrepo_dir_ng`` and ``winrepo_dir`` settings so that they are inside
    the ``file_roots``. You might also want to verify ``winrepo_source_dir`` on
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

This setting tells the ``winrepo.upgate_git_repos`` command where the next
generation winrepo is hosted. This a list of URLs to multiple git repos. The
default is a list containing a single URL:

`https://github.com/saltstack/salt-winrepo-ng
<https://github.com/saltstack/salt-winrepo-ng>`_

Initialization
**************

Populate the Local Repository
=============================

The SLS files used to install Windows packages are not distributed by default
with Salt. Use the :mod:`winrepo.update_git_repos <salt.runners.winrepo.update_git_repos>`
runner initialize the repository in the location specified by ``winrepo_dir_ng``
in the master config. This will pull the software definition files down from the
git repository.

.. code-block:: bash

    salt-run winrepo.update_git_repos

If running a minion in masterless mode, the same command can be run using
``salt-call``. The repository will be initialized in the location specified by
``winrepo_dir_ng`` in the minion config.

.. code-block:: bash

    salt-call --local winrepo.update_git_repos

These commands will also sync down the legacy repo to maintain backwards
compatibility with legacy minions. See :ref:`Legacy Minions <legacy-minions>`

The legacy repo can be disabled by setting it to an empty list in the master or
minion config.

.. code-block:: bash

    winrepo_remotes: []

Generate the Metadata File (Legacy)
===================================

This step is only required if you are supporting legacy minions. In current
usage the metadata file is generated on the minion in the next step, Update
the Minion Database. For legacy minions the metadata file is generated on the
master using the :mod:`winrepo.genrepo <salt.runners.winrepo.genrepo>` runner.

.. code-block:: bash

    salt-run winrepo.genrepo

Update the Minion Database
==========================

Run :mod:`pkg.refresh_db <salt.modules.win_pkg.refresh_db>` on each of your
Windows minions to synchronize the package repository to the minion and build
the package database.

.. code-block:: bash

    # From the master
    salt -G 'os:windows' pkg.refresh_db

    # From the minion in masterless mode
    salt-call --local pkg.refresh_db

The above command returns the following summary denoting the number of packages
that succeeded or failed to compile:

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
    This command can take a few minutes to complete as the software definition
    files are copied to the minion and the database is generated.

.. note::
    Use ``pkg.refresh_db`` when developing new Windows package definitions to
    check for errors in the definitions against one or more Windows minions.

Usage
*****

After completing the configuration and initialization steps, you are ready to
manage software on your Windows minions.

.. note::
    The following example commands can be run from the master using ``salt`` or
    on a masterless minion using ``salt-call``

List Installed Packages
=======================

You can get a list of packages installed on the system using
:mod:`pkg.list_pkgs <salt.modules.win_pkg.list_pkgs>`.

.. code-block:: bash

    # From the master
    salt -G 'os:windows' pkg.list_pkgs

    # From the minion in masterless mode
    salt-call --local pkg.list_pkgs

This will return all software installed on the system whether it is managed by
Salt or not as shown below:

.. code-block:: console

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

You can tell by how the software name is displayed which software is managed by
Salt and which software is not. When Salt finds a match in the winrepo database
it displays the short name as defined in the software definition file. It is
usually a single-word, lower-case name. All other software names will be
displayed with the full name as they are shown in Add/Remove Programs. So, in
the return above, you can see that Git (git), Nullsoft Installer (nsis), Python
3.7 (python3_x64) and Salt (salt-minion-py3) all have a corresponding software
definition file. The others do not.

List Available Versions
=======================

You can query the available version of a package using
:mod:`pkg.list_available <salt.modules.win_pkg.list_available>` and passing the
name of the software:

.. code-block:: bash

    # From the master
    salt winminion pkg.list_available firefox_x64

    # From the minion in masterless mode
    salt-call --local pkg.list_available firefox_x64

The above command will return the following:

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

As you can see, there are many versions of Firefox available for installation.
You can refer to a software package by its ``name`` or its ``full_name``
surrounded by quotes.

.. note::
    From a Linux master it is OK to use single-quotes. However, the ``cmd``
    shell on Windows requires you to use double-quotes when wrapping strings
    that may contain spaces. Powershell seems to accept either one.

Install a Package
=================

You can install a package using :mod:`pkg.install <salt.modules.win_pkg.install>`:

.. code-block:: bash

    # From the master
    salt winminion pkg.install 'firefox_x64'

    # From the minion in masterless mode
    salt-call --local pkg.install "firefox_x64"

The above will install the latest version of Firefox.

.. code-block:: bash

    # From the master
    salt winminion pkg.install 'firefox_x64' version=74.0

    # From the minion in masterless mode
    salt-call --local pkg.install "firefox_x64" version=74.0

The above will install version 74.0 of Firefox.

If a different version of the package is already installed it will be replaced
with the version in the winrepo (only if the package itself supports live
updating).

You can also specify the full name:

.. code-block:: bash

    # From the master
    salt winminion pkg.install 'Mozilla Firefox 17.0.1 (x86 en-US)'

    # From the minion in masterless mode
    salt-call --local pkg.install "Mozilla Firefox 17.0.1 (x86 en-US)"

Remove a Package
================

You can uninstall a package using :mod:`pkg.remove <salt.modules.win_pkg.remove>`:

.. code-block:: bash

    # From the master
    salt winminion pkg.remove firefox_x64

    # From the minion in masterless mode
    salt-call --local pkg.remove firefox_x64

.. _software-definition-files:

Software Definition Files
*************************

A software definition file is a YAML/JINJA2 file that contains all the
information needed to install a piece of software using Salt. It defines
information about the package to include version, full name, flags required for
the installer and uninstaller, whether or not to use the Windows task scheduler
to install the package, where to download the installation package, etc.

Directory Structure and Naming
==============================

The files are stored in the location designated by the ``winrepo_dir_ng``
setting. All files in this directory that have a ``.sls`` file extension are
considered software definition files. The files are evaluated to create the
metadata file on the minion.

You can maintain standalone software definition files that point to software on
other servers or on the internet. In this case the file name would be the short
name of the software with the ``.sls`` extension, ie ``firefox.sls``.

You can also store the binaries for your software together with their software
definition files in their own directory. In this scenario, the directory name
would be the short name for the software and the software definition file would
be inside that directory and named ``init.sls``.

Look at the following example directory structure on a Linux master assuming
default config settings:

.. code-block:: console

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

In the above directory structure, the user has created the ``custom_defs``
directory in which to store their custom software definition files. In that
directory you see a folder for MS Office 2013 that contains all the installer
files along with a software definition file named ``init.sls``. The user has
also created two more standalone software definition files; ``openssl.sls`` and
``zoom.sls``.

The ``salt-winrepo-ng`` directory is created by the ``winrepo.update_git_repos``
command. This folder contains the clone of the git repo designated by the
``winrepo_remotes_ng`` config setting.

.. warning::
    It is recommended that the user not modify the files in the
    ``salt-winrepo-ng`` directory as it will break future runs of
    ``winrepo.update_git_repos``.

.. warning::
    It is recommended that the user not place any custom software definition
    files in the ``salt-winrepo-ng`` directory. The ``winrepo.update_git_repos``
    command wipes out the contents of the ``salt-winrepo-ng`` directory each
    time it is run. Any extra files stored there will be lost.

Writing Software Definition Files
=================================

A basic software definition file is really easy to write if you already know
some basic things about your software:

- The full name as shown in Add/Remove Programs
- The exact version number as shown in Add/Remove Programs
- How to install your software silently from the command line

The software definition file itself is just a data structure written in YAML.
The top level item is a short name that Salt will use to reference the software.
There can be only one short name in the file and it must be unique across all
software definition files in the repo. This is the name that will be used to
install/remove the software. It is also the name that will appear when Salt
finds a match in the repo when running ``pkg.list_pkgs``.

The next indentation level is the version number. There can be many of these,
but they must be unique within the file. This is also displayed in
``pkg.list_pkgs``.

The last indentation level contains the information Salt needs to actually
install the software. Available parameters are:

- ``full_name`` : The full name as displayed in Add/Remove Programs
- ``installer`` : The location of the installer binary
- ``install_flags`` : The flags required to install silently
- ``uninstaller`` : The location of the uninstaller binary
- ``uninstall_flags`` : The flags required to uninstall silently
- ``msiexec`` : Use msiexec to install this package
- ``allusers`` : If this is an MSI, install to all users
- ``cache_dir`` : Cache the entire directory in the installer URL if it starts with ``salt://``
- ``cache_file`` : Cache a single file in the installer URL if it starts with ``salt://``
- ``use_scheduler`` : Launch the installer using the task scheduler
- ``source_hash`` : The hash sum for the installer

Usage of these parameters is demonstrated in the following examples and
discussed in more detail below. To understand these examples you'll need a basic
understanding of Jinja. The following links have some basic tips and best
practices for working with Jinja in Salt:

`Understanding Jinja <https://docs.saltproject.io/en/latest/topics/jinja/index.html>`_

`Jinja <https://docs.saltproject.io/en/getstarted/config/jinja.html>`_

Example: Basic
==============

Take a look at this basic, pure YAML example for a software definition file for
Firefox:

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

You can see the first item is the short name for the software, in this case
``firefox_x64``. It is the first line in the definition. The next line is
indented two spaces and contains the software ``version``. The lines following
the ``version`` are indented two more spaces and contain all the information
needed to install the Firefox package.

.. important::
    The package name must be unique to all other packages in the software
    repository. The ``full_name`` combined with the version must also be unique.
    They must also match exactly what is shown in Add/Remove Programs
    (``appwiz.cpl``).

.. important::
    The version number must be enclosed in quotes, otherwise the YAML parser
    will remove trailing zeros. For example, `74.0` will just become `74`.

As you can see in the example above, a software definition file can define
multiple versions for the same piece of software. These are denoted by putting
the next version number at the same indentation level as the first with its
software definition information indented below it.

Example: Jinja
==============

When there are tens or hundreds of versions available for a piece of software
definition file can become quite large. This is a scenario where Jinja can be
helpful. Consider the following software definition file for Firefox using
Jinja:

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

In this example we are able to generate a software definition file that defines
how to install 12 versions of Firefox. We use Jinja to create a list of
available versions. That list is in a ``for loop`` where each version is placed
in the ``version`` variable. The version is inserted everywhere there is a
``{{ version }}`` marker inside the ``for loop``.

You'll notice that there is a single variable (``lang``) defined at the top of
the software definition. Because these files are going through the Salt renderer
many Salt modules are exposed via the ``salt`` keyword. In this case it is
calling the ``config.get`` function to get a language setting that can be placed
in the minion config. If it is not there, it defaults to ``en-US``.

Example: Latest
===============

There are some software vendors that do not provide access to all versions of
their software. Instead they provide a single URL to what is always the latest
version. In some cases the software keeps itself up to date. One example of this
is the Google Chrome web browser.

`Chrome <https://dl.google.com/edgedl/chrome/install/GoogleChromeStandaloneEnterprise.msi>`_

To handle situations such as these, set the version to `latest`. Here's an
example:

.. code-block:: yaml

    chrome:
      latest:
        full_name: 'Google Chrome'
        installer: 'https://dl.google.com/edgedl/chrome/install/GoogleChromeStandaloneEnterprise.msi'
        install_flags: '/qn /norestart'
        uninstaller: 'https://dl.google.com/edgedl/chrome/install/GoogleChromeStandaloneEnterprise.msi'
        uninstall_flags: '/qn /norestart'
        msiexec: True

The above example shows us two things. First it demonstrates the usage of
``latest`` as the version. In this case Salt will install the version of Chrome
at the URL and report that version.

The second thing to note is that this is installing software using an MSI. You
can see that ``msiexec`` is set to ``True``.

Example: MSI Patch
==================

When the ``msiexec`` parameter is set to ``True`` it uses the ``/i`` option for
installs and the ``/x`` option for uninstalls. This is problematic when trying
to install an MSI patch which requires the ``/p`` option. You can't combine the
``/i`` and ``/p`` options. So how do you apply a patch to installed software in
winrepo using an ``.msp`` file?

One wiley contributor came up with the following solution to this problem by
using the ``%cd%`` environment variable. Consider the following software
definition file:

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
        cache_file: salt://win/repo/MyApp/MyApp.1.1.msp

There are a few things to note about this software definition file. First, is
the solution we are trying to solve, that of applying a patch. Version ``1.0``
just installs the application using the ``1.0`` MSI defined in the ``installer``
parameter. There is nothing special in the ``install_flags`` and nothing is
cached.

Version ``1.1`` uses the same installer, but uses the ``cache_file`` option to
specify a single file to cache. In order for this to work the MSP file needs to
be in the same directory as the MSI file on the ``file_roots``.

The final step to getting this to work is to add the additional ``/update`` flag
to the ``install_flags`` parameter. Add the path to the MSP file using the
``%cd%`` environment variable. ``%cd%`` resolves to the current working
directory which is the location in the minion cache where the installer file is
cached.

See issue `#32780 <https://github.com/saltstack/salt/issues/32780>`_ for more
details.

This same approach could be used for applying MST files for MSIs and answer
files for other types of .exe based installers.

Parameters
==========

These are the parameters that can be used to generate a software definition
file. These parameters are all placed under the ``version`` in the software
definition file:

Example usage can be found on the `github repo
<https://github.com/saltstack/salt-winrepo-ng>`_

full_name (str)
---------------

This is the full name for the software as shown in "Programs and Features" in
the control panel. You can also get this information by installing the package
manually and then running ``pkg.list_pkgs``. Here's an example of the output
from ``pkg.list_pkgs``:

.. code-block:: console

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

Notice the Full Name for Firefox: ``Mozilla Firefox 74.0 (x64 en-US)``. That's
exactly what should be in the ``full_name`` parameter in the software definition
file.

If any of the software installed on the machine matches the full name defined in
one of the software definition files in the repository the package name will be
returned. The example below shows the ``pkg.list_pkgs`` for a machine that has
Mozilla Firefox 74.0 installed and a software definition for that version of
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

.. important::
    The version number and ``full_name`` need to match the output from
    ``pkg.list_pkgs`` exactly so that the installation status can be verified
    by the state system.

.. note::
    It is still possible to successfully install packages using ``pkg.install``,
    even if the ``full_name`` or the version number don't match exactly. The
    module will complete successfully, but continue to display the full name
    in ``pkg.list_pkgs``. If this is happening, verify that the ``full_name``
    and the ``version`` match exactly what is displayed in Add/Remove
    Programs.

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

This is the path to the binary (``.exe``, ``.msi``) that will install the
package. This can be a local path or a URL. If it is a URL or a Salt path
(``salt://``), the package will be cached locally and then executed. If it is a
path to a file on disk or a file share, it will be executed directly.

.. note::
    When storing software in the same location as the winrepo it is usually best
    practice to place each installer in its own directory rather than in the
    root of winrepo.

    Best practice is to create a sub folder named after the package. That folder
    will contain the software definition file named ``init.sls``. The binary
    installer should be stored in that directory as well if you're hosting those
    files on the file_roots.

    ``pkg.refresh_db`` will process all ``.sls`` files in all sub directories
    in the ``winrepo_dir_ng`` directory.

install_flags (str)
-------------------

This setting contains any flags that need to be passed to the installer to make
it perform a silent install. These can often be found by adding ``/?`` or ``/h``
when running the installer from the command-line. A great resource for finding
these silent install flags is the WPKG project wiki_:

.. warning::
    Salt will appear to hang if the installer is expecting user input. So it is
    imperative that the software have the ability to install silently.

uninstaller (str)
-----------------

This is the path to the program used to uninstall this software. This can be the
path to the same ``exe`` or ``msi`` used to install the software. Exe
uninstallers are pretty straight forward. MSIs, on the other hand, can be
handled a couple different ways. You can use the GUID for the software to
uninstall or you can use the same MSI used to install the software.

You can usually find uninstall information in the registry:

- Software\\Microsoft\\Windows\\CurrentVersion\\Uninstall
- Software\\WOW6432Node\\Microsoft\\Windows\\CurrentVersion\\Uninstall

Here's an example using the GUID to uninstall software.

.. code-block:: yaml

    7zip:
      '9.20.00.0':
        full_name: 7-Zip 9.20 (x64 edition)
        installer: salt://win/repo-ng/7zip/7z920-x64.msi
        install_flags: '/qn /norestart'
        uninstaller: '{23170F69-40C1-2702-0920-000001000000}'
        uninstall_flags: '/qn /norestart'
        msiexec: True

Here's an example using the same MSI used to install the software:

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

This setting contains any flags that need to be passed to the uninstaller to
make it perform a silent uninstall. These can often be found by adding ``/?`` or
``/h`` when running the uninstaller from the command-line. A great resource for
finding these silent install flags the WPKG project wiki_:

.. warning::
    Salt will appear to hang if the uninstaller is expecting user input. So it
    is imperative that the software have the ability to uninstall silently.

msiexec (bool, str)
-------------------

This tells Salt to use ``msiexec /i`` to install the package and ``msiexec /x``
to uninstall. This is for ``.msi`` installations only.

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
install the software for all users. The default is ``True``.

cache_dir (bool)
----------------

This setting requires the software to be stored on the ``file_roots`` and only
applies to URLs that begin with ``salt://``. If ``True`` the entire directory
where the installer resides will be recursively cached. This is useful for
installers that depend on other files in the same directory for installation.

.. warning::
    Be aware that all files and directories in the same location as the
    installer file will be copied down to the minion. If you place your
    software definition file in the root of winrepo (``/srv/salt/win/repo-ng``)
    and it contains ``cache_dir: True`` the entire contents of winrepo will be
    cached to the minion. Therefore, it is best practice to place your installer
    files in a subdirectory if they are to be stored in winrepo.

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
applies to URLs that begin with ``salt://``. It indicates a single file to copy
down for use with the installer. It is copied to the same location as the
installer. Use this over ``cache_dir`` if there are many files in the directory
and you only need a specific file and don't want to cache additional files that
may reside in the installer directory.

use_scheduler (bool)
--------------------

If set to ``True``, Windows will use the task scheduler to run the installation.
A one-time task will be created in the task scheduler and launched. The return
to the minion will be that the task was launched successfully, not that the
software was installed successfully.

.. note::
    This is used by the software definition for Salt itself. The first thing the
    Salt installer does is kill the Salt service, which then kills all child
    processes. If the Salt installer is launched via Salt, then the installer
    itself is killed leaving Salt on the machine but not running. Use of the
    task scheduler allows an external process to launch the Salt installation so
    its processes aren't killed when the Salt service is stopped.

source_hash (str)
-----------------

This tells Salt to compare a hash sum of the installer to the provided hash sum
before execution. The value can be formatted as ``<hash_algorithm>=<hash_sum>``,
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
on the Git repo. However, they are not implemented and have no effect on the
installation process.

:param bool reboot: Not implemented

:param str locale: Not implemented

.. _standalone-winrepo:

Managing Windows Software on a Standalone Windows Minion
********************************************************

The Windows Software Repository functions similarly in a standalone environment,
with a few differences in the configuration.

To replace the winrepo runner that is used on the Salt master, an
:mod:`execution module <salt.modules.win_repo>` exists to provide the same
functionality to standalone minions. The functions are named the same as the
ones in the runner, and are used in the same way; the only difference is that
``salt-call`` is used instead of ``salt-run``:

.. code-block:: bash

    salt-call winrepo.update_git_repos
    salt-call pkg.refresh_db

After executing the previous commands the repository on the standalone system is
ready for use.

.. _winrepo-troubleshooting:

Troubleshooting
***************

My software installs correctly but pkg.installed says it failed
===============================================================

If you have a package that seems to install properly, but Salt reports a failure
then it is likely you have a ``version`` or ``full_name`` mismatch.

Check the exact ``full_name`` and ``version`` as shown in Add/Remove Programs
(``appwiz.cpl``). Use ``pkg.list_pkgs`` to check that the ``full_name`` and
``version`` exactly match what is installed. Make sure the software definition
file has the exact value for ``full_name`` and that the version matches exactly.

Also, make sure the version is wrapped in single quotes in the software
definition file.

Changes to sls files not being picked up
========================================

You may have recently updated some of the software definition files on the repo.
Ensure you have refreshed the database on the minion.

.. code-block:: bash

    salt winminion pkg.refresh_db

How Success and Failure are Reported by pkg.installed
=====================================================

The install state/module function of the Windows package manager works roughly
as follows:

1. Execute ``pkg.list_pkgs`` to get a list of software currently on the machine
2. Compare the requested version with the installed version
3. If versions are the same, report no changes needed
4. Install the software as described in the software definition file
5. Execute ``pkg.list_pkgs`` to get a new list of software currently on the
   machine
6. Compare the requested version with the new installed version
7. If versions are the same, report success
8. If versions are different, report failure

Winrepo Upgrade Issues
======================

To minimize potential issues, it is a good idea to remove any winrepo git
repositories that were checked out by the legacy (pre-2015.8.0) winrepo code
when upgrading the master to 2015.8.0 or later. Run
:mod:`winrepo.update_git_repos <salt.runners.winrepo.update_git_repos>` to
clone them anew after the master is started.

pygit2_/GitPython_ Support for Maintaining Git Repos
****************************************************

The :mod:`winrepo.update_git_repos <salt.runners.winrepo.update_git_repos>`
runner now makes use of the same underlying code used by the :ref:`Git Fileserver Backend <tutorial-gitfs>`
and :mod:`Git External Pillar <salt.pillar.git_pillar>` to maintain and update
its local clones of git repositories. If a compatible version of either pygit2_
(0.20.3 and later) or GitPython_ (0.3.0 or later) is installed, Salt will use it
instead of the old method (which invokes the :mod:`git.latest <salt.states.git.latest>`
state).

.. note::
    If compatible versions of both pygit2_ and GitPython_ are installed, then
    Salt will prefer pygit2_. To override this behavior use the
    :conf_master:`winrepo_provider` configuration parameter:

    .. code-block:: yaml

        winrepo_provider: gitpython

    The :mod:`winrepo execution module <salt.modules.win_repo>` (discussed
    above in the :ref:`Managing Windows Software on a Standalone Windows Minion
    <standalone-winrepo>` section) does not yet officially support the new
    pygit2_/GitPython_ functionality, but if either pygit2_ or GitPython_ is
    installed into Salt's bundled Python then it *should* work. However, it
    should be considered experimental at this time.

Accessing Authenticated Git Repos (pygit2)
******************************************

Support for pygit2 added the ability to access authenticated git repositories
and to set per-remote config settings. An example of this would be the
following:

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
    counterparts. For instance, setting :conf_master:`winrepo_passphrase` would
    set a global passphrase for winrepo that would apply to all SSH-based
    remotes, unless overridden by a ``passphrase`` per-remote parameter.

    See :ref:`here <gitfs-per-remote-config>` for more a more in-depth
    explanation of how per-remote configuration works in gitfs. The same
    principles apply to winrepo.

Maintaining Git Repos
*********************

A ``clean`` argument has been added to the
:mod:`winrepo.update_git_repos <salt.runners.winrepo.update_git_repos>`
runner. When ``clean`` is ``True`` it will tell the runner to dispose of
directories under the :conf_master:`winrepo_dir_ng`/:conf_minion:`winrepo_dir_ng`
which are not explicitly configured. This prevents the need to manually remove
these directories when a repo is removed from the config file. To clean these
old directories, just pass ``clean=True``:

.. code-block:: bash

    salt-run winrepo.update_git_repos clean=True

If a mix of git and non-git Windows Repo definition files are being used, then
this should *not* be used, as it will remove the directories containing non-git
definitions.

Name Collisions Between Repos
*****************************

Collisions between repo names are now detected. The
:mod:`winrepo.update_git_repos <salt.runners.winrepo.update_git_repos>`
runner will not proceed if any are detected. Consider the following
configuration:

.. code-block:: yaml

    winrepo_remotes:
      - https://foo.com/bar/baz.git
      - https://mydomain.tld/baz.git
      - https://github.com/foobar/baz

The :mod:`winrepo.update_git_repos <salt.runners.winrepo.update_git_repos>`
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

.. _legacy-minions:

Legacy Minions
**************

The Windows Package Manager was upgraded with breaking changes starting with
Salt 2015.8.0. To maintain backwards compatibility Salt continues to support
older minions.

The breaking change was to generate the winrepo database on the minion instead
of the master. This allowed for the use of Jinja in the software definition
files. It enabled the use of pillar, grains, execution modules, etc. during
compile time. To support this new functionality, a next-generation (ng) repo was
created.

See the :ref:`Changes in Version 2015.8.0 <2015-8-0-winrepo-changes>` for
details.

On prior versions of Salt, or legacy minions, the winrepo database was
generated on the master and pushed down to the minions. Any grains exposed at
compile time would have been those of the master and not the minion.

The repository for legacy minions is named ``salt-winrepo`` and is located at:

- https://github.com/saltstack/salt-winrepo

Legacy Configuration
====================

Winrepo settings were changed with the introduction of the Next Generation (ng)
of winrepo.

Legacy Master Config Options
----------------------------
There were three options available for a legacy master to configure winrepo.
Unless you're running a legacy master as well, you shouldn't need to configure
any of these.

- ``win_gitrepos``
- ``win_repo``
- ``win_repo_mastercachefile``

``win_gitrepos``: (list)

A list of URLs to github repos. Default is a list with a single URL:

- 'https://github.com/saltstack/salt-winrepo.git'

``win_repo``: (str)

The location on the master to store the winrepo. The default is
``/srv/salt/win/repo``.

``win_repo_mastercachefile``: (str)
The location on the master to generate the winrepo database file. The default is
``/srv/salt/win/repo/winrep.p``

Legacy Minion Config Options
----------------------------

There is only one option available to configure a legacy minion for winrepo.

- ``win_repo_cachefile``

``win_repo_cachefile``: (str)

The location on the Salt file server to obtain the winrepo database file. The
default is ``salt://win/repo/winrepo.p``

.. note::
    If the location of the ``winrepo.p`` file is not in the default location on
    the master, the :conf_minion:`win_repo_cachefile` setting will need to be
    updated to reflect the proper location on each minion.

Legacy Quick Start
==================

You can get up and running with winrepo pretty quickly just using the defaults.
Assuming no changes to the default configuration (ie, ``file_roots``) run the
following commands on the master:

.. code-block:: bash

    salt-run winrepo.update_git_repos
    salt-run winrepo.genrepo
    salt * pkg.refresh_db
    salt * pkg.install firefox

These commands clone the default winrepo from github, generate the metadata
file, push the metadata file down to the legacy minion, and install the latest
version of Firefox.

Legacy Initialization
=====================

Initializing the winrepo for a legacy minion is similar to that for a newer
minion. There is an added step in that the metadata file needs to be generated
on the master prior to refreshing the database on the minion.

Populate the Local Repository
-----------------------------

The SLS files used to install Windows packages are not distributed by default
with Salt. So, the first step is to clone the repo to the master. Use the
:mod:`winrepo.update_git_repos <salt.runners.winrepo.update_git_repos>`
runner initialize the repository in the location specified by ``winrepo_dir``
in the master config. This will pull the software definition files down from the
git repository.

.. code-block:: bash

    salt-run winrepo.update_git_repos

Generate the Metadata File
--------------------------

The next step is to create the metadata file for the repo (``winrepo.p``).
The metadata file is generated on the master using the
:mod:`winrepo.genrepo <salt.runners.winrepo.genrepo>` runner.

.. code-block:: bash

    salt-run winrepo.genrepo

.. note::
    You only need to do this if you need to support legacy minions.

Update the Minion Database
--------------------------

Run :mod:`pkg.refresh_db <salt.modules.win_pkg.refresh_db>` on each of your
Windows minions to copy the metadata file down to the minion.

.. code-block:: bash

    # From the master
    salt -G 'os:windows' pkg.refresh_db

.. _2015-8-0-winrepo-changes:

Changes in Version 2015.8.0+
============================

Git repository management for the Windows Software Repository changed in version
2015.8.0, and several master/minion config parameters were renamed for
consistency.

For a complete list of the new winrepo config options, see
:ref:`here <winrepo-master-config-opts>` for master config options, and
:ref:`here <winrepo-minion-config-opts>` for configuration options for masterless Windows
minions.

pygit2_/GitPython_ Support
--------------------------

On the master, the
:mod:`winrepo.update_git_repos <salt.runners.winrepo.update_git_repos>`
runner was updated to use either pygit2_ or GitPython_ to checkout the git
repositories containing repo data. If pygit2_ or GitPython_ is installed,
existing winrepo git checkouts should be removed after upgrading to 2015.8.0.
Then they should be cloned again by running
:mod:`winrepo.update_git_repos <salt.runners.winrepo.update_git_repos>`.

If neither GitPython_ nor pygit2_ are installed, Salt will fall back to
pre-existing behavior for
:mod:`winrepo.update_git_repos <salt.runners.winrepo.update_git_repos>`, and a
warning will be logged in the master log.

.. note::
    Standalone Windows minions do not support the new GitPython_/pygit2_
    functionality, and will instead use the
    :mod:`git.latest <salt.states.git.latest>` state to keep repositories
    up-to-date. More information on how to use the Windows Software Repo on a
    standalone minion can be found :ref:`here <standalone-winrepo>`.

Config Parameters Renamed
-------------------------

Many of the legacy winrepo configuration parameters changed in version 2015.8.0
to make them more consistent. Below are the parameters which changed for
version 2015.8.0:

Master Config

======================== ================================
Old Name                 New Name
======================== ================================
win_repo                 :conf_master:`winrepo_dir`
win_repo_mastercachefile No longer used on master
win_gitrepos             :conf_master:`winrepo_remotes`
======================== ================================

.. note::
    The ``winrepo_dir_ng`` and ``winrepo_remotes_ng`` settings were introduced
    in 2015.8.0 for working with the next generation repo.

See :ref:`here <winrepo-master-config-opts>` for detailed information on all
master config options for the Windows Repo.

Minion Config

======================== ================================
Old Name                 New Name
======================== ================================
win_repo                 :conf_minion:`winrepo_dir`
win_repo_cachefile       :conf_minion:`winrepo_cachefile`
win_gitrepos             :conf_minion:`winrepo_remotes`
======================== ================================

.. note::
    The ``winrepo_dir_ng`` and ``winrepo_remotes_ng`` settings were introduced
    in 2015.8.0 for working with the next generation repo.

See :ref:`here <winrepo-minion-config-opts>` for detailed information on all
minion config options for the Windows Repo.

.. _wiki: https://wpkg.org/Category:Silent_Installers
.. _pygit2: https://github.com/libgit2/pygit2
.. _GitPython: https://github.com/gitpython-developers/GitPython
