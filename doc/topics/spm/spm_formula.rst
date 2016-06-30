.. _spm-formula:

============
FORMULA File
============

In addition to the formula itself, a ``FORMULA`` file must exist which
describes the package. An example of this file is:

.. code-block:: yaml

    name: apache
    os: RedHat, Debian, Ubuntu, SUSE, FreeBSD
    os_family: RedHat, Debian, SUSE, FreeBSD
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
should be ``201506``. If multiple releases are made in a month, the ``release``
field should be used.

minimum_version
~~~~~~~~~~~~~~~
Minimum recommended version of Salt to use this formula. Not currently enforced.

release
~~~~~~~
This field refers primarily to a release of a version, but also to multiple
versions within a month. In general, if a version has been made public, and
immediate updates need to be made to it, this field should also be updated.

summary
~~~~~~~
A one-line description of the package.

description
~~~~~~~~~~~
A more detailed description of the package which can contain more than one line.

Optional Fields
```````````````
The following fields may also be present.

top_level_dir
~~~~~~~~~~~~~
This field is optional, but highly recommended. If it is not specified, the
package name will be used.

Formula repositories typically do not store ``.sls`` files in the root of the
repository; instead they are stored in a subdirectory. For instance, an
``apache-formula`` repository would contain a directory called ``apache``, which
would contain an ``init.sls``, plus a number of other related files. In this
instance, the ``top_level_dir`` should be set to ``apache``.

Files outside the ``top_level_dir``, such as ``README.rst``, ``FORMULA``, and
``LICENSE`` will not be installed. The exceptions to this rule are files that
are already treated specially, such as ``pillar.example`` and ``_modules/``.

dependencies
~~~~~~~~~~~~
A comma-separated list of packages that must be installed along with this
package. When this package is installed, SPM will attempt to discover and
install these packages as well. If it is unable to, then it will refuse to
install this package.

This is useful for creating packages which tie together other packages. For
instance, a package called wordpress-mariadb-apache would depend upon
wordpress, mariadb, and apache.

optional
~~~~~~~~
A comma-separated list of packages which are related to this package, but are
neither required nor necessarily recommended. This list is displayed in an
informational message when the package is installed to SPM.

recommended
~~~~~~~~~~~
A comma-separated list of optional packages that are recommended to be
installed with the package. This list is displayed in an informational message
when the package is installed to SPM.

Building a Package
------------------
Once a ``FORMULA`` file has been created, it is placed into the root of the
formula that is to be turned into a package. The ``spm build`` command is
used to turn that formula into a package:

.. code-block:: bash

    spm build /path/to/saltstack-formulas/apache-formula

The resulting file will be placed in the build directory. By default this
directory is located at ``/srv/spm/``.

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
Packages are built using BZ2-compressed tarballs. By default, the package
database is stored using the ``sqlite3`` driver (see Loader Modules below).

Support for these are built into Python, and so no external dependencies are
needed.

All other files belonging to SPM use YAML, for portability and ease of use and
maintainability.


SPM-Specific Loader Modules
===========================
SPM was designed to behave like traditional package managers, which apply files
to the filesystem and store package metadata in a local database. However,
because modern infrastructures often extend beyond those use cases, certain
parts of SPM have been broken out into their own set of modules.


Package Database
----------------
By default, the package database is stored using the ``sqlite3`` module. This
module was chosen because support for SQLite3 is built into Python itself.

Please see the SPM Development Guide for information on creating new modules
for package database management.


Package Files
-------------
By default, package files are installed using the ``local`` module. This module
applies files to the local filesystem, on the machine that the package is
installed on.

Please see the :ref:`SPM Development Guide <spm-development>` for information
on creating new modules for package file management.


Types of Packages
=================
SPM supports different types of formula packages. The function of each package
is denoted by its name. For instance, packages which end in ``-formula`` are
considered to be Salt States (the most common type of formula). Packages which
end in ``-conf`` contain configuration which is to be placed in the
``/etc/salt/`` directory. Packages which do not contain one of these names are
treated as if they have a ``-formula`` name.

formula
-------
By default, most files from this type of package live in the ``/srv/spm/salt/``
directory. The exception is the ``pillar.example`` file, which will be renamed
to ``<package_name>.sls`` and placed in the pillar directory (``/srv/spm/pillar/``
by default).

reactor
-------
By default, files from this type of package live in the ``/srv/spm/reactor/``
directory.

conf
----
The files in this type of package are configuration files for Salt, which
normally live in the ``/etc/salt/`` directory. Configuration files for packages
other than Salt can and should be handled with a Salt State (using a ``formula``
type of package).
