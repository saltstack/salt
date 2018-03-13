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
