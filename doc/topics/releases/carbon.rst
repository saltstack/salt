:orphan:

====================================
Salt Release Notes - Codename Carbon
====================================

New Features
============

Docker Introspection and Configuration
--------------------------------------

Major additions have been made to the Docker support in Carbon. The new
addition allows Salt to be executed within a Docker container without a
minion running or installed in the container. This allows states to
be run inside a container, but also all of Salt's remote execution
commands to be run inside docker containers as well. This makes
container introspection simple and powerful. See the tutorial on using
this new feature here:

#TODO: Add link to docker sls tutorial

Advanced Ceph Control
---------------------

Our friends over at SUSE have delivered a powerful new tool to make the
deployment of Ceph storage systems using Salt very easy. These new Ceph
tools allow for a storage system to be easily defined using the new
`ceph.quorum` state.

Thorium Additions and Improvements
----------------------------------

The Thorium advanced reactor has undergone extensive testing and updates.
These updates include many more Thorium states, a system for automating
key management, the ability to use Thorium to easily replace old
reactors and a great deal of stability and bug fixes.

State Rollback Using Snapper
----------------------------

Rollback has been one of the most prevalent requests for Salt. We
have researched it extensively and concluded that the only way to
accomplish truly reliable rollback would be to execute it at
the filesystem layer. To accomplish this we have introduced Snapper
integration into Salt States.

Snapper is a tool which allows for simple and reliable snapshots
of the filesystem to be made. With the new `snapper_states` option
set to `True` in the minion config a snapshot will be made before
and after every Salt State run.

These snapshots can be viewed, managed and rolled back to via the
`snapper` execution module.

Preserve File Perms in File States
----------------------------------

This feature has been requested for years, the ability to set a flag
and use the same file permissions for files deployed to a minion as
the permissions set to the file on the master. Just set the `keep_mode`
option on any file management state to `True`.

Ponies!
-------

We all agreed that cowsay was just not good enough, install the `ponysay`
command and the new `pony` outputter will work. For for the whole family!

Additional Features
-------------------

- Minions can run in stand-alone mode to use beacons and engines without
  having to connect to a master. (Thanks @adelcast!)
- Added a ``salt`` runner to allow running salt modules via salt-run.

    .. code-block:: bash

        salt-run salt.cmd test.ping
        # call functions with arguments and keyword arguments
        salt-run salt.cmd test.arg 1 2 3 a=1
- Added SSL support to Cassandra CQL returner.
  SSL can be enabled by setting ``ssl_options`` for the returner.
  Also added support for specifying ``protocol_version`` when establishing
  cluster connection.
- The ``mode`` parameter in the :py:mod:`file.managed
  <salt.states.file.managed>` state, and the ``file_mode`` parameter in the
  :py:mod:`file.recurse <salt.states.file.recurse>` state, can both now be set
  to ``keep`` and the minion will keep the mode of the file from the Salt
  fileserver. This works only with files coming from sources prefixed with
  ``salt://``, or files local to the minion (i.e. those which are absolute
  paths, or are prefixed with ``file://``). For example:

  .. code-block:: yaml

      /etc/myapp/myapp.conf:
        file.managed:
          - source: salt://conf/myapp/myapp.conf
          - mode: keep

      /var/www/myapp:
        file.recurse:
          - source: salt://path/to/myapp
          - dir_mode: 755
          - file_mode: keep
          
- The ``junos`` state module is now available. It has all the functions 
  that are present in the ``junos`` execution module.

Config Changes
==============

The following default config values were changed:

- ``gitfs_ssl_verify``: Changed from ``False`` to ``True``
- ``git_pillar_ssl_verify``: Changed from ``False`` to ``True``
- ``winrepo_ssl_verify``: Changed from ``False`` to ``True``

Grains Changes
==============

- All core grains containing ``VMWare`` have been changed to ``VMware``, which
  is the `official capitalization <https://www.vmware.com>`_.  Additionally,
  all references to ``VMWare`` in the documentation have been changed to
  ``VMware`` :issue:`30807`.  Environments using versions of Salt before and
  after Salt Carbon should employ case-insensitive grain matching on these
  grains.

  .. code-block:: jinja

      {% set on_vmware = grains['virtual'].lower() == 'vmware' %}


- On Windows the ``cpu_model`` grain has been changed to provide the actual cpu
  model name and not the cpu family.

  Old behavior:

  .. code-block:: bash

      root@master:~# salt 'testwin200' grains.item cpu_model
      testwin200:
          ----------
          cpu_model:
              Intel64 Family 6 Model 58 Stepping 9, GenuineIntel

  New behavior:

  .. code-block:: bash

      root@master:~# salt 'testwin200' grains.item cpu_model
      testwin200:
          ----------
          cpu_model:
              Intel(R) Core(TM) i7-3520M CPU @ 2.90GHz


Beacons Changes
===============

- The ``loadavg`` beacon now outputs averages as integers instead of strings.
  (Via :issuse:`31124`.)

Runner Changes
==============

- Runners can now call out to :ref:`utility modules <writing-utility-modules>`
  via ``__utils__``.
- ref:`Utility modules <writing-utility-modules>` (placed in
  ``salt://_utils/``) are now able to be synced to the master, making it easier
  to use them in custom runners. A :py:mod:`saltutil.sync_utils
  <salt.runners.saltutil.sync_utils>` function has been added to the
  :py:mod:`saltutil runner <salt.runners.saltutil>` to faciliate the syncing of
  utility modules to the master.

Pillar Changes
==============

- Thanks to the new :py:mod:`saltutil.sync_utils
  <salt.runners.saltutil.sync_utils>` runner, it is now easier to get
  ref:`utility modules <writing-utility-modules>` synced to the correct
  location on the Master so that they are available in execution modules called
  from Pillar SLS files.
  
Junos Module Changes
===================

- The following new functionalities were added to the junos module

  - facts - Displays the facts gathered during the connection.
  - shutdown - Shut down or reboot a device running Junos OS.
  - install_config - Modify the configuration of a Junos device.
  - install_os - Install Junos OS software package.
  - zeroize - Remove all configuration information on the Routing Engines and reset all key values on a device.
  - file_copy - Copy file from proxy to the Junos device.

Returner Changes
================

- Any returner which implements a `save_load` function is now required to
  accept a `minions` keyword argument. All returners which ship with Salt
  have been modified to do so.

External Module Packaging
=========================

Modules may now be packaged via entry-points in setuptools. See
:doc:`external module packaging </topics/tutorials/packaging_modules>` tutorial
for more information.

Functionality Changes
=====================

- The ``onfail`` requisite now uses OR logic instead of AND logic.
  :issue:`22370`
- The consul external pillar now strips leading and trailing whitespace.
  :issue:`31165`
- The win_system.py state is now case sensitive for computer names. Previously
  computer names set with a state were converted to all caps. If you have a
  state setting computer names with lower case letters in the name that has
  been applied, the computer name will be changed again to apply the case
  sensitive name.
- The ``mac_user.list_groups`` function in the ``mac_user`` execution module
  now lists all groups for the specified user, including groups beginning with
  an underscore. In previous releases, groups beginning with an underscore were
  excluded from the list of groups.
- The ``junos.call_rpc`` function in the ``junos`` execution module can now be used
  to call any valid rpc. Earlier it used to call only "get_software_information".
- A new option for minions called ``master_tries`` has been added. This
  specifies the number of times a minion should attempt to contact a master to
  attempt a connection.  This allows better handling of occasional master
  downtime in a multi-master topology.
- Nodegroups consisting of a simple list of minion IDs can now also be declared
  as a yaml list. The below two examples are equivalent:

  .. code-block:: yaml

      # Traditional way
      nodegroups:
        - group1: L@host1,host2,host3

      # New way (optional)
      nodegroups:
        - group1:
          - host1
          - host2
          - host3

Deprecations
============

General Deprecations
--------------------

- ``env`` to ``saltenv``

  All occurrences of ``env`` and some occurrences of ``__env__`` marked for
  deprecation in Salt Carbon have been removed.  The new way to use the salt
  environment setting is with a variable called ``saltenv``:

  .. code-block:: python

    def fcn(msg='', env='base', refresh=True, saltenv='base', **kwargs):

  has been changed to

  .. code-block:: python

    def fcn(msg='', refresh=True, saltenv='base', **kwargs):

  - If ``env`` (or ``__env__``) is supplied as a keyword argument to a function
    that also accepts arbitrary keyword arguments, then a new warning informs the
    user that ``env`` is no longer used if it is found.  This new warning will be
    removed in Salt Nitrogen.

    .. code-block:: python

      def fcn(msg='', refresh=True, saltenv='base', **kwargs):

    .. code-block:: python

      # will result in a warning log message
      fcn(msg='add more salt', env='prod', refresh=False)

  - If ``env`` (or ``__env__``) is supplied as a keyword argument to a function
    that does not accept arbitrary keyword arguments, then python will issue an
    error.

    .. code-block:: python

      def fcn(msg='', refresh=True, saltenv='base'):

    .. code-block:: python

      # will result in a python TypeError
      fcn(msg='add more salt', env='prod', refresh=False)

  - If ``env`` (or ``__env__``) is supplied as a positional argument to a
    function, then undefined behavior will occur, as the removal of ``env`` and
    ``__env__`` from the function's argument list changes the function's
    signature.

    .. code-block:: python

      def fcn(msg='', refresh=True, saltenv='base'):

    .. code-block:: python

      # will result in refresh evaluating to True and saltenv likely not being a string at all
      fcn('add more salt', 'prod', False)

- Deprecations in ``minion.py``:

  - The ``salt.minion.parse_args_and_kwargs`` function has been removed. Please
  use the ``salt.minion.load_args_and_kwargs`` function instead.

Cloud Deprecations
------------------

- The ``vsphere`` cloud driver has been removed. Please use the ``vmware`` cloud driver
  instead.

- The ``private_ip`` option in the ``linode`` cloud driver is deprecated and has been
  removed. Use the ``assign_private_ip`` option instead.

- The ``create_dns_record`` and ``delete_dns_record`` functions are deprecated and have
  been removed from the ``digital_ocean`` driver. Use the ``post_dns_record`` function
  instead.


Execution Module Deprecations
-----------------------------

- The ``blockdev`` execution module had four functions removed:

  - dump
  - tune
  - resize2fs
  - wipe

  The ``disk`` module should be used instead with the same function names.

- The ``boto_vpc`` execution module had two functions removed,
  ``boto_vpc.associate_new_dhcp_options_to_vpc`` and
  ``boto_vpc.associate_new_network_acl_to_subnet`` in favor of more concise function
  names, ``boto_vpc.create_dhcp_options`` and ``boto_vpc.create_network_acl``, respectively.

- The ``data`` execution module had ``getval`` and ``getvals`` functions removed
  in favor of one function, ``get``, which combines the functionality of the
  removed functions.

- File module deprecations:

  - The ``contains_regex_multiline`` function was removed. Use ``file.search`` instead.
  - Additional command line options for ``file.grep`` should be passed one at a time.
    Please do not pass more than one in a single argument.

- The ``lxc`` execution module has the following changes:

  - The ``run_cmd`` function was removed. Use ``lxc.run`` instead.
  - The ``nic`` argument was removed from the ``lxc.init`` function. Use ``network_profile``
    instead.
  - The ``clone`` argument was removed from the ``lxc.init`` function. Use ``clone_from``
    instead.
  - passwords passed to the ``lxc.init`` function will be assumed to be hashed, unless
    ``password_encrypted=False``.
  - The ``restart`` argument for ``lxc.start`` was removed. Use ``lxc.restart`` instead.
  - The old style of defining lxc containers has been removed. Please use keys under which
    LXC profiles should be configured such as ``lxc.container_profile.profile_name``.

- The ``env`` and ``activate`` keyword arguments have been removed from the ``install``
  function in the ``pip`` execution module. The use of ``bin_env`` replaces both of these
  options.

- ``reg`` execution module

  Functions in the ``reg`` execution module had misleading and confusing names
  for dealing with the Windows registry. They failed to clearly differentiate
  between hives, keys, and name/value pairs. Keys were treated like value names.
  There was no way to delete a key.

  New functions were added in 2015.5 to properly work with the registry. They
  also made it possible to edit key default values as well as delete an entire
  key tree recursively. With the new functions in place, the following functions
  have been deprecated:

  - read_key
  - set_key
  - create_key
  - delete_key

  Use the following functions instead:

  - for ``read_key`` use ``read_value``
  - for ``set_key`` use ``set_value``
  - for ``create_key`` use ``set_value`` with no ``vname`` and no ``vdata``
  - for ``delete_key`` use ``delete_key_recursive``. To delete a value, use
    ``delete_value``.

- The ``hash_hostname`` option was removed from the ``salt.modules.ssh`` execution
  module. The ``hash_known_hosts`` option should be used instead.

- The ``human_readable`` option was removed from the ``uptime`` function in the
  ``status`` execution module. The function was also updated in 2015.8.9 to return
  a more complete offering of uptime information, formatted as an easy-to-read
  dictionary. This updated function replaces the need for the ``human_readable``
  option.

- The ``persist`` kwarg was removed from the ``win_useradd`` execution module. This
  option is no longer supported for Windows. ``persist`` is only supported as part
  of user management in UNIX/Linux.

- The ``zpool_list`` function in the ``zpool`` execution module was removed. Use ``list``
  instead.


Outputter Module Deprecations
-----------------------------

- The ``compact`` outputter has been removed. Set ``state_verbose`` to ``False`` instead.


Runner Module Deprecations
--------------------------

- The ``grains.cache`` runner no longer accepts ``outputter`` or ``minion`` as keyword arguments.
  Users will need to specify an outputter using the ``--out`` option. ``tgt`` is
  replacing the ``minion`` kwarg.

- The ``fileserver`` runner no longer accepts the ``outputter`` keyword argument. Users will
  need to specify an outputter using the ``--out`` option.

- The ``jobs`` runner no longer accepts the ``ouputter`` keyword argument. Users will need to
  specify an outputter using the ``--out`` option.

- ``virt`` runner module:

  - The ``hyper`` kwarg was removed from the ``init``, ``list``, and ``query`` functions.
    Use the ``host`` option instead.
  - The ``next_hyper`` function was removed. Use the ``next_host`` function instead.
  - The ``hyper_info`` function was removed. Use the ``host_info`` function instead.


State Module Deprecations
-------------------------

- The ``env`` and ``activate`` keyword arguments were removed from the ``installed``
  function in the ``pip`` state module. The use of ``bin_env`` replaces both of these
  options.

- ``reg`` state module

  The ``reg`` state module was modified to work with the new functions in the
  execution module. Some logic was left in the ``reg.present`` and the
  ``reg.absent`` functions to handle existing state files that used the final
  key in the name as the value name. That logic has been removed so you now must
  specify value name (``vname``) and, if needed, value data (``vdata``).

  For example, a state file that adds the version value/data pair to the
  Software\\Salt key in the HKEY_LOCAL_MACHINE hive used to look like this:

  .. code-block:: yaml

      HKEY_LOCAL_MACHINE\\Software\\Salt\\version:
        reg.present:
          - value: 2016.3.1

  Now it should look like this:

  .. code-block:: yaml

      HKEY_LOCAL_MACHINE\\Software\\Salt
        reg.present:
          - vname: version
          - vdata: 2016.3.1

  A state file for removing the same value added above would have looked like
  this:

  .. code-block:: yaml

      HKEY_LOCAL_MACHINE\\Software\\Salt\\version:
        reg.absent:

  Now it should look like this:

  .. code-block:: yaml

      HKEY_LOCAL_MACHINE\\Software\\Salt
        reg.absent:
          - vname: version

  This new structure is important as it allows salt to deal with key default
  values which was not possible before. If vname is not passed, salt will work
  with the default value for that hive\key.

  Additionally, since you could only delete a value from a the state module, a
  new function (``key_absent``) has been added to allow you to delete a registry
  key and all subkeys and name/value pairs recursively. It uses the new
  ``delete_key_recursive`` function.

  For additional information see the documentation for the ``reg`` execution and
  state modules.

- ``lxc`` state module: The following functions were removed from the ``lxc`` state
  module:

  - ``created``: replaced by the ``present`` state.
  - ``started``: replaced by the ``running`` state.
  - ``cloned``: replaced by the ``present`` state. Use the ``clone_from`` argument
    to set the name of the clone source.

- The ``hash_hostname`` option was removed from the ``salt.states.ssh_known_hosts``
  state. The ``hash_known_hosts`` option should be used instead.

- The ``always`` kwarg used in the ``built`` function of the ``pkgbuild`` state module
  was removed. Use ``force`` instead.


Utils Module Deprecations
-------------------------

- The use of ``jid_dir`` and ``jid_load`` were removed from the
  ``salt.utils.jid``. ``jid_dir`` functionality for job_cache management was moved to
  the ``local_cache`` returner. ``jid_load`` data is now retrieved from the
  ``master_job_cache``.

- ``ip_in_subnet`` function in ``salt.utils.network.py`` has been removed. Use the
  ``in_subnet`` function instead.

- The ``iam`` utils module had two functions removed: ``salt.utils.iam.get_iam_region``
  and ``salt.utils.iam.get_iam_metadata`` in favor of the aws utils functions
  ``salt.utils.aws.get_region_from_metadata`` and ``salt.utils.aws.creds``, respectively.
