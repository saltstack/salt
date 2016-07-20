=================
Package Providers
=================

This page contains guidelines for writing package providers.

Package Functions
-----------------

One of the most important features of Salt is package management. There is no
shortage of package managers, so in the interest of providing a consistent
experience in :mod:`pkg <salt.states.pkg>` states, there are certain functions
that should be present in a package provider. Note that these are subject to
change as new features are added or existing features are enhanced.


list_pkgs
^^^^^^^^^

This function should declare an empty dict, and then add packages to it by
calling :mod:`pkg_resource.add_pkg <salt.modules.pkg_resource.add_pkg>`, like
so:

.. code-block:: python

        __salt__['pkg_resource.add_pkg'](ret, name, version)

The last thing that should be done before returning is to execute
:mod:`pkg_resource.sort_pkglist <salt.modules.pkg_resource.sort_pkglist>`. This
function does not presently do anything to the return dict, but will be used in
future versions of Salt.

.. code-block:: python

        __salt__['pkg_resource.sort_pkglist'](ret)


``list_pkgs`` returns a dictionary of installed packages, with the keys being
the package names and the values being the version installed. Example return
data:

.. code-block:: python

        {'foo': '1.2.3-4',
         'bar': '5.6.7-8'}


latest_version
^^^^^^^^^^^^^^

Accepts an arbitrary number of arguments. Each argument is a package name. The
return value for a package will be an empty string if the package is not found
or if the package is up-to-date. The only case in which a non-empty string is
returned is if the package is available for new installation (i.e. not already
installed) or if there is an upgrade available.

If only one argument was passed, this function return a string, otherwise a
dict of name/version pairs is returned.

This function must also accept ``**kwargs``, in order to receive the
``fromrepo`` and ``repo`` keyword arguments from pkg states. Where supported,
these arguments should be used to find the install/upgrade candidate in the
specified repository. The ``fromrepo`` kwarg takes precedence over ``repo``, so
if both of those kwargs are present, the repository specified in ``fromrepo``
should be used. However, if ``repo`` is used instead of ``fromrepo``, it should
still work, to preserve backwards compatibility with older versions of Salt.


version
^^^^^^^

Like ``latest_version``, accepts an arbitrary number of arguments and
returns a string if a single package name was passed, or a dict of name/value
pairs if more than one was passed. The only difference is that the return
values are the currently-installed versions of whatever packages are passed. If
the package is not installed, an empty string is returned for that package.


upgrade_available
^^^^^^^^^^^^^^^^^

Deprecated and destined to be removed. For now, should just do the following:

.. code-block:: python

        return __salt__['pkg.latest_version'](name) != ''


install
^^^^^^^

The following arguments are required and should default to ``None``:

#. name (for single-package pkg states)
#. pkgs (for multiple-package pkg states)
#. sources (for binary package file installation)

The first thing that this function should do is call
:mod:`pkg_resource.parse_targets <salt.modules.pkg_resource.parse_targets>`
(see below). This function will convert the SLS input into a more easily parsed
data structure.
:mod:`pkg_resource.parse_targets <salt.modules.pkg_resource.parse_targets>` may
need to be modified to support your new package provider, as it does things
like parsing package metadata which cannot be done for every package management
system.

.. code-block:: python

        pkg_params, pkg_type = __salt__['pkg_resource.parse_targets'](name,
                                                                      pkgs,
                                                                      sources)

Two values will be returned to the :strong:`install` function. The first of
them will be a dictionary. The keys of this dictionary will be package names,
though the values will differ depending on what kind of installation is being
done:

* If :strong:`name` was provided (and :strong:`pkgs` was not), then there will
  be a single key in the dictionary, and its value will be ``None``. Once the
  data has been returned, if the :strong:`version` keyword argument was
  provided, then it should replace the ``None`` value in the dictionary.

* If :strong:`pkgs` was provided, then :strong:`name` is ignored, and the
  dictionary will contain one entry for each package in the :strong:`pkgs`
  list. The values in the dictionary will be ``None`` if a version was not
  specified for the package, and the desired version if specified. See the
  :strong:`Multiple Package Installation Options` section of the
  :mod:`pkg.installed <salt.states.pkg.installed>` state for more info.

* If :strong:`sources` was provided, then :strong:`name` is ignored, and the
  dictionary values will be the path/URI for the package.


The second return value will be a string with two possible values:
``repository`` or ``file``. The :strong:`install` function can use this value
(if necessary) to build the proper command to install the targeted package(s).

Both before and after the installing the target(s), you should run
:strong:`list_pkgs` to obtain a list of the installed packages. You should then
return the output of ``salt.utils.compare_dicts()``

.. code-block:: python

        return salt.utils.compare_dicts(old, new)


remove
^^^^^^

Removes the passed package and return a list of the packages removed.


Package Repo Functions
----------------------
There are some functions provided by ``pkg`` which are specific to package
repositories, and not to packages themselves. When writing modules for new
package managers, these functions should be made available as stated below, in
order to provide compatibility with the ``pkgrepo`` state.

All repo functions should accept a basedir option, which defines which
directory repository configuration should be found in. The default for this
is dictated by the repo manager that is being used, and rarely needs to be
changed.

.. code-block:: python

        basedir = '/etc/yum.repos.d'
        __salt__['pkg.list_repos'](basedir)

list_repos
^^^^^^^^^^
Lists the repositories that are currently configured on this system.

.. code-block:: python

    __salt__['pkg.list_repos']()

Returns a dictionary, in the following format:

.. code-block:: python

    {'reponame': 'config_key_1': 'config value 1',
                 'config_key_2': 'config value 2',
                 'config_key_3': ['list item 1 (when appropriate)',
                                  'list item 2 (when appropriate)]}

get_repo
^^^^^^^^
Displays all local configuration for a specific repository.

.. code-block:: python

    __salt__['pkg.get_repo'](repo='myrepo')

The information is formatted in much the same way as list_repos, but is
specific to only one repo.

.. code-block:: python

    {'config_key_1': 'config value 1',
     'config_key_2': 'config value 2',
     'config_key_3': ['list item 1 (when appropriate)',
                      'list item 2 (when appropriate)]}

del_repo
^^^^^^^^
Removes the local configuration for a specific repository. Requires a `repo`
argument, which must match the locally configured name. This function returns
a string, which informs the user as to whether or not the operation was a
success.

.. code-block:: python

    __salt__['pkg.del_repo'](repo='myrepo')

mod_repo
^^^^^^^^
Modify the local configuration for one or more option for a configured repo.
This is also the way to create new repository configuration on the local
system; if a repo is specified which does not yet exist, it will be created.

The options specified for this function are specific to the system; please
refer to the documentation for your specific repo manager for specifics.

.. code-block:: python

    __salt__['pkg.mod_repo'](repo='myrepo', url='http://myurl.com/repo')


Low-Package Functions
---------------------
In general, the standard package functions as describes above will meet your
needs. These functions use the system's native repo manager (for instance,
yum or the apt tools). In most cases, the repo manager is actually separate
from the package manager. For instance, yum is usually a front-end for rpm, and
apt is usually a front-end for dpkg. When possible, the package functions that
use those package managers directly should do so through the low package
functions.

It is normal and sane for ``pkg`` to make calls to ``lowpkgs``, but ``lowpkg``
must never make calls to ``pkg``. This is affects functions which are required
by both ``pkg`` and ``lowpkg``, but the technique in ``pkg`` is more performant
than what is available to ``lowpkg``. When this is the case, the ``lowpkg``
function that requires that technique must still use the ``lowpkg`` version.

list_pkgs
^^^^^^^^^
Returns a dict of packages installed, including the package name and version.
Can accept a list of packages; if none are specified, then all installed
packages will be listed.

.. code-block:: python

    installed = __salt__['lowpkg.list_pkgs']('foo', 'bar')

Example output:

.. code-block:: python

        {'foo': '1.2.3-4',
         'bar': '5.6.7-8'}

verify
^^^^^^
Many (but not all) package management systems provide a way to verify that the
files installed by the package manager have or have not changed. This function
accepts a list of packages; if none are specified, all packages will be
included.

.. code-block:: python

    installed = __salt__['lowpkg.verify']('httpd')

Example output:

.. code-block:: python

    {'/etc/httpd/conf/httpd.conf': {'mismatch': ['size', 'md5sum', 'mtime'],
                                    'type': 'config'}}

file_list
^^^^^^^^^
Lists all of the files installed by all packages specified. If not packages are
specified, then all files for all known packages are returned.

.. code-block:: python

    installed = __salt__['lowpkg.file_list']('httpd', 'apache')

This function does not return which files belong to which packages; all files
are returned as one giant list (hence the `file_list` function name. However,
This information is still returned inside of a dict, so that it can provide
any errors to the user in a sane manner.

.. code-block:: python

    {'errors': ['package apache is not installed'],
      'files': ['/etc/httpd',
                '/etc/httpd/conf',
                '/etc/httpd/conf.d',
                '...SNIP...']}

file_dict
^^^^^^^^^
Lists all of the files installed by all packages specified. If not packages are
specified, then all files for all known packages are returned.

.. code-block:: python

    installed = __salt__['lowpkg.file_dict']('httpd', 'apache', 'kernel')

Unlike `file_list`, this function will break down which files belong to which
packages. It will also return errors in the same manner as `file_list`.

.. code-block:: python

    {'errors': ['package apache is not installed'],
     'packages': {'httpd': ['/etc/httpd',
                            '/etc/httpd/conf',
                            '...SNIP...'],
                  'kernel': ['/boot/.vmlinuz-2.6.32-279.el6.x86_64.hmac',
                             '/boot/System.map-2.6.32-279.el6.x86_64',
                             '...SNIP...']}}
