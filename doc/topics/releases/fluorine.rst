:orphan:

======================================
Salt Release Notes - Codename Fluorine
======================================


Minion Startup Events
---------------------

When a minion starts up it sends a notification on the event bus with a tag
that looks like this: `salt/minion/<minion_id>/start`. For historical reasons
the minion also sends a similar event with an event tag like this:
`minion_start`. This duplication can cause a lot of clutter on the event bus
when there are many minions. Set `enable_legacy_startup_events: False` in the
minion config to ensure only the `salt/minion/<minion_id>/start` events are
sent.

The new :conf_minion:`enable_legacy_startup_events` minion config option
defaults to ``True``, but will be set to default to ``False`` beginning with
the Neon release of Salt.

The Salt Syndic currently sends an old style  `syndic_start` event as well. The
syndic respects :conf_minion:`enable_legacy_startup_events` as well.


Deprecations
------------

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
