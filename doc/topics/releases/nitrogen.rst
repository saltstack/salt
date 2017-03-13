:orphan:

======================================
Salt Release Notes - Codename Nitrogen
======================================

States Added for Management of systemd Unit Masking
===================================================

The :py:func:`service.masked <salt.states.service.masked>` and
:py:func:`service.umasked <salt.states.service.unmasked>` states have been
added to allow Salt to manage masking of systemd units.

Additionally, the following functions in the :mod:`systemd
<salt.modules.systemd>` execution module have changed to accomodate the fact
that indefinite and runtime masks can co-exist for the same unit:

- :py:func:`service.masked <salt.modules.systemd.masked>` - The return from
  this function has changed from previous releases. Before, ``False`` would be
  returned if the unit was not masked, and the output of ``systemctl is-enabled
  <unit name>`` would be returned if the unit was masked. However, since
  indefinite and runtime masks can exist for the same unit at the same time,
  this function has been altered to accept a ``runtime`` argument. If ``True``,
  the minion will be checked for a runtime mask assigned to the named unit. If
  ``False``, then the minion will be checked for an indefinite mask. If one is
  found, ``True`` will be returned. If not, then ``False`` will be returned.
- :py:func:`service.masked <salt.modules.systemd.masked>` - This function used
  to just run ``systemctl is-enabled <unit name>`` and based on the return
  from this function the corresponding mask type would be removed. However, if
  both runtime and indefinite masks are set for the same unit, then ``systemctl
  is-enabled <unit name>`` would show just the indefinite mask. The indefinite
  mask would be removed, but the runtime mask would remain. The function has
  been modified to accept a ``runtime`` argument, and will attempt to remove a
  runtime mask if that argument is set to ``True``. If set to ``False``, it
  will attempt to remove an indefinite mask.

These new ``runtime`` arguments default to ``False``.

Pillar Encryption
=================

Beginning in 2016.3.0 the CLI pillar data passed to several functions could
conditionally be passed through a renderer to be decrypted. This functionality
has now been extended to pillar SLS files as well. See :ref:`here
<pillar-encryption>` for detailed documentation on this feature.

Grains Changes
==============

- The ``os_release`` grain has been changed from a string to an integer.
  State files, especially those using a templating language like Jinja
  may need to be adjusted to account for this change.
- Add ability to specify disk backing mode in the VMWare salt cloud profile.

State Module Changes
====================

- The :py:func:`service.running <salt.states.service.running>` and
  :py:func:`service.dead <salt.states.service.dead>` states now support a
  ``no_block`` argument which, when set to ``True`` on systemd minions, will
  start/stop the service using the ``--no-block`` flag in the ``systemctl``
  command. On non-systemd minions, a warning will be issued.

- The :py:func:`module.run <salt.states.module.run>` state has dropped its previous
  syntax with ``m_`` prefix for reserved keywords. Additionally, it allows
  running several functions in a batch.

.. note::
    It is nesessary to explicitly turn on the new behaviour (see below)

  Before and after:

.. code-block:: yaml

    # Before
    run_something:
      module.run:
        - name: mymodule.something
        - m_name: 'some name'
        - kwargs: {
          first_arg: 'one',
          second_arg: 'two',
          do_stuff: 'True'
        }

    # After
    run_something:
      module.run:
        mymodule.something:
          - name: some name
          - first_arg: one
          - second_arg: two
          - do_stuff: True

- Previous behaviour of the function :py:func:`module.run <salt.states.module.run>` is
  still kept by default and can be bypassed in case you want to use behaviour above.
  Please keep in mind that the old syntax will no longer be supported in the ``Oxygen``
  release of Salt. To enable the new behavior, add the following to the minion config file:


.. code-block:: yaml

    use_superseded:
      - module.run



Execution Module Changes
========================

- Several functions in the :mod:`systemd <salt.modules.systemd>` execution
  module have gained a ``no_block`` argument, which when set to ``True`` will
  use ``--no-block`` in the ``systemctl`` command.
- In the :mod:`solarisips <salt.modules.solarisips>` ``pkg`` module, the
  default value for the ``refresh`` argument to the ``list_upgrades`` function
  has been changed from ``False`` to ``True``. This makes the function more
  consistent with all of the other ``pkg`` modules (The other
  ``pkg.list_upgrades`` functions all defaulted to ``True``).
- The functions which handle masking in the :mod:`systemd
  <salt.modules.systemd>` module have changed. These changes are described
  above alongside the information on the new states which have been added to
  manage masking of systemd units.
- The :py:func:`pkg.list_repo_pkgs <salt.modules.yumpkg.list_repo_pkgs>`
  function for yum/dnf-based distros has had its default output format changed.
  In prior releases, results would be organized by repository. Now, the default
  for each package will be a simple list of versions. To get the old behavior,
  pass ``byrepo=True`` to the function.
- A ``pkg.list_repo_pkgs`` function has been added for both
  :py:func:`Debian/Ubuntu <salt.modules.aptpkg.list_repo_pkgs>` and
  :py:func:`Arch Linux <salt.modules.pacman.list_repo_pkgs>`-based distros.

Wildcard Versions in :py:func:`pkg.installed <salt.states.pkg.installed>` States
================================================================================

The :py:func:`pkg.installed <salt.states.pkg.installed>` state now supports
wildcards in package versions, for the following platforms:

- Debian/Ubuntu
- RHEL/CentOS
- Arch Linux

This support also extends to any derivatives of these distros, which use the
:mod:`aptpkg <salt.modules.aptpkg>`, :mod:`yumpkg <salt.modules.yumpkg>`, or
:mod:`pacman <salt.modules.pacman>` providers for the ``pkg`` virtual module.

Using wildcards can be useful for packages where the release name is built into
the version in some way, such as for RHEL/CentOS which typically has version
numbers like ``1.2.34-5.el7``. An example of the usage for this would be:

.. code-block:: yaml

    mypkg:
      pkg.installed:
        - version: '1.2.34*'

- The :mod:`system <salt.modules.system>` module changed the returned format
  from "HH:MM AM/PM" to "HH:MM:SS AM/PM" for `get_system_time`.

Master Configuration Additions
==============================

- :conf_master:`syndic_forward_all_events` - Option on multi-syndic or single
  when connected to multiple masters to be able to send events to all connected
  masters.

Minion Configuration Additions
==============================

- :conf_minion:`pillarenv_from_saltenv` - When set to ``True`` (default is
  ``False``), the :conf_minion:`pillarenv` option will take the same value as
  the effective saltenv when running states. This would allow a user to run
  ``salt '*' state.apply mysls saltenv=dev``, and the SLS for both the state
  and pillar data would be sourced from the ``dev`` environment, essentially
  the equivalent of running ``salt '*' state.apply mysls saltenv=dev
  pillarenv=dev``. Note that if :conf_minion:`pillarenv` is set in the minion
  config file, or if ``pillarenv`` is provided on the CLI, it will override
  this option.

Python API Changes
==================

The :ref:`LocalClient <local-client>`'s ``expr_form`` argument has been
deprecated and renamed to ``tgt_type``. This change was made due to numerous
reports of confusion among community members, since the targeting method is
published to minions as ``tgt_type``, and appears as ``tgt_type`` in the job
cache as well.

While ``expr_form`` will continue to be supported until the **Fluorine**
release cycle (two major releases after this one), those who are using the
:ref:`LocalClient <local-client>` (either directly, or implictly via a
:ref:`netapi module <all-netapi-modules>`) are encouraged to update their code
to use ``tgt_type``.

Custom Refspecs in GitFS / git_pillar / winrepo
===============================================

It is now possible to specify the refspecs to use when fetching from remote
repositories for GitFS, git_pillar, and winrepo. More information on how this
feature works can be found :ref:`here <gitfs-custom-refspecs>` in the GitFS
Walkthrough. The git_pillar and winrepo versions of this feature work the same
as their GitFS counterpart.

git_pillar "mountpoints" Feature Added
======================================

See :ref:`here <git-pillar-mountpoints>` for detailed documentation.

Big Improvements to Docker Support
==================================

The old ``docker`` state and execution modules have been moved to
salt-contrib_. The ``dockerng`` execution module has been renamed to
:mod:`docker <salt.modules.docker>` and now serves as Salt's official Docker
execution module.

The old ``dockerng`` state module has been split into 4 state modules:

- :mod:`docker_container <salt.states.docker_container>` - States to manage
  Docker containers
- :mod:`docker_image <salt.states.docker_image>` - States to manage Docker
  images
- :mod:`docker_volume <salt.states.docker_volume>` - States to manage
  Docker volumes
- :mod:`docker_network <salt.states.docker_network>` - States to manage
  Docker networks

The reason for this change was to make states and requisites more clear. For
example, imagine this SLS:

.. code-block:: yaml

    myuser/appimage:
      docker.image_present:
        - sls: docker.images.appimage

    myapp:
      docker.running:
        - image: myuser/appimage
        - require:
          - docker: myuser/appimage

The new syntax would be:

.. code-block:: yaml

    myuser/appimage:
      docker_image.present:
        - sls: docker.images.appimage

    myapp:
      docker_container.running:
        - image: myuser/appimage
        - require:
          - docker_image: myuser/appimage

This is similar to how Salt handles MySQL, MongoDB, Zabbix, and other cases
where the same execution module is used to manage several different kinds
of objects (users, databases, roles, etc.).

The old syntax will continue to work until the **Fluorine** release of Salt.
The old ``dockerng`` naming will also continue to work until that release, so
no immediate changes need to be made to your SLS files (unless you were still
using the old docker states that have been moved to salt-contrib_).

The :py:func:`docker_container.running <salt.states.docker_container.running>`
state has undergone a significant change in how it determines whether or not a
container needs to be replaced. Rather than comparing individual arguments to
their corresponding values in the named container, a temporary container is
created using the passed arguments. The two containers are then compared to
each other to determine whether or not there are changes.

Salt still needs to translate arguments into the format which docker-py
expects, but if it does not properly do so, the :ref:`skip_translate
<docker-container-running-skip-translate>` argument can be used to skip input
translation on an argument-by-argument basis, and you can then format your SLS
file to pass the data in the format that the docker-py expects. This allows you
to work around any changes in Docker's API or issues with the input
translation, and continue to manage your Docker containers using Salt. Read the
documentation for :ref:`skip_translate
<docker-container-running-skip-translate>` for more information.

.. _salt-contrib: https://github.com/saltstack/salt-contrib

New SSH Cache Roster
====================

The :mod:`SSH cache Roster <salt.roster.cache>` has been rewritten from scratch to increase its usefulness.
The new roster supports all minion matchers, so it is now possible to target minions identically through `salt` and `salt-ssh`.
The new configuration syntax allows for flexible combinations of arbitrary grains, pillar and mine data.
This applies not just for the `host` of a minion, but also for other configuration data.
The new release is also fully IPv4 and IPv6 enabled and even allows for the selection of certain CIDR ranges for connecting.

Deprecations
============

General Deprecations
--------------------

- Removed support for aliasing ``cmd.run`` to ``cmd.shell``.
- Removed support for Dulwich from :ref:`GitFS <tutorial-gitfs>`.
- Beacon configurations should be lists instead of dictionaries.
- The ``PidfileMixin`` has been removed. Please use ``DaemonMixIn`` instead.
- The ``use_pending`` argument was removed from the ``salt.utils.event.get_event``
  function.
- The ``pending_tags`` argument was removed from the ``salt.utils.event.get_event``
  function.

Configuration Option Deprecations
---------------------------------

- The ``client_acl`` configuration option has been removed. Please use
  ``publisher_acl`` instead.
- The ``client_acl_blacklist`` configuration option has been removed.
  Please use ``publisher_acl_blacklist`` instead.
- The ``win_gitrepos`` configuration option has been removed. Please use
  the ``winrepo_remotes`` option instead.
- The ``win_repo`` configuration option has been removed. Please use
  ``winrepo_dir`` instead.
- The ``win_repo_mastercachefile`` configuration option has been removed.
  Please use the ``winrepo_cachefile`` option instead.

Module Deprecations
-------------------

The ``git`` execution module had the following changes:

- The ``fmt`` argument was removed from the ``archive`` function. Please
  use ``format`` instead.
- The ``repository`` argument was removed from the ``clone`` function.
  Please use ``url`` instead.
- The ``is_global`` argument was removed from the ``config_set`` function.
  Please use ``global`` instead.
- The ``branch`` argument was removed from the ``merge`` function. Please
  use ``rev`` instead.
- The ``branch`` argument was removed from the ``push`` function. Please
  use ``rev`` instead.

The ``glusterfs`` execution module had the following functions removed:

- ``create``: Please use ``create_volume`` instead.
- ``delete``: Please use ``delete_volume`` instead.
-  ``list_peers``: Please use ``peer_status`` instead.

The ``htpasswd`` execution module had the following function removed:

- ``useradd_all``: Please use ``useradd`` instead.

The ``img`` execution module has been removed. All of its associated functions
were marked for removal in the Nitrogen release. The functions removed in this
module are mapped as follows:

- ``mount_image``/``mnt_image``: Please use ``mount.mount`` instead.
- ``umount_image``: Please use ``mount.umount`` instead.
- ``bootstrap``: Please use ``genesis.bootstrap`` instead.

The ``smartos_virt`` execution module had the following functions removed:

- ``create``: Please use ``start`` instead.
- ``destroy`` Please use ``stop`` instead.
- ``list_vms``: Please use ``list_domains`` instead.

The ``virt`` execution module had the following functions removed:

- ``create``: Please use ``start`` instead.
- ``destroy`` Please use ``stop`` instead.
- ``list_vms``: Please use ``list_domains`` instead.

The ``virtualenv_mod`` execution module had the following changes:

- The ``package_or_requirement`` argument was removed from both the
  ``get_resource_path`` and the ``get_resource_content`` functions.
  Please use ``package`` instead.
- The ``resource_name`` argument was removed from both the
  ``get_resource_path`` and ``get_resource_content`` functions.
  Please use ``resource`` instead.

The ``win_repo`` execution module had the following changes:

- The ``win_repo_source_dir`` option was removed from the ``win_repo``
  module. Please use ``winrepo_source_dir`` instead.

The ``xapi`` execution module had the following functions removed:

- ``create``: Please use ``start`` instead.
- ``destroy``: Please use ``stop`` instead.
- ``list_vms``: Please use ``list_domains`` instead.

The ``zypper`` execution module had the following function removed:

- ``info``: Please use ``info_available`` instead.

Pillar Deprecations
-------------------

- Support for the ``raw_data`` argument for the file_tree ext_pillar has been
  removed. Please use ``keep_newline`` instead.
- SQLite3 database connection configuration previously had keys under
  pillar. This legacy compatibility has been removed.

Proxy Minion Deprecations
-------------------------

- The ``proxy_merge_grains_in_module`` default has been switched from
  ``False`` to ``True``.

Salt-API Deprecations
---------------------

- The ``SaltAPI.run()`` function has been removed. Please use the
  ``SaltAPI.start()`` function instead.

Salt-Cloud Deprecations
-----------------------

- Support for using the keyword ``provider`` in salt-cloud provider config
  files has been removed. Please use ``driver`` instead. The ``provider``
  keyword should now only be used in cloud profile config files.

Salt-SSH Deprecations
---------------------

- The ``wipe_ssh`` option for ``salt-ssh`` has been removed. Please use the
  ``ssh_wipe`` option instead.

State Deprecations
------------------

The ``apache_conf`` state had the following functions removed:

  - ``disable``: Please use ``disabled`` instead.
  - ``enable``: Please use ``enabled`` instead.

The ``apache_module`` state had the following functions removed:

  - ``disable``: Please use ``disabled`` instead.
  - ``enable``: Please use ``enabled`` instead.

The ``apache_site`` state had the following functions removed:

  - ``disable``: Please use ``disabled`` instead.
  - ``enable``: Please use ``enabled`` instead.

The ``chocolatey`` state had the following functions removed:

  - ``install``: Please use ``installed`` instead.
  - ``uninstall``: Please use ``uninstalled`` instead.

The ``git`` state had the following changes:

  - The ``config`` function was removed. Please use ``config_set`` instead.
  - The ``is_global`` option was removed from the ``config_set`` function.
    Please use ``global`` instead.
  - The ``always_fetch`` option was removed from the ``latest`` function, as
    it no longer has any effect. Please see the :ref:`2015.8.0<release-2015-8-0>`
    release notes for more information.
  - The ``force`` option was removed from the ``latest`` function. Please
    use ``force_clone`` instead.
  - The ``remote_name`` option was removed from the ``latest`` function.
    Please use ``remote`` instead.

The ``glusterfs`` state had the following function removed:

  - ``created``: Please use ``volume_present`` instead.

The ``openvswitch_port`` state had the following change:

  - The ``type`` option was removed from the ``present`` function. Please use ``tunnel_type`` instead.
