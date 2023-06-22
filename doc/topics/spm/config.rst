.. _spm-config:

=================
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
Default: ``/srv/spm_build``

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
