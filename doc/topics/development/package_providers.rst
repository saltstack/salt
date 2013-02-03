=================
Package Providers
=================

This page contains guidelines for writing package providers.

Functions
---------

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


available_version
^^^^^^^^^^^^^^^^^

Accepts an arbitrary number of arguments. Each argument is a package name. The
return value for a package will be an empty string if the package is not found
or if the package is up-to-date. The only case in which a non-empty string is
returned is if the package is available for new installation (i.e. not already
installed) or if there is an upgrade available.

If only one argument was passed, this function return a string, otherwise a
dict of name/version pairs is returned.


version
^^^^^^^

Like ``available_version``, accepts an arbitrary number of arguments and
returns a string if a single package name was passed, or a dict of name/value
pairs if more than one was passed. The only difference is that the return
values are the currently-installed versions of whatever packages are passed. If
the package is not installed, an empty string is returned for that package.


upgrade_available
^^^^^^^^^^^^^^^^^

Deprecated and destined to be removed. For now, should just do the following:

.. code-block:: python

        return __salt__['pkg.available_version'](name) != ''


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


The second return value will be a string with two possbile values:
``repository`` or ``file``. The :strong:`install` function can use this value
(if necessary) to build the proper command to install the targeted package(s).

Both before and after the installing the target(s), you should run
:strong:`list_pkgs` to obtain a list of the installed packages. You should then
return the output of
:mod:`pkg_resource.find_changes <salt.modules.pkg_resource.find_changes>`:

.. code-block:: python

        return __salt__['pkg_resource.find_changes'](old, new)


remove
^^^^^^

Removes the passed package and return a list of the packages removed.
