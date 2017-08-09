:orphan:

====================================
Salt Release Notes - Codename Oxygen
====================================

Comparison Operators in Package Installation
--------------------------------------------

Salt now supports using comparison operators (e.g. ``>=1.2.3``) when installing
packages on minions which use :mod:`yum/dnf <salt.modules.yumpkg>` or :mod:`apt
<salt.modules.aptpkg>`. This is supported both in the :py:func:`pkg.installed
<salt.states.pkg.installed>` state and in the ``pkg.install`` remote execution
function.

:ref:`Master Tops <master-tops-system>` Changes
-----------------------------------------------

When both :ref:`Master Tops <master-tops-system>` and a :ref:`Top File
<states-top>` produce SLS matches for a given minion, the matches were being
merged in an unpredictable manner which did not preserve ordering. This has
been changed. The top file matches now execute in the expected order, followed
by any master tops matches that are not matched via a top file.

To make master tops matches execute first, followed by top file matches, set
the new :conf_minion:`master_tops_first` minion config option to ``True``.

LDAP via External Authentication Changes
----------------------------------------
In this release of Salt, if LDAP Bind Credentials are supplied, then
these credentials will be used for all LDAP access except the first
authentication when a job is submitted.  The first authentication will
use the user's credentials as passed on the CLI.  This behavior is to
accommodate certain two-factor authentication schemes where the authentication
token can only be used once.

In previous releases the bind credentials would only be used to determine
the LDAP user's existence and group membership.  The user's LDAP credentials
were used from then on.

New GitFS Features
------------------

Two new features which affect how GitFS maps branches/tags to fileserver
environments (i.e. ``saltenvs``) have been added:

1. It is now possible to completely turn off Salt's default mapping logic
   (aside from the mapping of the ``base`` saltenv). This can be triggered
   using the new :conf_master:`gitfs_disable_saltenv_mapping` config option.

   .. note::
       When this is disabled, only the ``base`` saltenv and any configured
       using :ref:`per-saltenv configuration parameters
       <gitfs-per-saltenv-config>` will be available.

2. The types of refs which Salt will use as saltenvs can now be controlled. In
   previous releases, branches and tags were both mapped as environments, and
   individual commit SHAs could be specified as saltenvs in states (and when
   caching files using :py:func:`cp.cache_file <salt.modules.cp.cache_file>`).
   Using the new :conf_master:`gitfs_ref_types` config option, the types of
   refs which are used as saltenvs can be restricted. This makes it possible to
   ignore all tags and use branches only, and also to keep SHAs from being made
   available as saltenvs.

Salt Cloud Features
===================

Pre-Flight Commands
-------------------

Support has been added for specified "preflight commands" to run on a VM before
the deploy script is run. These must be defined as a list in a cloud configuration
file. For example:

.. code-block:: yaml

       my-cloud-profile:
         provider: linode-config
         image: Ubuntu 16.04 LTS
         size: Linode 2048
         preflight_cmds:
           - whoami
           - echo 'hello world!'

These commands will run in sequence **before** the bootstrap script is executed.

Newer PyWinRM Versions
----------------------

Versions of ``pywinrm>=0.2.1`` are finally able to disable validation of self
signed certificates.  :ref:`Here<new-pywinrm>` for more information.

Solaris Logical Domains In Virtual Grain
----------------------------------------

Support has been added to the ``virtual`` grain for detecting Solaris LDOMs
running on T-Series SPARC hardware.  The ``virtual_subtype`` grain is 
populated as a list of domain roles.


Deprecations
============

Configuration Option Deprecations
---------------------------------

- The ``requests_lib`` configuration option has been removed. Please use
  ``backend`` instead.

Profitbricks Cloud Updated Dependency
-------------------------------------

The minimum version of the `profitbrick` python package for the `profitbricks`
cloud driver has changed from 3.0.0 to 3.1.0.

Module Deprecations
-------------------

The ``blockdev`` execution module has been removed. Its functions were merged
with the ``disk`` module. Please use the ``disk`` execution module instead.

The ``lxc`` execution module had the following changes:

- The ``dnsservers`` option to the ``cloud_init_interface`` function no longer
  defaults to ``4.4.4.4`` and ``8.8.8.8``.
- The ``dns_via_dhcp`` option to the ``cloud_init_interface`` function defaults
  to ``True`` now instead of ``False``.

The ``win_psget`` module had the following changes:

- The ``psversion`` function was removed. Please use ``cmd.shell_info`` instead.

The ``win_service`` module had the following changes:

- The ``config`` function was removed. Please use the ``modify`` function
  instead.
- The ``binpath`` option was removed from the ``create`` function. Please use
  ``bin_path`` instead.
- The ``depend`` option was removed from the ``create`` function. Please use
  ``dependencies`` instead.
- The ``DisplayName`` option was removed from the ``create`` function. Please
  use ``display_name`` instead.
- The ``error`` option was removed from the ``create`` function. Please use
  ``error_control`` instead.
- The ``group`` option was removed from the ``create`` function. Please use
  ``load_order_group`` instead.
- The ``obj`` option was removed from the ``create`` function. Please use
  ``account_name`` instead.
- The ``password`` option was removed from the ``create`` function. Please use
  ``account_password`` instead.
- The ``start`` option was removed from the ``create`` function. Please use
  ``start_type`` instead.
- The ``type`` option was removed from the ``create`` function. Please use
  ``service_type`` instead.

Runner Deprecations
-------------------

The ``manage`` runner had the following changes:

- The ``root_user`` kwarg was removed from the ``bootstrap`` function. Please
  use ``salt-ssh`` roster entries for the host instead.

State Deprecations
------------------

The ``archive`` state had the following changes:

- The ``tar_options`` and the ``zip_options`` options were removed from the
  ``extracted`` function. Please use ``options`` instead.

The ``cmd`` state had the following changes:

- The ``user`` and ``group`` options were removed from the ``run`` function.
  Please use ``runas`` instead.
- The ``user`` and ``group`` options were removed from the ``script`` function.
  Please use ``runas`` instead.
- The ``user`` and ``group`` options were removed from the ``wait`` function.
  Please use ``runas`` instead.
- The ``user`` and ``group`` options were removed from the ``wait_script``
  function. Please use ``runas`` instead.

The ``file`` state had the following changes:

- The ``show_diff`` option was removed. Please use ``show_changes`` instead.

Grain Deprecations
------------------

For ``smartos`` some grains have been deprecated. These grains will be removed in Neon.

- The ``hypervisor_uuid`` has been replaced with ``mdata:sdc:server_uuid`` grain.
- The ``datacenter`` has been replaced with ``mdata:sdc:datacenter_name`` grain.

Utils Deprecations
------------------

The ``salt.utils.cloud.py`` file had the following change:

- The ``fire_event`` function now requires a ``sock_dir`` argument. It was previously
  optional.

Other Miscellaneous Deprecations
--------------------------------

The ``version.py`` file had the following changes:

- The ``rc_info`` function was removed. Please use ``pre_info`` instead.
