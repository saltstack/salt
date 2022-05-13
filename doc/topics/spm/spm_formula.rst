.. _spm-formula:

============
FORMULA File
============

In addition to the formula itself, a ``FORMULA`` file must exist which
describes the package. An example of this file is:

.. code-block:: yaml

    name: apache
    os: RedHat, Debian, Ubuntu, SUSE, FreeBSD
    os_family: RedHat, Debian, Suse, FreeBSD
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

files
~~~~~
A files section can be added, to specify a list of files to add to the SPM.
Such a section might look like:

.. code-block:: yaml

    files:
      - _pillar
      - FORMULA
      - _runners
      - d|mymodule/index.rst
      - r|README.rst

When ``files`` are specified, then only those files will be added to the SPM,
regardless of what other files exist in the directory. They will also be added
in the order specified, which is useful if you have a need to lay down files in
a specific order.

As can be seen in the example above, you may also tag files as being a specific
type. This is done by pre-pending a filename with its type, followed by a pipe
(``|``) character. The above example contains a document file and a readme. The
available file types are:

* ``c``: config file
* ``d``: documentation file
* ``g``: ghost file (i.e. the file contents are not included in the package payload)
* ``l``: license file
* ``r``: readme file
* ``s``: SLS file
* ``m``: Salt module

The first 5 of these types (``c``, ``d``, ``g``, ``l``, ``r``) will be placed in
``/usr/share/salt/spm/`` by default. This can be changed by setting an
``spm_share_dir`` value in your ``/etc/salt/spm`` configuration file.

The last two types (``s`` and ``m``) are currently ignored, but they are
reserved for future use.

Pre and Post States
-------------------
It is possible to run Salt states before and after installing a package by
using pre and post states. The following sections may be declared in a
``FORMULA``:

* ``pre_local_state``
* ``pre_tgt_state``
* ``post_local_state``
* ``post_tgt_state``

Sections with ``pre`` in their name are evaluated before a package is installed
and sections with ``post`` are evaluated after a package is installed. ``local``
states are evaluated before ``tgt`` states.

Each of these sections needs to be evaluated as text, rather than as YAML.
Consider the following block:

.. code-block:: yaml

    pre_local_state: >
      echo test > /tmp/spmtest:
        cmd:
          - run

Note that this declaration uses ``>`` after ``pre_local_state``. This is a YAML
marker that marks the next multi-line block as text, including newlines. It is
important to use this marker whenever declaring ``pre`` or ``post`` states, so
that the text following it can be evaluated properly.

local States
~~~~~~~~~~~~
``local`` states are evaluated locally; this is analogous to issuing a state
run using a ``salt-call --local`` command. These commands will be issued on the
local machine running the ``spm`` command, whether that machine is a master or
a minion.

``local`` states do not require any special arguments, but they must still use
the ``>`` marker to denote that the state is evaluated as text, not a data
structure.

.. code-block:: yaml

    pre_local_state: >
      echo test > /tmp/spmtest:
        cmd:
          - run

tgt States
~~~~~~~~~~
``tgt`` states are issued against a remote target. This is analogous to issuing
a state using the ``salt`` command. As such it requires that the machine that
the ``spm`` command is running on is a master.

Because ``tgt`` states require that a target be specified, their code blocks
are a little different. Consider the following state:

.. code-block:: yaml

    pre_tgt_state:
      tgt: '*'
      data: >
        echo test > /tmp/spmtest:
          cmd:
            - run

With ``tgt`` states, the state data is placed under a ``data`` section, inside
the ``*_tgt_state`` code block. The target is of course specified as a ``tgt``
and you may also optionally specify a ``tgt_type`` (the default is ``glob``).

You still need to use the ``>`` marker, but this time it follows the ``data``
line, rather than the ``*_tgt_state`` line.

Templating States
~~~~~~~~~~~~~~~~~
The reason that state data must be evaluated as text rather than a data
structure is because that state data is first processed through the rendering
engine, as it would be with a standard state run.

This means that you can use Jinja or any other supported renderer inside of
Salt. All formula variables are available to the renderer, so you can reference
``FORMULA`` data inside your state if you need to:

.. code-block:: yaml

    pre_tgt_state:
      tgt: '*'
      data: >
         echo {{ name }} > /tmp/spmtest:
          cmd:
            - run

You may also declare your own variables inside the ``FORMULA``. If SPM doesn't
recognize them then it will ignore them, so there are no restrictions on
variable names, outside of avoiding reserved words.

By default the renderer is set to ``jinja|yaml``. You may change this by
changing the ``renderer`` setting in the ``FORMULA`` itself.

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
