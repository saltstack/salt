:orphan:

======================================
Salt Release Notes - Codename Fluorine
======================================


Minion Startup Events
---------------------

When a minion starts up it sends a notification on the event bus with a tag
that looks like this: ``salt/minion/<minion_id>/start``. For historical reasons
the minion also sends a similar event with an event tag like this:
``minion_start``. This duplication can cause a lot of clutter on the event bus
when there are many minions. Set ``enable_legacy_startup_events: False`` in the
minion config to ensure only the ``salt/minion/<minion_id>/start`` events are
sent.

The new :conf_minion:`enable_legacy_startup_events` minion config option
defaults to ``True``, but will be set to default to ``False`` beginning with
the Neon release of Salt.

The Salt Syndic currently sends an old style ``syndic_start`` event as well. The
syndic respects :conf_minion:`enable_legacy_startup_events` as well.


Failhard changes
----------------

It is now possible to override a global failhard setting with a state-level
failhard setting. This is most useful in case where global failhard is set to
``True`` and you want the execution not to stop for a specific state that
could fail, by setting the state level failhard to ``False``.
This also allows for the use of ``onfail*``-requisites, which would previously
be ignored when a global failhard was set to ``True``.
This is a deviation from previous behavior, where the global failhard setting
always resulted in an immediate stop whenever any state failed (regardless
of whether the failing state had a failhard setting of its own, or whether
any ``onfail*``-requisites were used).


Pass Through Options to :py:func:`file.serialize <salt.states.file.serialize>` State
------------------------------------------------------------------------------------

This allows for more granular control over the way in which the dataset is
serialized. See the documentation for the new ``serializer_opts`` option in the
:py:func:`file.serialize <salt.states.file.serialize>` state for more
information.


Deprecations
------------

API Deprecations
================

Support for :ref:`LocalClient <local-client>`'s ``expr_form`` argument has
been removed. Please use ``tgt_type`` instead. This change was made due to
numerous reports of confusion among community members, since the targeting
method is published to minions as ``tgt_type``, and appears as ``tgt_type``
in the job cache as well.

Those who are using the :ref:`LocalClient <local-client>` (either directly,
or implicitly via a :ref:`netapi module <all-netapi-modules>`) need to update
their code to use ``tgt_type``.

.. code-block:: python

    >>> import salt.client
    >>> local = salt.client.LocalClient()
    >>> local.cmd('*', 'cmd.run', ['whoami'], tgt_type='glob')
    {'jerry': 'root'}

Module Deprecations
===================

The ``napalm_network`` module had the following changes:

- Support for the ``template_path`` has been removed in the ``load_template``
  function. This is because support for NAPALM native templates has been
  dropped.

The ``trafficserver`` module had the following changes:

- Support for the ``match_var`` function was removed. Please use the
  ``match_metric`` function instead.
- Support for the ``read_var`` function was removed. Please use the
  ``read_config`` function instead.
- Support for the ``set_var`` function was removed. Please use the
  ``set_config`` function instead.

The ``win_update`` module has been removed. It has been replaced by ``win_wua``
module.

The ``win_wua`` module had the following changes:

- Support for the ``download_update`` function has been removed. Please use the
  ``download`` function instead.
- Support for the ``download_updates`` function has been removed. Please use the
  ``download`` function instead.
- Support for the ``install_update`` function has been removed. Please use the
  ``install`` function instead.
- Support for the ``install_updates`` function has been removed. Please use the
  ``install`` function instead.
- Support for the ``list_update`` function has been removed. Please use the
  ``get`` function instead.
- Support for the ``list_updates`` function has been removed. Please use the
  ``list`` function instead.

Pillar Deprecations
===================

The ``vault`` pillar had the following changes:

- Support for the ``profile`` argument was removed. Any options passed up until
  and following the first ``path=`` are discarded.

Roster Deprecations
===================

The ``cache`` roster had the following changes:

- Support for ``roster_order`` as a list or tuple has been removed. As of the
  ``Fluorine`` release, ``roster_order`` must be a dictionary.
- The ``roster_order`` option now includes IPv6 in addition to IPv4 for the
  ``private``, ``public``, ``global`` or ``local`` settings. The syntax for these
  settings has changed to ``ipv4-*`` or ``ipv6-*``, respectively.

State Deprecations
==================

The ``docker`` state has been removed. The following functions should be used
instead.

- The ``docker.running`` function was removed. Please update applicable SLS files
  to use the ``docker_container.running`` function instead.
- The ``docker.stopped`` function was removed. Please update applicable SLS files
  to use the ``docker_container.stopped`` function instead.
- The ``docker.absent`` function was removed. Please update applicable SLS files
  to use the ``docker_container.absent`` function instead.
- The ``docker.absent`` function was removed. Please update applicable SLS files
  to use the ``docker_container.absent`` function instead.
- The ``docker.network_present`` function was removed. Please update applicable
  SLS files to use the ``docker_network.present`` function instead.
- The ``docker.network_absent`` function was removed. Please update applicable
  SLS files to use the ``docker_network.absent`` function instead.
- The ``docker.image_present`` function was removed. Please update applicable SLS
  files to use the ``docker_image.present`` function instead.
- The ``docker.image_absent`` function was removed. Please update applicable SLS
  files to use the ``docker_image.absent`` function instead.
- The ``docker.volume_present`` function was removed. Please update applicable SLS
  files to use the ``docker_volume.present`` function instead.
- The ``docker.volume_absent`` function was removed. Please update applicable SLS
  files to use the ``docker_volume.absent`` function instead.

The ``docker_network`` state had the following changes:

- Support for the ``driver`` option has been removed from the ``absent`` function.
  This option had no functionality in ``docker_network.absent``.

The ``git`` state had the following changes:

- Support for the ``ref`` option in the ``detached`` state has been removed.
  Please use the ``rev`` option instead.

The ``k8s`` state has been removed. The following functions should be used
instead:

- The ``k8s.label_absent`` function was removed. Please update applicable SLS
  files to use the ``kubernetes.node_label_absent`` function instead.
- The ``k8s.label_present`` function was removed. Please updated applicable SLS
  files to use the ``kubernetes.node_label_present`` function instead.
- The ``k8s.label_folder_absent`` function was removed. Please update applicable
  SLS files to use the ``kubernetes.node_label_folder_absent`` function instead.

The ``netconfig`` state had the following changes:

- Support for the ``template_path`` option in the ``managed`` state has been
  removed. This is because support for NAPALM native templates has been dropped.

The ``trafficserver`` state had the following changes:

- Support for the ``set_var`` function was removed. Please use the ``config``
  function instead.

The ``win_update`` state has been removed. Please use the ``win_wua`` state instead.

Utils Deprecations
==================

The ``vault`` utils module had the following changes:

- Support for specifying Vault connection data within a 'profile' has been removed.
  Please see the :mod:`vault execution module <salt.modules.vault>` documentation for
  details on the new configuration schema.

=======
SaltSSH major updates
=====================

SaltSSH now works across different major Python versions. Python 2.7 ~ Python 3.x
are now supported transparently. Requirement is, however, that the SaltMaster should
have installed Salt, including all related dependencies for Python 2 and Python 3.
Everything needs to be importable from the respective Python environment.

SaltSSH can bundle up an arbitrary version of Salt. If there would be an old box for
example, running an outdated and unsupported Python 2.6, it is still possible from
a SaltMaster with Python 3.5 or newer to access it. This feature requires an additional
configuration in /etc/salt/master as follows:


.. code-block:: yaml

       ssh_ext_alternatives:
           2016.3:                     # Namespace, can be actually anything.
               py-version: [2, 6]      # Constraint to specific interpreter version
               path: /opt/2016.3/salt  # Main Salt installation
               dependencies:           # List of dependencies and their installation paths
                 jinja2: /opt/jinja2
                 yaml: /opt/yaml
                 tornado: /opt/tornado
                 msgpack: /opt/msgpack
                 certifi: /opt/certifi
                 singledispatch: /opt/singledispatch.py
                 singledispatch_helpers: /opt/singledispatch_helpers.py
                 markupsafe: /opt/markupsafe
                 backports_abc: /opt/backports_abc.py

It is also possible to use several alternative versions of Salt. You can for instance generate
a minimal tarball using runners and include that. But this is only possible, when such specific
Salt version is also available on the Master machine, although does not need to be directly
installed together with the older Python interpreter.
