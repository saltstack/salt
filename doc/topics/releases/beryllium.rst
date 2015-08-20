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

Git Pillar Rewritten
====================

The Git external pillar has been rewritten to bring it up to feature parity
with :mod:`gitfs <salt.fileserver.gitfs>`. See :mod:`here
<salt.pillar.git_pillar>` for more information on the new git_pillar
functionality.

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
