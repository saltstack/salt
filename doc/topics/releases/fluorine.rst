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

Roster Deprecations
===================

The ``cache`` roster had the following changes:

- Support for ``roster_order`` as a list or tuple has been removed. As of the
  ``Fluorine`` release, ``roster_order`` must be a dictionary.
- The ``roster_order`` option now includes IPv6 in addition to IPv4 for the
  ``private``, ``public``, ``global`` or ``local`` settings. The syntax for these
  settings has changed to ``ipv4-*`` or ``ipv6-*``, respectively.
