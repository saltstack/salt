.. _spm:

====================
Salt Package Manager
====================
The Salt Package Manager, or SPM, allows Salt formulas to be packaged, for ease
of deployment. The design of SPM was influenced by other existing packaging
systems including RPM, Yum, and Pacman.


Building Packages
=================
Before SPM can install packages, they must be built. The source for these
packages is often a Git repository, such as those found at the
``saltstack-formulas`` organization on GitHub.

FORMULA
-------
In addition to the formula itself, a ``FORMULA`` file must exist which
describes the package. An example of this file is:

.. code-block:: yaml

    name: apache
    os: RedHat, Debian, Ubuntu, Suse, FreeBSD
    os_family: RedHat, Debian, Suse, FreeBSD
    dependencies: None
    version: 201506
    release: 2
    summary: Formula for installing Apache
    description: Formula for installing Apache

Required Fields
```````````````
This file must contain at least the following fields:

name
~~~~
The name of the package, as it will appear in the package filename, in the
repository metadata, and the package database. Even if the source formula has
``-formula`` in its name, this name should probably not include that. For
instance, when packaging the ``apache-formula``, the name should be set to
``apache``.

os
~~
The value of the ``os`` grain that this formula supports. This is used to
help users know which operating systems can support this package.

os_family
~~~~~~~~~
The value of the ``os_family`` grain that this formula supports. This is used to
help users know which operating system families can support this package.

version
~~~~~~~
The version of the package. While it is up to the organization that manages this
package, it is suggested that this version is specified in a ``YYYYMM`` format.
For instance, if this version was released in June 2015, the package version
should be ``201506``. If multiple released are made in a month, the ``release``
field should be used.

release
~~~~~~~
This field refers primarily to a release of a version, but also to multiple
versions within a month. In general, if a version has been made public, and
immediate updates need to be made to it, this field should also be updated.

summary
~~~~~~~
A one-line description of the package.

description
A more detailed description of the package which can contain more than one line.

Optional Fields
```````````````
The following fields may also be present.

dependencies
~~~~~~~~~~~~
A list of packages which must be installed before this package can function.

Building a Package
------------------
Once a ``FORMULA`` file has been created, it is placed into the root of the
formula that is to be turned into a package. The the ``spm build`` command is
used to turn that formula into a package:

.. code-block:: bash

    spm build /path/to/saltstack-formulas/apache-formula

The resulting file will be placed in the build directory. By default this
directory is located at ``/srv/spm/``.


Building Repositories
=====================
Once one or more packages have been built, they can be made available to SPM
via a package repository. Place the packages into the directory to be served
and issue an ``spm create_repo`` command:

.. code-block:: bash

    spm create_repo /srv/spm

This command is used, even if reposity metadata already exists in that
directory. SPM will regenerate the repository metadata again, using all of the
packages in that directory.


Configuring Remote Repositories
===============================
Before SPM can use a repository, two things need to happen. First, SPM needs to
know where the repositories are. Then it needs to pull down the repository
metadata.

Repository Configuration Files
------------------------------
Normally repository configuration files are placed in the
``/etc/salt/spm.repos.d``. These files contain the name of the repository, and
the link to that repository:

.. code-block:: yaml

    my_repo:
      url: https://spm.example.com/

The URL can use ``http``, ``https``, ``ftp``, or ``file``.

.. code-block:: yaml

    local_repo:
      url: file:///srv/spm

Updating Local Repository Metadata
----------------------------------
Once the repository is configured, its metadata needs to be downloaded. At the
moment, this is a manual process, using the ``spm update_repo`` command.

.. code-block:: bash

    spm update_repo

Installing Packages
===================
Packages may be installed either from a local file, or from an SPM repository.
To install from a repository, use the ``spm install`` command:

.. code-block:: bash

    spm install apache

To install from a local file, use the ``spm local_install`` command:

.. code-block:: bash

    spm local_install /srv/spm/apache-201506-1.spm

Currently, SPM does not check to see if files are already in place before
installing them. That means that existing files will be overwritten without
warning.

Pillars
=======
Formula packages include a pillar.example file. Rather than being placed in the
formula directory, this file is renamed to ``<formula name>.sls.orig`` and
placed in the ``pillar_roots``, where it can be easily updated to meet the
user's needs.

Loader Modules
==============
When an execution module is placed in ``<file_roots>/_modules/`` on the master,
it will automatically be synced to minions, the next time a sync operation takes
place. Other modules are also propagated this way: state modules can be placed
in ``_states/``, and so on.

When SPM detects a file in a package which resides in one of these directories,
that directory will be placed in ``<file_roots>`` instead of in the formula
directory with the rest of the files.

Removing Packages
=================
Packages may be removed once they are installed using the ``spm remove``
command.

.. code-block:: bash

    spm remove apache

If files have been modified, they will not be removed. Empty directories will
also be removed.


Technical Information
=====================
Packages are built using BZ2-compressed tarballs. Support for this is built into
Python, and so no external dependencies are needed.

The package database is stored using SQLite3. Support for this is built into
Python, and so no external dependencies are needed.

All other files belonging to SPM use YAML, for portability and ease of use and
maintainability.


SPM Configuration
=================
There are a number of options that are specific to SPM. They may be configured
in the ``master`` configuration file, or in SPM's own ``spm`` configuration
file (normally located at ``/etc/salt/spm``). If configured in both places, the
``spm`` file takes precedence. In general, these values will not need to be
changed from the defaults.

spm_logfile
-----------
Default: ``/var/log/salt/spm``

Where SPM logs messages.

spm_repos_config
----------------
Default: ``/etc/salt/spm.repos``

SPM repositories are configured with this file. There is also a directory which
corresponds to it, which ends in ``.d``. For instance, if the filename is
``/etc/salt/spm.repos``, the directory will be ``/etc/salt/spm.repos.d/``.

spm_cache_dir
-------------
Default: ``/var/cache/salt/spm``

When SPM updates package repository metadata and downloads packaged, they will
be placed in this directory. The package database, normally called
``packages.db``, also lives in this directory.

spm_db
------
Default: ``/var/cache/salt/spm/packages.db``

The location and name of the package database. This database stores the names of
all of the SPM packages installed on the system, the files that belong to them,
and the metadata for those files.

spm_build_dir
-------------
Default: ``/srv/spm``

When packages are built, they will be placed in this directory.

spm_build_exclude
-----------------
Default: ``['.git']``

When SPM builds a package, it normally adds all files in the formula directory
to the package. Files listed here will be excluded from that package. This
option requires a list to be specified.

.. code-block:: yaml

    spm_build_exclude:
      - .git
      - .svn
