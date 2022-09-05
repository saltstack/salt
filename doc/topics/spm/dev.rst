.. _spm-development:

=====================
SPM Development Guide
=====================
This document discusses developing additional code for SPM.


SPM-Specific Loader Modules
===========================
SPM was designed to behave like traditional package managers, which apply files
to the filesystem and store package metadata in a local database. However,
because modern infrastructures often extend beyond those use cases, certain
parts of SPM have been broken out into their own set of modules.

Each function that accepts arguments has a set of required and optional
arguments. Take note that SPM will pass all arguments in, and therefore each
function must accept each of those arguments. However, arguments that are
marked as required are crucial to SPM's core functionality, while arguments that
are marked as optional are provided as a benefit to the module, if it needs to
use them.

.. _spm-development-pkgdb:

Package Database
----------------
By default, the package database is stored using the ``sqlite3`` module. This
module was chosen because support for SQLite3 is built into Python itself.

Modules for managing the package database are stored in the ``salt/spm/pkgdb/``
directory. A number of functions must exist to support database management.


init()
``````
Get a database connection, and initialize the package database if necessary.

This function accepts no arguments. If a database is used which supports a
connection object, then that connection object is returned. For instance, the
``sqlite3`` module returns a ``connect()`` object from the ``sqlite3`` library:

.. code-block:: python

   def myfunc():
       conn = sqlite3.connect(__opts__["spm_db"], isolation_level=None)
       ...
       return conn

SPM itself will not use this connection object; it will be passed in as-is to
the other functions in the module. Therefore, when you set up this object, make
sure to do so in a way that is easily usable throughout the module.


info()
``````
Return information for a package. This generally consists of the information
that is stored in the ``FORMULA`` file in the package.

The arguments that are passed in, in order, are ``package`` (required) and
``conn`` (optional).

``package`` is the name of the package, as specified in the ``FORMULA``.
``conn`` is the connection object returned from ``init()``.


list_files()
````````````
Return a list of files for an installed package. Only the filename should be
returned, and no other information.

The arguments that are passed in, in order, are ``package`` (required) and
``conn`` (optional).

``package`` is the name of the package, as specified in the ``FORMULA``.
``conn`` is the connection object returned from ``init()``.


register_pkg()
``````````````
Register a package in the package database. Nothing is expected to be returned
from this function.

The arguments that are passed in, in order, are ``name`` (required),
``formula_def`` (required), and ``conn`` (optional).

``name`` is the name of the package, as specified in the ``FORMULA``.
``formula_def`` is the contents of the ``FORMULA`` file, as a ``dict``. ``conn``
is the connection object returned from ``init()``.



register_file()
```````````````
Register a file in the package database. Nothing is expected to be returned
from this function.

The arguments that are passed in are ``name`` (required), ``member`` (required),
``path`` (required), ``digest`` (optional), and ``conn`` (optional).

``name`` is the name of the package.

``member`` is a ``tarfile`` object for the
package file. It is included, because it contains most of the information for
the file.

``path`` is the location of the file on the local filesystem.

``digest`` is the SHA1 checksum of the file.

``conn`` is the connection object returned from ``init()``.


unregister_pkg()
````````````````
Unregister a package from the package database. This usually only involves
removing the package's record from the database. Nothing is expected to be
returned from this function.

The arguments that are passed in, in order, are ``name`` (required) and
``conn`` (optional).

``name`` is the name of the package, as specified in the ``FORMULA``. ``conn``
is the connection object returned from ``init()``.


unregister_file()
`````````````````
Unregister a package from the package database. This usually only involves
removing the package's record from the database. Nothing is expected to be
returned from this function.

The arguments that are passed in, in order, are ``name`` (required), ``pkg``
(optional) and ``conn`` (optional).

``name`` is the path of the file, as it was installed on the filesystem.

``pkg`` is the name of the package that the file belongs to.

``conn`` is the connection object returned from ``init()``.


db_exists()
```````````
Check to see whether the package database already exists. This is the path to
the package database file. This function will return ``True`` or ``False``.

The only argument that is expected is ``db_``, which is the package database
file.


.. _spm-development-pkgfiles:

Package Files
-------------
By default, package files are installed using the ``local`` module. This module
applies files to the local filesystem, on the machine that the package is
installed on.

Modules for managing the package database are stored in the
``salt/spm/pkgfiles/`` directory. A number of functions must exist to support
file management.

init()
``````
Initialize the installation location for the package files. Normally these will
be directory paths, but other external destinations such as databases can be
used. For this reason, this function will return a connection object, which can
be a database object. However, in the default ``local`` module, this object is a
dict containing the paths. This object will be passed into all other functions.

Three directories are used for the destinations: ``formula_path``,
``pillar_path``, and ``reactor_path``.

``formula_path`` is the location of most of the files that will be installed.
The default is specific to the operating system, but is normally ``/srv/salt/``.

``pillar_path`` is the location that the ``pillar.example`` file will be
installed to.  The default is specific to the operating system, but is normally
``/srv/pillar/``.

``reactor_path`` is the location that reactor files will be installed to. The
default is specific to the operating system, but is normally ``/srv/reactor/``.


check_existing()
````````````````
Check the filesystem for existing files. All files for the package will be
checked, and if any are existing, then this function will normally state that
SPM will refuse to install the package.

This function returns a list of the files that exist on the system.

The arguments that are passed into this function are, in order: ``package``
(required), ``pkg_files`` (required), ``formula_def`` (formula_def), and
``conn`` (optional).

``package`` is the name of the package that is to be installed.

``pkg_files`` is a list of the files to be checked.

``formula_def`` is a copy of the information that is stored in the ``FORMULA``
file.

``conn`` is the file connection object.


install_file()
``````````````
Install a single file to the destination (normally on the filesystem). Nothing
is expected to be returned from this function.

This function returns the final location that the file was installed to.

The arguments that are passed into this function are, in order, ``package``
(required), ``formula_tar`` (required), ``member`` (required), ``formula_def``
(required), and ``conn`` (optional).

``package`` is the name of the package that is to be installed.

``formula_tar`` is the tarfile object for the package. This is passed in so that
the function can call ``formula_tar.extract()`` for the file.

``member`` is the tarfile object which represents the individual file. This may
be modified as necessary, before being passed into ``formula_tar.extract()``.

``formula_def`` is a copy of the information from the ``FORMULA`` file.

``conn`` is the file connection object.


remove_file()
`````````````
Remove a single file from file system. Normally this will be little more than an
``os.remove()``. Nothing is expected to be returned from this function.

The arguments that are passed into this function are, in order, ``path``
(required) and ``conn`` (optional).

``path`` is the absolute path to the file to be removed.

``conn`` is the file connection object.


hash_file()
```````````
Returns the hexdigest hash value of a file.

The arguments that are passed into this function are, in order, ``path``
(required), ``hashobj`` (required), and ``conn`` (optional).

``path`` is the absolute path to the file.

``hashobj`` is a reference to ``hashlib.sha1()``, which is used to pull the
``hexdigest()`` for the file.

``conn`` is the file connection object.

This function will not generally be more complex than:

.. code-block:: python

    def hash_file(path, hashobj, conn=None):
        with salt.utils.files.fopen(path, "r") as f:
            hashobj.update(f.read())
            return hashobj.hexdigest()


path_exists()
`````````````
Check to see whether the file already exists on the filesystem. Returns ``True``
or ``False``.

This function expects a ``path`` argument, which is the absolute path to the
file to be checked.


path_isdir()
````````````
Check to see whether the path specified is a directory. Returns ``True`` or
``False``.

This function expects a ``path`` argument, which is the absolute path to be
checked.
