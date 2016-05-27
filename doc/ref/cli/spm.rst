.. _spm-cli:

=======
``spm``
=======

:ref:`Salt Package Manager <spm>`

Synopsis
========

.. code-block:: bash

    spm <command> [<argument>]

Description
===========

spm is the frontend command for managing Salt packages. Packages normally only
include formulas, meaning a group of SLS files that install into the
``file_roots`` on the Salt Master, but Salt modules can also be installed.

Options
=======

.. program:: spm

.. option:: -y, --assume-yes

    Assume ``yes`` instead of prompting the other whether or not to proceed
    with a particular command. Default is False.

.. option:: -f, --force

    When presented with a course of action that spm would normally refuse to
    perform, that action will be performed anyway. This is often destructive,
    and should be used with caution.

.. include:: _includes/logging-options.rst
.. |logfile| replace:: /var/log/salt/spm
.. |loglevel| replace:: ``warning``


Commands
========

.. program:: spm

.. option:: update_repo

    Connect to remote repositories locally configured on the system and download
    their metadata.

.. option:: install

    Install a package from a configured SPM repository. Requires a package name.

.. option:: remove

    Remove an installed package from the system. Requires a package name.

.. option:: info

    List information about an installed package. Requires a package name.

.. option:: files

    List files belonging to an installed package. Requires a package name.

.. option:: local

    Perform one of the above options (except for remove) on a package file,
    instead of on a package in a repository, or an installed package. Requires
    a valid path to a local file on the system.

.. option:: build

    Build a package from a directory containing a FORMULA file. Requires a valid
    path to a local directory on the system.

.. option:: create_repo

    Scan a directory for valid SPM package files and build an SPM-METADATA file
    in that directory which describes them.


See also
========

:manpage:`salt(1)`
:manpage:`salt-master(1)`
:manpage:`salt-minion(1)`
