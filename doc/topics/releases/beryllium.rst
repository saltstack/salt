=======================================
Salt Release Notes - Codename Beryllium
=======================================

Core Changes
============

- Add system version info to ``versions_report``, which appears in both ``salt
  --versions-report`` and ``salt '*' test.versions_report``. Also added is an
  alias ``test.versions`` to ``test.versions_report``. (:issue:`21906`)

- Add colorized console logging support.  This is activated by using
  ``%(colorlevel)s``, ``%(colorname)s``, ``%(colorprocess)s``, ``%(colormsg)s``
  in ``log_fmt_console`` in the config file for any of ``salt-master``,
  ``salt-minion``, and ``salt-cloud``.

Salt Cloud Changes
==================

- Changed the default behavior of ``rename_on_destroy`` to be set to ``True``
  in the EC2 and AWS drivers.
- Changed the default behavior of the EC2 and AWS drivers to always check for
  duplicate names of VMs before trying to create a new VM. Will now throw an
  error similarly to other salt-cloud drivers when trying to create a VM of the
  same name, even if the VM is in the ``terminated`` state.
- Modified the Linode Salt Cloud driver to use Linode's native API instead of
  depending on apache-libcloud or linode-python.
- When querying for VMs in ``ditigal_ocean.py``, the number of VMs to include in
  a page was changed from 20 (default) to 200 to reduce the number of API calls
  to Digital Ocean.

New Docker State/Module
=======================

A new docker :mod:`state <salt.states.dockerng>` and :mod:`execution module
<salt.modules.dockerng>` have been added. They will eventually take the place
of the existing state and execution module, but for now will exist alongside
them.

Git State and Execution Modules Rewritten
=========================================

The git state and execution modules have gone through an extensive overhaul.

Changes in the :py:func:`git.latest <salt.states.git.latest>` State
-------------------------------------------------------------------

- The ``branch`` parameter has been added, allowing for a custom branch name to
  be used in the local checkout maintained by the :py:func:`git.latest
  <salt.states.git.latest>` state. This can be helpful in avoiding ambiguous
  refs in the local checkout when a tag is used as the ``rev`` parameter. If no
  ``branch`` is specified, then the state uses the value of ``rev`` as the
  branch name.
- The ``remote_name`` parameter has been deprecated and renamed to ``remote``.
- The ``force`` parameter has been deprecated and renamed to ``force_clone`` to
  reduce ambiguity with the other "force" parameters.
- Using SHA1 hashes (full or shortened) in the ``rev`` parameter is now
  properly supported.
- Non-fast-forward merges are now detected before the repository is updated,
  and the state will not update the repository if the change is not a
  fast-forward. Non-fast-forward updates must be overridden with the
  ``force_reset`` parameter. If ``force_reset`` is set to ``True``, the state
  will only reset the repository if it cannot be fast-forwarded. This is in
  contrast to the earlier behavior, in which a hard-reset would be performed
  every time the state was run if ``force_reset`` was set to ``True``.
- A ``git pull`` is no longer performed by this state, dropped in favor of a
  fetch-and-merge (or fetch-and-reset) workflow.

:py:func:`git.config_unset <salt.states.git.config_unset>` state added
----------------------------------------------------------------------

This state allows for configuration values (or entire keys) to be unset. See
:py:func:`here <salt.states.git.config_unset>` for more information and example
SLS.

git.config State Renamed to :py:func:`git.config_set <salt.states.git.config_set>`
----------------------------------------------------------------------------------

To reduce confusion after the addition of :py:func:`git.config_unset
<salt.states.git.config_unset>`, the git.config state has been renamed to
:py:func:`git.config_set <salt.states.git.config_set>`. The old config.get name
will still work for a couple releases, allowing time for SLS files to be
updated.

In addition, this state now supports managing multivar git configuration
values. See :py:func:`here <salt.states.git.config_set>` for more information
and example SLS.

Initial Support for Git Worktrees in Execution Module
-----------------------------------------------------

Several functions have been added to the execution module to manage worktrees_
(a feature new to Git 2.5.0). State support does not exist yet, but will follow
soon.

.. _worktrees: http://git-scm.com/docs/git-worktree

New Functions in Git Execution Module
-------------------------------------

- :py:func:`git.config_get_regexp <salt.modules.git.config_regexp>`
- :py:func:`git.config_unset <salt.modules.git.config_unset>`
- :py:func:`git.is_worktree <salt.modules.git.is_worktree>`
- :py:func:`git.list_branches <salt.modules.git.list_branches>`
- :py:func:`git.list_tags <salt.modules.git.list_tags>`
- :py:func:`git.list_worktrees <salt.modules.git.list_worktrees>`
- :py:func:`git.merge_base <salt.modules.git.merge_base>`
- :py:func:`git.merge_tree <salt.modules.git.merge_tree>`
- :py:func:`git.rev_parse <salt.modules.git.rev_parse>`
- :py:func:`git.version <salt.modules.git.version>`
- :py:func:`git.worktree_rm <salt.modules.git.worktree_rm>`
- :py:func:`git.worktree_add <salt.modules.git.worktree_add>`
- :py:func:`git.worktree_prune <salt.modules.git.worktree_prune>`

Changes to Functions in Git Execution Module
--------------------------------------------

:py:func:`git.add <salt.states.git.add>`
****************************************

- ``--verbose`` is now implied when running the ``git add`` command, to provide
  a list of the files added in the return data.

:py:func:`git.archive <salt.modules.git.archive>`
*************************************************

- Now returns ``True`` when the ``git archive`` command was successful, and
  otherwise raises an error.
- ``overwrite`` argument added to prevent an exixting archive from being
  overwritten by this function.
- ``fmt`` argument deprecated and renamed to ``format``
- Trailing slash no longer implied in ``prefix`` argument, must be included if
  this argument is passed.

:py:func:`git.checkout <salt.modules.git.checkout>`
***************************************************

- The ``rev`` argument is now optional when using ``-b`` or ``-B`` in ``opts``,
  allowing for a branch to be created (or reset) using ``HEAD`` as the starting
  point.

:py:func:`git.clone <salt.modules.git.clone>`
*********************************************

- The ``name`` argument has been added to specify the name of the directory in
  which to clone the repository. If this option is specified, then the clone
  will be made within the directory specified by the ``cwd``, instead of at
  that location.
- ``repository`` argument deprecated and renamed to ``url``

:py:func:`git.config_get <salt.modules.git.config_get>`
*******************************************************

- ``setting_name`` argument deprecated and renamed to ``key``
- The ``global`` argument has been added, to query the global git configuration
- The ``all`` argument has been added to return a list of all values for the
  specified key, allowing for all values in a multivar to be returned.
- ``cwd`` argument is now optional if ``global`` is set to ``True``

:py:func:`git.config_set <salt.modules.git.config_set>`
*******************************************************

- The value(s) of the key being set are now returned
- ``setting_name`` argument deprecated and renamed to ``key``
- ``setting_value`` argument deprecated and renamed to ``value``
- ``is_global`` argument deprecated and renamed to ``global``
- The ``multivar`` argument has been added to specify a list of values to set
  for the specified key. The ``value`` argument is not compatible with
  ``multivar``.
- The ``add`` argument has been added to add a value to a key (this essentially
  just adds an ``--add`` to the ``git config`` command that is run to set the
  value).

:py:func:`git.ls_remote <salt.modules.git.ls_remote>`
*****************************************************

- ``repository`` argument deprecated and renamed to ``remote``
- ``branch`` argument deprecated and renamed to ``ref``
- The ``opts`` argument has been added to allow for additional CLI options to
  be passed to the ``git ls-remote`` command.

:py:func:`git.merge <salt.modules.git.merge>`
*********************************************

- The ``branch`` argument deprecated and renamed to ``rev``

:py:func:`git.status <salt.modules.git.status>`
***********************************************

- Return data has been changed from a list of lists to a dictionary containing
  lists of files in the modified, added, deleted, and untracked states.

:py:func:`git.submodule <salt.modules.git.submodule>`
*****************************************************

- Added the ``command`` argument to allow for operations other than ``update``
  to be run on submodules, and deprecated the ``init`` argument. To do a
  submodule update with ``init=True`` moving forward, use ``command=update
  opts='--init'``


Git Pillar Rewritten
====================

The git external pillar has been rewritten to bring it up to feature parity
with :mod:`gitfs <salt.fileserver.gitfs>`. Support for pygit2_ has been added,
bring with it the ability to access authenticated repositories.

Using the new features will require updates to the git ext_pillar
configuration, further details can be found :ref:`here
<git-pillar-2015-8-0-and-later>`.

.. note::
    As with :mod:`gitfs <salt.fileserver.gitfs>`, pygit2_ 0.20.3 is required to
    use pygit2_ with the git external pillar.

Windows Software Repo Changes
=============================

Several config options have been renamed to make the naming more consistent.
For a list of the winrepo config options, see :ref:`here
<winrepo-config-opts>`.

The :mod:`winrepo.update_git_repos <salt.runners.winrepo.update_git_repos>`
runner has been updated to use either pygit2_ or GitPython_ to checkout the git
repositories containing repo data. If pygit2_ or GitPython_ is installed,
existing winrepo git checkouts should be removed after upgrading to 2015.8.0,
to allow them to be checked out again by running
:py:func:`winrepo.update_git_repos <salt.runners.winrepo.update_git_repos>`.

This enhancement also brings new functionality, see the :ref:`Windows Software
Repository <2015-8-0-winrepo-changes>` documentation for more information.

If neither GitPython_ nor pygit2_ are installed, then Salt will fall back to
the pre-existing behavior for :mod:`winrepo.update_git_repos
<salt.runners.winrepo.update_git_repos>`, and a warning will be logged in the
master log.

.. _pygit2: https://github.com/libgit2/pygit2
.. _GitPython: https://github.com/gitpython-developers/GitPython

JBoss 7 State
=============

Remove unused argument ``timeout`` in jboss7.status.

Pkgrepo State
=============

Deprecate ``enabled`` argument in ``pkgrepo.managed`` in favor of ``disabled``.

Archive Module
==============

In the ``archive.tar`` and ``archive.cmd_unzip`` module functions, remove the
arbitrary prefixing of the options string with ``-``.  An options string
beginning with a ``--long-option``, would have uncharacteristically needed its
first ``-`` removed under the former scheme.

Also, tar will parse its options differently if short options are used with or
without a preceding ``-``, so it is better to not confuse the user into
thinking they're using the non- ``-`` format, when really they are using the
with- ``-`` format.

Win System Module
=================

The unit of the ``timeout`` parameter in the ``system.halt``,
``system.poweroff``, ``system.reboot``,  and ``system.shutdown`` functions has
been changed from seconds to minutes in order to be consistent with the linux
timeout setting. (:issue:`24411`)  Optionally, the unit can be reverted to
seconds by specifying ``in_seconds=True``.

Deprecations
============

- The ``digital_ocean.py`` Salt Cloud driver was removed in favor of the
``digital_ocean_v2.py`` driver as DigitalOcean has removed support for APIv1.
The ``digital_ocean_v2.py`` was renamed to ``digital_ocean.py`` and supports
DigitalOcean's APIv2.

- The ``vsphere.py`` Salt Cloud driver has been deprecated in favor of the
``vmware.py`` driver.

- The ``openstack.py`` Salt Cloud driver has been deprecated in favor of the
``nova.py`` driver.

- The use of ``provider`` in Salt Cloud provider files to define cloud drivers
has been deprecated in favor of useing ``driver``. Both terms will work until
the Nitrogen release of Salt. Example provider file:

.. code-block:: yaml

    my-ec2-cloud-config:
      id: 'HJGRYCILJLKJYG'
      key: 'kdjgfsgm;woormgl/aserigjksjdhasdfgn'
      private_key: /etc/salt/my_test_key.pem
      keyname: my_test_key
      securitygroup: default
      driver: ec2

- The use of ``lock`` has been deprecated and from ``salt.utils.fopen``.
``salt.utils.flopen`` should be used instead.

- The following args have been deprecated from the ``rabbitmq_vhost.present``
state: ``user``, ``owner``, ``conf``, ``write``, ``read``, and ``runas``.

- The use of ``runas`` has been deprecated from the ``rabbitmq_vhost.absent``
state.

- Support for ``output`` in ``mine.get`` was removed. ``--out`` should be used
instead.

- The use of ``delim`` was removed from the following functions in the ``match``
execution module: ``pillar_pcre``, ``pillar``, ``grain_pcre``,

Known Issues
============

- The TCP transport does not function on FreeBSD.
